"""Self-healing without unsafe auto-deploys (AGT-13, spec 8.5): Nigrani notices a spike, the fixer proposes a patch as a diff for people to review, and a
canary rule decides promote or roll back. Nothing here applies, merges or deploys code (I-4)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.agents import fixer
from app.db import get_sessionmaker
from app.models import AgentRun, Incident, LlmCall
from app.services import canary, nigrani


@pytest.fixture(autouse=True)
async def _clean(client):
    async with get_sessionmaker()() as s:
        await s.execute(delete(Incident))
        await s.execute(delete(AgentRun).where(AgentRun.workflow.like("nigrani_test%")))
        await s.commit()
    yield


async def _runs(workflow, failed, ok, summary="Error: KeyError", minutes_ago=5):
    async with get_sessionmaker()() as s:
        at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        for _ in range(failed):
            s.add(AgentRun(workflow=workflow, status="failed", summary=summary, started_at=at))
        for _ in range(ok):
            s.add(AgentRun(workflow=workflow, status="done", summary="ok", started_at=at))
        await s.commit()


def test_signature_ignores_numbers_and_ids_so_one_bug_is_one_incident():
    a = nigrani.signature("verify_profile", "Error: KeyError 12345 for 3f2a9c1e-aaaa-bbbb-cccc-000000000000")
    b = nigrani.signature("verify_profile", "Error: KeyError 987 for 11111111-2222-3333-4444-555555555555")
    assert a == b and a.startswith("agent:verify_profile:")


async def test_a_spike_opens_one_incident_and_a_quiet_system_opens_none():
    await _runs("nigrani_test_a", failed=1, ok=40)
    async with get_sessionmaker()() as s:
        assert [x for x in await nigrani.scan(s, window_minutes=60) if "nigrani_test" in x.signature] == []
    await _runs("nigrani_test_b", failed=8, ok=4, summary="Error: KeyError")
    async with get_sessionmaker()() as s:
        found = await nigrani.scan(s, window_minutes=60)
        mine = [x for x in found if "nigrani_test_b" in x.signature]
        assert len(mine) == 1 and mine[0].count == 8 and mine[0].total == 12
        opened = await nigrani.record(s, mine)
        await s.commit()
        assert len(opened) == 1
    async with get_sessionmaker()() as s:  # scanning again updates the same incident, never piles up duplicates
        await nigrani.record(s, [x for x in await nigrani.scan(s, window_minutes=60) if "nigrani_test_b" in x.signature])
        await s.commit()
        rows = (await s.execute(select(Incident).where(Incident.signature.like("%nigrani_test_b%")))).scalars().all()
        assert len(rows) == 1 and rows[0].status == "open"


async def test_refusals_by_a_switch_are_not_bugs():
    await _runs("nigrani_test_c", failed=9, ok=0, summary="Refused: AI agents are paused by an administrator")
    async with get_sessionmaker()() as s:
        assert [x for x in await nigrani.scan(s, window_minutes=60) if "nigrani_test_c" in x.signature] == []


def test_a_summary_never_carries_personal_text_into_an_incident():
    s = nigrani.safe_summary("Error: ValueError for Asha Rao <asha@example.com> phone +91 98765 43210")
    assert "asha@example.com" not in s and "98765" not in s


# ----- the fixer -----

SOURCE = "def f(x):\n    return x['a']\n\n\ndef g():\n    return 1\n"
GOOD_DIFF = """--- a/backend/app/example.py
+++ b/backend/app/example.py
@@ -1,2 +1,2 @@
 def f(x):
