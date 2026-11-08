"""Shilpkar: custom fields (instant, no code) and AI-written plugins (guard → sandbox → human approval)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app import plugins_loader
from app.agents import shilpkar
from app.agents.schemas import PluginFile, PluginProposal
from app.config import get_settings
from app.services import sandbox
from tests.test_directory import _approved


def key() -> str:
    return "f_" + uuid.uuid4().hex[:10]


async def mkfield(client, admin, **kw):
    body = {"key": key(), "label": "Test field", "type": "text", **kw}
    r = await client.post("/v1/admin/fields", headers=admin, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# =========================================================================== custom fields
async def test_field_definitions_are_validated_and_admin_only(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    post = lambda **b: client.post("/v1/admin/fields", headers=admin, json=b)  # noqa: E731
    assert (await client.post("/v1/admin/fields", headers=person, json={"key": "xx_ok", "label": "L"})).status_code == 403
    assert (await post(key="Bad Key", label="L")).status_code == 422
    assert (await post(key="full_name", label="L")).status_code == 422  # reserved by the platform
    assert (await post(key="password", label="L")).status_code == 422
    assert (await post(key=key(), label="L", type="blob")).status_code == 422
    assert (await post(key=key(), label="L", type="select", options=["only-one"])).status_code == 422
    assert (await post(key=key(), label="L", type="text", options=["a", "b"])).status_code == 422
    f = await mkfield(client, admin)
    assert (await post(key=f["key"], label="dupe")).status_code == 422
    assert f["key"] in {x["key"] for x in (await client.get("/v1/fields")).json()}  # public, no auth


async def test_values_are_type_checked_on_profiles(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    num = await mkfield(client, admin, type="number", label="Patents")
    sel = await mkfield(client, admin, type="select", options=["email", "phone"], label="Contact")
    url = await mkfield(client, admin, type="url", label="Site")
    lst = await mkfield(client, admin, type="list", label="Tags")
    dt = await mkfield(client, admin, type="date", label="Born")

    async def make(custom):
        return await client.post("/v1/profiles", headers=person, json={"full_name": "Custom Tester", "custom": custom})

    ok = await make({num["key"]: "7", sel["key"]: "phone", url["key"]: "https://example.org/me",
                     lst["key"]: ["a", " b ", ""], dt["key"]: "1980-02-29"})
    assert ok.status_code == 201, ok.text
    c = ok.json()["custom"]
    assert c[num["key"]] == 7 and c[sel["key"]] == "phone" and c[lst["key"]] == ["a", "b"]

    for bad in ({num["key"]: "lots"}, {num["key"]: True}, {sel["key"]: "carrier-pigeon"}, {url["key"]: "javascript:alert(1)"},
                {url["key"]: "ftp://x"}, {dt["key"]: "29/02/1980"}, {dt["key"]: "2023-02-30"}, {lst["key"]: "not a list"},
                {"no_such_field": "x"}, {num["key"]: "NaN"}, {num["key"]: "inf"}):
        r = await make(bad)
        assert r.status_code == 422, (bad, r.text)
    assert (await make({lst["key"]: ["x" * 101]})).status_code == 422
    assert (await make({"": "x"})).status_code == 422


async def test_patching_clears_fields_and_deactivation_keeps_data(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    f = await mkfield(client, admin, label="Hobby")
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "Hobby Person", "custom": {f["key"]: "chess"}})).json()
    assert p["custom"][f["key"]] == "chess"

    patched = (await client.patch(f"/v1/profiles/{p['id']}", headers=person, json={"headline": "x"})).json()
    assert patched["custom"][f["key"]] == "chess"  # unrelated patches never wipe custom values

    # deactivate: hidden from forms, but the value is preserved (never destroyed by a config change)
    await client.patch(f"/v1/admin/fields/{f['id']}", headers=admin, json={"active": False})
    assert f["key"] not in {x["key"] for x in (await client.get("/v1/fields")).json()}
    kept = (await client.patch(f"/v1/profiles/{p['id']}", headers=person, json={"headline": "y"})).json()
    assert kept["custom"][f["key"]] == "chess"
    assert (await client.patch(f"/v1/profiles/{p['id']}", headers=person, json={"custom": {f["key"]: "go"}})).status_code == 422

    await client.patch(f"/v1/admin/fields/{f['id']}", headers=admin, json={"active": True})
    cleared = (await client.patch(f"/v1/profiles/{p['id']}", headers=person, json={"custom": {f["key"]: None}})).json()
    assert f["key"] not in cleared["custom"]


async def test_select_options_can_grow_but_never_shrink(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    f = await mkfield(client, admin, type="select", options=["a", "b"])
    assert (await client.patch(f"/v1/admin/fields/{f['id']}", headers=admin, json={"options": ["a", "b", "c"]})).status_code == 200
    assert (await client.patch(f"/v1/admin/fields/{f['id']}", headers=admin, json={"options": ["a", "c"]})).status_code == 422
    text = await mkfield(client, admin)
    assert (await client.patch(f"/v1/admin/fields/{text['id']}", headers=admin, json={"options": ["a", "b"]})).status_code == 422


async def test_a_new_field_is_searchable_the_moment_it_exists(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    f = await mkfield(client, admin, label="Favourite instrument")
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={
        "full_name": "Sitar Player", "sector": "Arts & Culture", "state": "Goa", "headline": "Musician",
        "consent_public_listing": True, "custom": {f["key"]: "zzyzxophone"}})).json()
    c = (await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": "A music prize"})).json()
    await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)
    await client.post(f"/v1/admin/claims/{c['id']}/verify", headers=admin, json={"status": "web", "confidence": 0.9})
    await client.post(f"/v1/admin/profiles/{p['id']}/status", headers=admin, json={"status": "approved"})
    hits = (await client.post("/v1/search", json={"query": "zzyzxophone"})).json()["results"]
    assert hits and hits[0]["id"] == p["id"]  # found by a field that did not exist five lines ago


def test_ai_extracted_custom_values_are_validated_leniently():
    """What the interviewer model returns is untrusted: bad values are dropped, never stored."""
    from types import SimpleNamespace as NS

    from app.agents.schemas import CustomValue, ProfileDelta
    from app.models import FieldDefinition, Profile
    from app.services.onboarding import apply_delta

    defs = [FieldDefinition(key="patents", label="Patents", type="number", options=[], active=True, searchable=True),
            FieldDefinition(key="tags", label="Tags", type="list", options=[], active=True, searchable=True),
            FieldDefinition(key="mode", label="Mode", type="select", options=["a", "b"], active=True, searchable=True)]
    p = Profile(full_name="X Y", slug="x", institutions=[], languages=[], custom={})
    apply_delta(p, ProfileDelta(custom=[
        CustomValue(key="patents", value="three"),          # not a number -> dropped
        CustomValue(key="tags", value="solar, wind ; hydro"),  # list split on , and ;
        CustomValue(key="mode", value="z"),                 # not an option -> dropped
        CustomValue(key="ghost", value="boo"),              # unknown key -> dropped
    ]), defs)
    assert p.custom == {"tags": ["solar", "wind", "hydro"]}


async def test_interviewer_is_told_about_active_fields():
    from app.agents.saathi import fields_block
    from app.models import FieldDefinition

    block = fields_block([FieldDefinition(key="mode", label="Contact mode", type="select", options=["email", "phone"],
                                          help_text="how to reach you", active=True, searchable=True)])
    assert "`mode`" in block and "email, phone" in block and "how to reach you" in block
    assert fields_block([]) == ""


# =========================================================================== Shilpkar: fields
async def test_shilpkar_proposes_a_field_but_creates_nothing(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    r = await client.post("/v1/admin/builder/field-proposal", headers=admin, json={"request": "add a patents held field"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposal"]["key"].startswith("patents_held") and body["proposal"]["type"] == "list" and body["errors"] == []
    assert body["proposal"]["key"] not in {x["key"] for x in (await client.get("/v1/fields")).json()}  # only a proposal
    assert (await client.post("/v1/admin/builder/field-proposal", headers=person, json={"request": "add a patents held field"})).status_code == 403


async def test_shilpkar_never_trusts_the_models_key(client, make_user, monkeypatch):
    admin, _ = await make_user(promote_to_admin=True)
    from app.agents.schemas import FieldProposal
    from app.llm.client import LLM

    taken = await mkfield(client, admin)

    class Sneaky(LLM):
        async def structured(self, schema, **kw):
            if schema is FieldProposal:
                return FieldProposal(key=taken["key"], label="Dupe", type="text", options=["x"], help_text="",
                                     searchable=True, reasoning="")
            return await super().structured(schema, **kw)

    from app.llm.client import set_llm_override
    set_llm_override(Sneaky())
    try:
        r = (await client.post("/v1/admin/builder/field-proposal", headers=admin, json={"request": "anything goes here"})).json()
    finally:
        set_llm_override(None)
    assert r["proposal"]["key"] != taken["key"] and r["proposal"]["key"].startswith(taken["key"])  # made unique
    assert r["proposal"]["options"] == []  # options stripped from a non-select field


# =========================================================================== Shilpkar: plugins
@pytest.fixture
def plugins_on(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "plugins_enabled", True)
    monkeypatch.setattr(plugins_loader, "plugins_dir", lambda: tmp_path)
    monkeypatch.setattr(plugins_loader, "loaded", {})
    return tmp_path


def proposal(slug: str, source: str | None = None) -> PluginProposal:
    from app.llm import mock

    p = mock.respond(PluginProposal, {"request": "members by state"})
    src = p.files[0].content.replace(p.slug, slug)
    tst = p.files[1].content.replace(p.slug, slug)
    return PluginProposal(slug=slug, summary="test plugin", files=[
        PluginFile(path=f"plugins/{slug}.py", content=source if source is not None else src),
        PluginFile(path=f"plugins/test_{slug}.py", content=tst)])


async def run_change(client, admin, monkeypatch, prop: PluginProposal):
    async def fake(ctx, request):
        return prop

    monkeypatch.setattr(shilpkar, "propose_plugin", fake)
    r = await client.post("/v1/admin/builder/changes", headers=admin, json={"request": "make me something"})
    assert r.status_code == 202, r.text
    # the pipeline runs as a background task; wait for it to reach a final state
    for _ in range(120):
        c = (await client.get(f"/v1/admin/builder/changes/{r.json()['id']}", headers=admin)).json()
        if c["status"] not in ("proposed",):
            return c
        await asyncio.sleep(0.5)
    raise AssertionError("change never finished")


async def test_unsafe_code_is_rejected_by_the_guard_and_never_reaches_the_sandbox(client, make_user, plugins_on, monkeypatch):
    admin, _ = await make_user(promote_to_admin=True)
    slug = "evil_" + uuid.uuid4().hex[:6]
    called = []
    monkeypatch.setattr(sandbox, "run_checks", lambda *a, **k: called.append(1))
    evil = proposal(slug, source=f'import os\nfrom fastapi import APIRouter\nrouter = APIRouter(prefix="/v1/plugins/{slug}")\nos.system("whoami")\n')
    c = await run_change(client, admin, monkeypatch, evil)
    assert c["status"] == "rejected_by_guard" and "import of 'os'" in " ".join(c["checks"]["guard"])
    assert not called  # the dangerous code was never run, anywhere
    r = await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)
    assert r.status_code == 409
    assert not list(plugins_on.glob("*.py"))


async def test_full_pipeline_approve_and_the_endpoint_goes_live_without_a_restart(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    await _approved(client, make_user, admin, name="Plugin Subject", sector="Science", state="Kerala", claim="Plugin test award")
    slug = "bystate_" + uuid.uuid4().hex[:6]

    c = await run_change(client, admin, monkeypatch, proposal(slug))
    assert c["status"] == "ready", c["checks"]
    assert c["checks"]["guard"] == [] and c["checks"]["sandbox"]["passed"] is True
    assert (await client.get(f"/v1/plugins/{slug}")).status_code == 404  # nothing live yet

    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=person)).status_code == 403
    applied = await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)
    assert applied.status_code == 200 and applied.json()["status"] == "applied"
    assert (plugins_on / f"{slug}.py").exists()

    live = await client.get(f"/v1/plugins/{slug}")  # new route, no restart
    assert live.status_code == 200 and any(r["state"] == "Kerala" for r in live.json()["data"])
    assert f"/v1/plugins/{slug}" in (await client.get("/openapi.json")).json()["paths"]  # docs/SDKs see it
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409  # not twice
    listed = (await client.get("/v1/admin/builder/plugins", headers=admin)).json()
    assert any(p["slug"] == slug for p in listed["plugins"])


async def test_failing_sandbox_checks_block_approval(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "broken_" + uuid.uuid4().hex[:6]
    p = proposal(slug)
    p.files[1].content += "\n\ndef test_wrong():\n    assert 1 == 2\n"
    c = await run_change(client, admin, monkeypatch, p)
    assert c["status"] == "checks_failed" and c["checks"]["sandbox"]["passed"] is False
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409


async def test_unverifiable_code_is_never_applied_when_the_sandbox_is_missing(client, make_user, plugins_on, monkeypatch):
    admin, _ = await make_user(promote_to_admin=True)

    async def no_docker():
        return False, "Docker is not installed or not running."

    monkeypatch.setattr(sandbox, "available", no_docker)
    c = await run_change(client, admin, monkeypatch, proposal("nodocker_" + uuid.uuid4().hex[:6]))
    assert c["status"] == "checks_failed" and c["checks"]["sandbox"]["ran"] is False
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409


async def test_apply_rechecks_the_code_it_is_about_to_write(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import CodeChange

    admin, _ = await make_user(promote_to_admin=True)
    slug = "swap_" + uuid.uuid4().hex[:6]
    c = await run_change(client, admin, monkeypatch, proposal(slug))
    assert c["status"] == "ready"
    # someone edits the stored files after the checks passed: apply must notice
    files = dict(c["files"])
    files[f"plugins/{slug}.py"] = "import os\n" + files[f"plugins/{slug}.py"]
    async with get_sessionmaker()() as s:
        await s.execute(update(CodeChange).where(CodeChange.id == uuid.UUID(c["id"])).values(files=files))
        await s.commit()
    r = await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)
    assert r.status_code == 409 and "Guard re-check failed" in r.text
    assert not list(plugins_on.glob("*.py"))


async def test_apply_is_refused_when_plugins_are_disabled(client, make_user, tmp_path, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    monkeypatch.setattr(get_settings(), "plugins_enabled", False)
    monkeypatch.setattr(plugins_loader, "plugins_dir", lambda: tmp_path)
    admin, _ = await make_user(promote_to_admin=True)
    c = await run_change(client, admin, monkeypatch, proposal("disabled_" + uuid.uuid4().hex[:6]))
    r = await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)
    assert r.status_code == 409 and "PLUGINS_ENABLED" in r.text
    assert not list(tmp_path.glob("*.py"))


async def test_a_rejected_change_cannot_be_applied(client, make_user, plugins_on, monkeypatch):
    admin, _ = await make_user(promote_to_admin=True)
    c = await run_change(client, admin, monkeypatch, proposal("rej_" + uuid.uuid4().hex[:6], source="import os\n"))
    r = await client.post(f"/v1/admin/builder/changes/{c['id']}/reject", headers=admin)
    assert r.json()["status"] == "rejected"
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409


# =========================================================================== loader (defence in depth)
def test_loader_refuses_shadowing_tampering_and_survives_bad_plugins(tmp_path, monkeypatch):
    from fastapi import FastAPI

    monkeypatch.setattr(plugins_loader, "plugins_dir", lambda: tmp_path)
    monkeypatch.setattr(plugins_loader, "loaded", {})
    app = FastAPI()
    hdr = "from fastapi import APIRouter\n"

    (tmp_path / "shadow.py").write_text(hdr + 'router = APIRouter(prefix="/v1/verify")\n')  # shadows a core route
    (tmp_path / "tampered.py").write_text('import os\n' + hdr + 'router = APIRouter(prefix="/v1/plugins/tampered")\n')
    (tmp_path / "noprefix.py").write_text(hdr + "router = APIRouter()\n")
    (tmp_path / "good.py").write_text(hdr + 'router = APIRouter(prefix="/v1/plugins/good")\n\n@router.get("")\ndef g():\n    return {"ok": 1}\n')
    for bad in ("shadow", "tampered", "noprefix"):
        with pytest.raises(plugins_loader.PluginRejected):
            plugins_loader.load_plugin(app, bad)
    with pytest.raises(plugins_loader.PluginRejected):
        plugins_loader.load_plugin(app, "../etc/passwd")
    with pytest.raises(plugins_loader.PluginRejected):
        plugins_loader.load_plugin(app, "missing_file")

    plugins_loader.load_all(app)  # bad ones are skipped, the good one loads, nothing raises
    assert list(plugins_loader.loaded) == ["good"]
    from fastapi.testclient import TestClient

    live = TestClient(app).get("/v1/plugins/good")  # behaviour, not FastAPI internals
    assert live.status_code == 200 and live.json() == {"ok": 1}
    assert TestClient(app).get("/v1/plugins/shadow").status_code == 404
    with pytest.raises(plugins_loader.PluginRejected):
        plugins_loader.load_plugin(app, "good")  # no silent double-registration


# =========================================================================== self-repair loop
def _calls_recorder(monkeypatch, make_fix):
    """Replace the model's repair step; record how often it was asked."""
    calls: list[str] = []

    async def fake(ctx, request, slug, files, step, output):
        calls.append(step)
        return make_fix(slug, files, step, output)

    monkeypatch.setattr(shilpkar, "repair_plugin", fake)
    return calls


