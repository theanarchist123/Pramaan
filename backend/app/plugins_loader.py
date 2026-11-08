"""Loads approved plugins into the running API — no restart, no downtime.

Defence in depth: the source is re-checked by the code guard immediately before import (the file on
disk may have changed since it was approved), the router must carry the exact prefix
/v1/plugins/<slug> and nothing else (so a plugin can never shadow a core route), and a load failure
is logged and skipped — it can never stop the API from starting.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI

from app.config import BACKEND_DIR, get_settings
from app.services.code_guard import SLUG_RE, check_source

log = logging.getLogger("pramaan.plugins")
loaded: dict[str, dict[str, Any]] = {}


class PluginRejected(Exception):
    pass


def plugins_dir() -> Path:
    custom = get_settings().plugins_dir
    return Path(custom) if custom else BACKEND_DIR / "plugins"


def load_plugin(app: FastAPI, slug: str) -> dict[str, Any]:
    if not SLUG_RE.match(slug) or slug.startswith("__"):
        raise PluginRejected(f"invalid plugin name '{slug}'")
    if slug in loaded:
        raise PluginRejected(f"plugin '{slug}' is already loaded (restart the API to replace it)")
    path = plugins_dir() / f"{slug}.py"
    if not path.is_file():
        raise PluginRejected(f"{path.name} not found")
    source = path.read_text(encoding="utf-8")
    violations = check_source(f"plugins/{slug}.py", source, slug)
    if violations:
        raise PluginRejected("; ".join(violations[:3]))

    spec = importlib.util.spec_from_file_location(f"pramaan_plugin_{slug}", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    router = getattr(module, "router", None)
    prefix = f"/v1/plugins/{slug}"
    if not isinstance(router, APIRouter) or router.prefix != prefix:
        raise PluginRejected(f"router must be an APIRouter with prefix {prefix}")
    if any(not r.path.startswith(prefix) for r in router.routes):  # type: ignore[attr-defined]
        raise PluginRejected("every route must live under the plugin's prefix")

    app.include_router(router)
    app.openapi_schema = None  # so /docs and the SDK generator see the new endpoints
    info = {"slug": slug, "prefix": prefix, "routes": len(router.routes), "doc": (module.__doc__ or "").strip()}
    loaded[slug] = info
    log.info("plugin %s loaded (%d routes)", slug, info["routes"])
    return info


def load_all(app: FastAPI) -> None:
    d = plugins_dir()
    if not d.is_dir():
        return
    for path in sorted(d.glob("*.py")):
        slug = path.stem
        if slug.startswith("_") or slug.startswith("test_"):
            continue
        try:
            load_plugin(app, slug)
        except Exception as exc:  # noqa: BLE001 - one bad plugin must never take the API down
            log.warning("plugin %s skipped: %s", slug, exc)
