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


# ---- the Go and Kotlin SDKs (not compiled here: no toolchain) --------------------------------------------------------------------------------
GO = CLIENT.parents[2] / "go" / "pramaan" / "client.go"
KOTLIN = CLIENT.parents[2] / "kotlin" / "src" / "main" / "kotlin" / "org" / "pramaan" / "sdk" / "Pramaan.kt"


def _first_arg(expr: str) -> str:
    """The first top-level argument of a call, string-aware."""
    depth, out, in_str, esc = 0, [], False, False
    for ch in expr:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        out.append(ch)
    return "".join(out).strip()


def _path(expr: str) -> str:
    parts = [p.strip() for p in re.split(r"\+(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", expr)]
    return "".join(p[1:-1] if p.startswith('"') and p.endswith('"') else "{}" for p in parts)


def calls_in(path, pattern):
    for m in re.finditer(pattern, path.read_text(encoding="utf-8")):
        yield m.group(1).lower(), re.sub(r"\{[^}]*\}", "{}", _path(_first_arg(m.group(2)))).rstrip("")


def test_the_go_sdk_calls_only_paths_the_api_has():
    from app.main import app

    api = {}
    for p, ops in app.openapi()["paths"].items():
        api.setdefault(re.sub(r"\{[^}]+\}", "{}", p), set()).update(ops)
    found = list(calls_in(GO, r'c\.do\(ctx, "(GET|POST|PATCH|DELETE)", ([^\n]*)'))
    assert len(found) >= 8
    assert [x for x in found if x[0] not in api.get(x[1], set())] == []


def test_the_kotlin_sdk_calls_only_paths_the_api_has():
    from app.main import app

    api = {}
    for p, ops in app.openapi()["paths"].items():
        api.setdefault(re.sub(r"\{[^}]+\}", "{}", p), set()).update(ops)
    found = list(calls_in(KOTLIN, r'call\("(GET|POST|PATCH|DELETE)", ([^\n]*)'))
    assert len(found) >= 8
    assert [x for x in found if x[0] not in api.get(x[1], set())] == []


def test_the_go_and_kotlin_webhook_verifiers_use_the_servers_exact_signing_rule():
    # The rule is `HMAC-SHA256(secret, "<t>." + body)` in hex, header "t=..,v1=..": the same as services/webhooks.sign. If that ever changes this fails.
    from app.services import webhooks as w

    assert w.sign("s", 1700000000, b"x") == __import__("hmac").new(b"s", b"1700000000.x", "sha256").hexdigest()
    assert 'mac.Write([]byte(ts + "."))' in GO.read_text(encoding="utf-8")
    assert '"$ts."' in KOTLIN.read_text(encoding="utf-8")
