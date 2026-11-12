"""View specs (AGT-10, tier T2): a page described as DATA, drawn by the web app's own interpreter.

An agent may propose a view, but a view is only a JSON document: a layout, a short list of blocks from a fixed set of components, and bindings to a fixed
list of public read endpoints. It can contain no script, no markup, no links and no styling, so there is nothing for the browser to run (spec 8.4: "no
agent-written JS runs in production"). The same rules are applied again by the interpreter in the browser. A draft is public to no one; publishing needs a
second person.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Public, anonymous, read-only endpoints whose answers are already safe to show to anyone.
ALLOWED_ENDPOINTS = ("/v1/stats/map", "/v1/stats", "/v1/transparency", "/v1/graph", "/v1/profiles")
MAX_BLOCKS = 20
MAX_TEXT = 600
_PATH = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
_MARKUP = re.compile(r"[<>]|javascript:|on\w+\s*=", re.I)
_LINK = re.compile(r"(https?:|www\.|//|\bmailto:)", re.I)
_BAD_KEYS = {"__proto__", "constructor", "prototype"}


class Bind(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    path: str = ""


class _Block(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Heading(_Block):
    type: Literal["heading"]
    text: str
    level: Literal[1, 2, 3] = 2


class Text(_Block):
    type: Literal["text"]
    text: str


class Stat(_Block):
    type: Literal["stat"]
    label: str
    bind: Bind


class BarChart(_Block):
    type: Literal["bar_chart"]
    label: str
    bind: Bind


class Table(_Block):
    type: Literal["table"]
    columns: list[str] = Field(max_length=4)
    bind: Bind


class ItemList(_Block):
    type: Literal["list"]
    label: str
    bind: Bind


Block = Annotated[Union[Heading, Text, Stat, BarChart, Table, ItemList], Field(discriminator="type")]


class ViewSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=120)
    layout: Literal["stack", "grid2", "grid3"] = "stack"
    blocks: list[Block]


COMPONENTS = {"heading", "text", "stat", "bar_chart", "table", "list"}


def _texts(b: dict) -> list[str]:
    return [v for k, v in b.items() if k in ("text", "label") and isinstance(v, str)] + [c for c in b.get("columns", []) if isinstance(c, str)]


def validate(raw) -> tuple[ViewSpec | None, list[str]]:
    """-> (the spec, []) or (None, why not). Never raises on garbage input."""
    if not isinstance(raw, dict):
        return None, ["a view spec must be a JSON object"]
    problems: list[str] = []
    blocks = raw.get("blocks")
    if isinstance(blocks, list):
        if len(blocks) > MAX_BLOCKS:
            problems.append(f"at most {MAX_BLOCKS} blocks")
        for i, b in enumerate(blocks):
            if not isinstance(b, dict):
                problems.append(f"block {i + 1} is not an object")
                continue
            if b.get("type") not in COMPONENTS:
                problems.append(f"block {i + 1}: '{b.get('type')}' is not an allowed component")
                continue
            for t in _texts(b):
                if len(t) > MAX_TEXT:
                    problems.append(f"block {i + 1}: text is too long")
                if _MARKUP.search(t):
                    problems.append(f"block {i + 1}: markup is not allowed in text")
                if _LINK.search(t):
                    problems.append(f"block {i + 1}: links are not allowed in text")
            bind = b.get("bind")
            if isinstance(bind, dict):
                if bind.get("endpoint") not in ALLOWED_ENDPOINTS:
                    problems.append(f"block {i + 1}: data may only come from the approved read endpoints")
                path = bind.get("path", "")
                if path and (not isinstance(path, str) or not _PATH.match(path) or any(p in _BAD_KEYS for p in path.split("."))):
                    problems.append(f"block {i + 1}: that binding path is not allowed")
    if raw.get("layout") not in (None, "stack", "grid2", "grid3"):
        problems.append("layout must be stack, grid2 or grid3")
    if problems:
        return None, problems
    try:
        return ViewSpec.model_validate(raw), []
    except ValidationError as exc:
        return None, [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" if e["type"] != "extra_forbidden" else f"unexpected field '{e['loc'][-1]}'" for e in exc.errors()][:6]


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    return s if len(s) >= 3 else "view"