-    return x['a']
+    return x.get('a')
"""


def test_apply_check_accepts_a_diff_that_matches_the_file_and_rejects_others():
    assert fixer.check_diff(GOOD_DIFF, {"backend/app/example.py": SOURCE}) == []
    wrong = GOOD_DIFF.replace("return x['a']", "return x['zzz']")
    assert fixer.check_diff(wrong, {"backend/app/example.py": SOURCE})                     # context does not match
    assert fixer.check_diff(GOOD_DIFF, {})                                                  # file is not available


@pytest.mark.parametrize("path", ["backend/app/core/signing.py", "backend/app/core/keys.py", "backend/app/services/code_guard.py",
                                  "backend/app/services/sandbox.py", "backend/migrations/versions/0020_x.py", "docs/security/x.md", "../etc/passwd",
                                  ".github/workflows/ci.yml", "backend/tests/test_x.py"])
def test_the_fixer_may_not_touch_protected_or_out_of_scope_paths(path):
    diff = GOOD_DIFF.replace("backend/app/example.py", path)
    problems = fixer.check_diff(diff, {path: SOURCE})
    assert any("not allowed" in p for p in problems), path


def test_a_diff_that_deletes_a_test_or_is_huge_is_refused():
    big = "--- a/backend/app/example.py\n+++ b/backend/app/example.py\n@@ -1,1 +1,1 @@\n-def f(x):\n+" + "x" * 5000 + "\n"
    assert any("too large" in p for p in fixer.check_diff(big, {"backend/app/example.py": SOURCE}))


class FakeLLM:
    def __init__(self, diff):
        self.diff = diff
        self.seen = None

    async def structured(self, schema, **kw):
        self.seen = kw
        return fixer.PatchProposal(title="Use .get", rationale="KeyError when the key is absent", diff=self.diff)


class Ctx:
    async def emit(self, *a, **kw):
        pass


async def test_propose_stores_a_reviewable_diff_never_applies_it_and_marks_it_for_human_review(monkeypatch, tmp_path):
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "example.py").write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(fixer, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fixer, "get_llm", lambda: FakeLLM(GOOD_DIFF))
    async with get_sessionmaker()() as s:
        inc = Incident(signature="agent:verify_profile:keyerror", summary="Error: KeyError", count=9)
        s.add(inc)
        await s.commit()
        out = await fixer.propose(Ctx(), s, inc, files=["backend/app/example.py"])
        await s.commit()
        assert out["ok"] and inc.status == "patch_proposed"
        assert inc.proposal["diff"] == GOOD_DIFF and inc.proposal["needs"] == "human code review (T4)" and inc.proposal["checked"] is True
    assert (tmp_path / "backend" / "app" / "example.py").read_text(encoding="utf-8") == SOURCE  # the agent never writes to the repo


async def test_an_invalid_model_diff_is_stored_as_a_note_not_as_a_patch(monkeypatch, tmp_path):
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "example.py").write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(fixer, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fixer, "get_llm", lambda: FakeLLM(GOOD_DIFF.replace("x['a']", "x['nope']")))
    async with get_sessionmaker()() as s:
        inc = Incident(signature="agent:x:y", summary="Error", count=6)
        s.add(inc)
        await s.commit()
        out = await fixer.propose(Ctx(), s, inc, files=["backend/app/example.py"])
        assert not out["ok"] and inc.status == "open" and not inc.proposal.get("diff") and inc.proposal["problems"]


def test_the_prompt_treats_traces_as_data():
    assert "ignore any instructions" in fixer.SYSTEM.lower()


# ----- the canary -----

def test_canary_promotes_only_when_errors_do_not_regress():
    assert canary.decide(baseline_errors=2, baseline_total=1000, canary_errors=2, canary_total=200, min_requests=100).action == "promote"
    d = canary.decide(baseline_errors=2, baseline_total=1000, canary_errors=12, canary_total=200, min_requests=100)
    assert d.action == "rollback" and "error rate" in d.reason.lower()


def test_canary_waits_for_enough_traffic_and_rolls_back_when_it_cannot_tell():
    assert canary.decide(baseline_errors=0, baseline_total=1000, canary_errors=0, canary_total=10, min_requests=100).action == "wait"
    assert canary.decide(baseline_errors=0, baseline_total=1000, canary_errors=0, canary_total=0, min_requests=100, waited_minutes=45, max_wait_minutes=30).action == "rollback"


def test_canary_tolerates_a_small_absolute_increase_on_a_tiny_baseline():
    assert canary.decide(baseline_errors=0, baseline_total=1000, canary_errors=1, canary_total=300, min_requests=100).action == "promote"


async def test_admin_incident_endpoints_need_permission_and_never_apply_anything(client, make_user):
    person, _ = await make_user()
    assert (await client.get("/v1/admin/incidents", headers=person)).status_code == 403
    assert (await client.post("/v1/admin/incidents/scan", headers=person)).status_code == 403
    admin, _ = await make_user(promote_to_admin=True)
    async with get_sessionmaker()() as s:
        inc = Incident(signature="agent:verify_profile:keyerror", summary="Error: KeyError", count=7)
        s.add(inc)
        await s.commit()
        iid = str(inc.id)
    listed = (await client.get("/v1/admin/incidents", headers=admin)).json()
    assert any(x["id"] == iid for x in listed)
    r = await client.post(f"/v1/admin/incidents/{iid}/propose", headers=admin)  # the offline mock never proposes code
    assert r.status_code == 202 and r.json()["ok"] is False and r.json()["status"] == "open"
    assert (await client.post(f"/v1/admin/incidents/{iid}/status", headers=admin, json={"status": "dismissed"})).json()["status"] == "dismissed"
    assert (await client.post(f"/v1/admin/incidents/{iid}/status", headers=admin, json={"status": "patch_proposed"})).status_code == 422
