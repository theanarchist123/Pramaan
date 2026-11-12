"""Build a Postman collection (v2.1) from the API's own OpenAPI document, so it can never drift from the code.
    python scripts/make_postman.py            # writes ../docs/api/pramaan.postman_collection.json
Only public, anonymous endpoints and the key-authenticated developer ones are included; staff (/v1/admin) routes are left out on purpose.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LLM_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def build(openapi: dict) -> dict:
    items = []
    for path, ops in sorted(openapi["paths"].items()):
        if path.startswith("/v1/admin"):
            continue
        for method, op in sorted(ops.items()):
            if method not in ("get", "post", "patch", "delete", "put"):
                continue
            url_path = "/".join(f"{{{{{s[1:-1]}}}}}" if s.startswith("{") else s for s in path.strip("/").split("/"))
            req = {"method": method.upper(), "header": [{"key": "X-API-Key", "value": "{{api_key}}", "disabled": True}],
                   "url": {"raw": "{{base_url}}/" + url_path, "host": ["{{base_url}}"], "path": url_path.split("/")}}
            if method in ("post", "patch", "put"):
                req["header"].append({"key": "Content-Type", "value": "application/json"})
                req["body"] = {"mode": "raw", "raw": "{}"}
            items.append({"name": f"{method.upper()} {path}", "request": {**req, "description": op.get("summary") or op.get("description", "")[:300]}})
    return {"info": {"name": "Pramaan API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                     "description": "Generated from /openapi.json. Public verification needs no key."},
            "variable": [{"key": "base_url", "value": "http://localhost:8000"}, {"key": "api_key", "value": ""}], "item": items}


if __name__ == "__main__":
    from app.main import app

    out = Path(__file__).resolve().parents[2] / "docs" / "api" / "pramaan.postman_collection.json"
    out.write_text(json.dumps(build(app.openapi()), indent=2), encoding="utf-8")
    print(f"wrote {out}")
