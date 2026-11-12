import json
import subprocess
import sys
from pathlib import Path

from scripts.make_postman import build

ROOT = Path(__file__).resolve().parents[2]


def test_collection_covers_public_routes_and_hides_staff_routes():
    from app.main import app

    spec = app.openapi()
    col = build(spec)
    names = {i["name"] for i in col["item"]}
    assert "GET /v1/verify/{code}" in names and "POST /v1/search" in names
    assert not any("/v1/admin" in n for n in names)


def test_the_committed_collection_is_up_to_date():
    from app.main import app

    committed = json.loads((ROOT / "docs" / "api" / "pramaan.postman_collection.json").read_text(encoding="utf-8"))
    # Compare the route set, not the prose: some tests install extra routes or documentation text, which must not make this flaky.
    want = {i["name"] for i in build(app.openapi())["item"]}
    have = {i["name"] for i in committed["item"]}
    assert want <= have, f"routes missing from the committed collection {sorted(want - have)[:5]}: run cd backend && python scripts/make_postman.py"
