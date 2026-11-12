"""Sutradhar (AGT-01): one front door for agent work, with idempotency, kill switches and budgets. Everything refused ends with a person (I-2)."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.agents import sutradhar
from app.agents.events import start_run
from app.db import get_sessionmaker
from app.models import AgentRun, LlmCall, Profile, ReviewItem
from app.services import governed


@pytest.fixture(autouse=True)
def _fresh_settings(client):  # `client` brings up the test database with the current schema
    governed.clear_cache()
    yield
    governed.clear_cache()


async def _set(key, value):
    """Write a governed setting straight to the table (the four-eyes route is tested elsewhere)."""
    from app.models import GovernedSetting

    async with get_sessionmaker()() as s:
        row = await s.get(GovernedSetting, key)
        if row is None:
            s.add(GovernedSetting(key=key, value={"v": value}, version=1))
        else:
            row.value = {"v": value}
        await s.commit()
    governed.clear_cache()


async def _clear(*keys):
    from app.models import GovernedSetting

    async with get_sessionmaker()() as s:
        await s.execute(delete(GovernedSetting).where(GovernedSetting.key.in_(keys)))
        await s.commit()
    governed.clear_cache()


async def _profile(client, make_user, name="Test Person"):
    person, _ = await make_user()
    r = await client.post("/v1/profiles", headers=person, json={"full_name": name, "sector": "Science", "state": "Kerala", "consent_public_listing": True})
    return person, r.json()["id"]


async def test_admit_allows_by_default():
    assert (await sutradhar.admit("pariksha")).ok


async def test_the_global_kill_switch_and_a_per_agent_switch_refuse():
    await _set("agents_paused", True)
    try:
        a = await sutradhar.admit("pariksha")
        assert not a.ok and "paused" in a.reason.lower()
    finally:
        await _clear("agents_paused")
    await _set("agent_lipik_enabled", False)
    try:
        assert not (await sutradhar.admit("lipik")).ok
        assert (await sutradhar.admit("pariksha")).ok  # only that agent is off
    finally:
        await _clear("agent_lipik_enabled")


async def test_the_daily_token_budget_pauses_agents_when_reached():
    await _set("daily_token_budget", 5000.0)
    try:
        assert (await sutradhar.admit("pariksha")).ok
        async with get_sessionmaker()() as s:
            s.add(LlmCall(provider="x", model="m", input_tokens=4000, output_tokens=2000, run_id=None))
            await s.commit()
        a = await sutradhar.admit("pariksha")
        assert not a.ok and "budget" in a.reason.lower()
    finally:
        await _clear("daily_token_budget")
        async with get_sessionmaker()() as s:
            await s.execute(delete(LlmCall).where(LlmCall.provider == "x"))
            await s.commit()


async def test_a_run_over_its_token_cap_is_stopped():
    ctx = await start_run("verify_profile")
    async with get_sessionmaker()() as s:
        s.add(LlmCall(provider="x", model="m", input_tokens=1500, output_tokens=0, run_id=ctx.run_id))
        await s.commit()
    await _set("run_token_cap", 1000.0)
    try:
        with pytest.raises(sutradhar.BudgetExceeded):
            await sutradhar.check_run_budget(ctx.run_id)
    finally:
        await _clear("run_token_cap")
    await sutradhar.check_run_budget(ctx.run_id)  # under the default cap: fine


async def test_dispatch_is_idempotent_and_records_the_versions_it_ran_under(client, make_user):
    _, pid = await _profile(client, make_user)
    first = await sutradhar.dispatch("profile.submitted", key=f"verify:{pid}:1", payload={"profile_id": pid}, wait=True)
    again = await sutradhar.dispatch("profile.submitted", key=f"verify:{pid}:1", payload={"profile_id": pid}, wait=True)
    assert first.status in ("started", "done") and again.status == "deduped" and again.run_id == first.run_id
    async with get_sessionmaker()() as s:
        runs = (await s.execute(select(AgentRun).where(AgentRun.idempotency_key == f"verify:{pid}:1"))).scalars().all()
        assert len(runs) == 1 and runs[0].versions.get("policy") and "prompts" in runs[0].versions


async def test_a_refused_verification_goes_to_a_person_never_to_approval(client, make_user):
    person, pid = await _profile(client, make_user)
    await _set("agents_paused", True)
    try:
        out = await sutradhar.dispatch("profile.submitted", key=f"verify:{pid}:paused", payload={"profile_id": pid}, wait=True)
    finally:
        await _clear("agents_paused")
    assert out.status == "refused"
    async with get_sessionmaker()() as s:
        p = await s.get(Profile, uuid.UUID(pid))
        assert p.status == "pending_review" and p.decision_basis == ""
        items = (await s.execute(select(ReviewItem).where(ReviewItem.profile_id == p.id, ReviewItem.status == "open"))).scalars().all()
        assert items and "paused" in items[0].reason.lower()


async def test_an_unknown_event_is_refused_not_guessed(client):
    out = await sutradhar.dispatch("profile.exploded", key="k", payload={}, wait=True)
    assert out.status == "refused" and "unknown" in out.reason.lower()


async def test_a_run_that_takes_too_long_is_stopped_and_escalated(client, make_user, monkeypatch):
    import asyncio

    _, pid = await _profile(client, make_user)

    async def slow(ctx, profile_id):
        await asyncio.sleep(5)
        return {"decision": "auto_approve"}

    monkeypatch.setattr("app.agents.workflows.run_verification", slow)

    async def tiny():
        return 0.1

    monkeypatch.setattr(sutradhar, "_wall_clock", tiny)
    try:
        out = await sutradhar.dispatch("profile.submitted", key=f"verify:{pid}:slow", payload={"profile_id": pid}, wait=True)
    finally:
        pass
    assert out.status == "timed_out"
    async with get_sessionmaker()() as s:
        p = await s.get(Profile, uuid.UUID(pid))
        assert p.status == "pending_review"