async def test_the_author_fixes_its_own_lint_error_and_it_becomes_ready(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "heal_" + uuid.uuid4().hex[:6]
    clean = proposal(slug)
    sloppy = proposal(slug)
    sloppy.files[0].content = sloppy.files[0].content.replace(
        "from app.models import Profile", "from app.models import Profile, Claim")  # unused import: ruff F401

    def fix(slug_, files, step, output):
        assert step == "lint (ruff)" and "F401" in output and "Claim" in output  # it is shown the real error
        return clean

    calls = _calls_recorder(monkeypatch, fix)
    c = await run_change(client, admin, monkeypatch, sloppy)
    assert c["status"] == "ready", c["checks"]
    assert calls == ["lint (ruff)"] and c["checks"]["attempts"] == 1
    assert c["checks"]["history"][0]["step"] == "lint (ruff)"
    assert "Claim" not in c["files"][f"plugins/{slug}.py"]  # the stored (and later applied) code is the fixed one


async def test_the_author_gets_at_most_two_repairs_then_a_human_decides(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "stubborn_" + uuid.uuid4().hex[:6]
    broken = proposal(slug)
    broken.files[1].content += "\n\ndef test_wrong():\n    assert 1 == 2\n"
    calls = _calls_recorder(monkeypatch, lambda s, f, st, o: PluginProposal(
        slug=s, summary="still broken", files=[PluginFile(path=k, content=v) for k, v in f.items()]))
    c = await run_change(client, admin, monkeypatch, broken)
    assert c["status"] == "checks_failed" and len(calls) == 2 and c["checks"]["attempts"] == 2  # bounded
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409


async def test_a_repair_that_introduces_unsafe_code_is_rejected(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "trojan_" + uuid.uuid4().hex[:6]
    sloppy = proposal(slug)
    sloppy.files[0].content = sloppy.files[0].content.replace("from app.models import Profile", "from app.models import Profile, Claim")

    def evil_fix(s, files, step, output):
        files = dict(files)
        files[f"plugins/{s}.py"] = "import os\n" + files[f"plugins/{s}.py"].replace(", Claim", "")  # "fixes" lint by adding os
        return PluginProposal(slug=s, summary="fixed", files=[PluginFile(path=k, content=v) for k, v in files.items()])

    _calls_recorder(monkeypatch, evil_fix)
    c = await run_change(client, admin, monkeypatch, sloppy)
    assert c["status"] == "rejected_by_guard" and "import of 'os'" in " ".join(c["checks"]["guard"])
    assert (await client.post(f"/v1/admin/builder/changes/{c['id']}/apply", headers=admin)).status_code == 409
    assert not list(plugins_on.glob("*.py"))


async def test_a_repair_cannot_rename_the_plugin_or_add_files(client, make_user, plugins_on, monkeypatch):
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "rename_" + uuid.uuid4().hex[:6]
    sloppy = proposal(slug)
    sloppy.files[0].content = sloppy.files[0].content.replace("from app.models import Profile", "from app.models import Profile, Claim")

    def sneaky(s, files, step, output):
        return PluginProposal(slug=s, summary="x", files=[
            PluginFile(path="plugins/other_name.py", content="x = 1\n"), PluginFile(path=f"plugins/test_{s}.py", content=files[f"plugins/test_{s}.py"])])

    _calls_recorder(monkeypatch, sneaky)
    c = await run_change(client, admin, monkeypatch, sloppy)
    assert c["status"] == "rejected_by_guard" and "exactly these files" in " ".join(c["checks"]["guard"])


async def test_collapsed_line_breaks_from_the_model_are_repaired_not_fatal(client, make_user, plugins_on, monkeypatch):
    """A real Gemini failure: every newline in both files turned into a space. The guard refuses it
    (syntax error); the author is told why and resubmits properly formatted code."""
    ok, why = await sandbox.available()
    if not ok:
        pytest.skip(why)
    admin, _ = await make_user(promote_to_admin=True)
    slug = "oneline_" + uuid.uuid4().hex[:6]
    good = proposal(slug)
    squashed = proposal(slug)
    for f in squashed.files:
        f.content = " ".join(f.content.split("\n"))

    seen = {}

    def fix(s, files, step, output):
        seen["step"], seen["output"] = step, output
        return good

    calls = _calls_recorder(monkeypatch, fix)
    c = await run_change(client, admin, monkeypatch, squashed)
    assert seen["step"] == "code guard" and "syntax error" in seen["output"]  # it was told exactly what was wrong
    assert c["status"] == "ready" and len(calls) == 1 and c["checks"]["attempts"] == 1
    assert c["checks"]["history"][0]["step"] == "code guard"
    assert "\n" in c["files"][f"plugins/{slug}.py"]  # what will be applied is the repaired, multi-line code
