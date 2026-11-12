"""Contract test (API-06): every path a Python SDK method calls must exist in the API, with that HTTP method."""
import re
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[2] / "packages" / "sdk" / "python" / "pramaan" / "client.py"


def sdk_calls():
    src = CLIENT.read_text(encoding="utf-8")
    for m in re.finditer(r'_Req\("(GET|POST|PATCH|DELETE|PUT)",\s*f?"([^"]+)"', src):
        yield m.group(1).lower(), re.sub(r"\{[^}]+\}", "{}", m.group(2))


def test_every_sdk_call_exists_in_the_api():
    from app.main import app

    api = {}
    for path, ops in app.openapi()["paths"].items():
        api.setdefault(re.sub(r"\{[^}]+\}", "{}", path), set()).update(ops)
    calls = list(sdk_calls())
    assert len(calls) >= 15
    missing = [(m, p) for m, p in calls if m not in api.get(p, set())]
    assert not missing, f"SDK calls that the API does not have: {missing}"
