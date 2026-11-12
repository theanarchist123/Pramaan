"""Write the API's OpenAPI document to a file without starting a server (used to generate and check the SDKs).
    python scripts/dump_openapi.py ../packages/sdk/openapi.json
Runtime plugin routes (/v1/plugins/*) are left out: they are created by the builder, not part of the fixed API.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LLM_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

spec = app.openapi()
spec["paths"] = {p: v for p, v in spec["paths"].items() if not p.startswith("/v1/plugins/")}
out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
print(f"wrote {out}")
