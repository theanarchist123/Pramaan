"""Phase 0 infrastructure: Redis-backed limits/locks/fan-out with an in-process fallback, and the Postgres job queue."""

from __future__ import annotations

import asyncio
import logging
import uuid

import pytest

from app import jobs
from app.config import get_settings
from app.core import ratelimit
from app.core import redis as rd
from app.core.locks import LockBusy, short_lock

REDIS = "redis://localhost:6379/15"


def use_redis(monkeypatch, url: str = REDIS) -> None:
    monkeypatch.setattr(get_settings(), "redis_url", url)
    rd._client = None  # rebuild the client for the new URL
    rd._down_since, rd._last_alert = None, 0.0


@pytest.fixture
async def real_redis(monkeypatch):
    use_redis(monkeypatch)
    try:
        await rd.get_redis().ping()
    except Exception:
        pytest.skip("Redis not reachable: run `docker compose up -d redis`")
    await rd.get_redis().flushdb()
    ratelimit.reset()
    yield rd.get_redis()
    await rd.get_redis().flushdb()
    await rd.close()
    ratelimit.reset()


@pytest.fixture(autouse=True)
def _restore_redis_state():
    yield
    rd._client = None
    rd._down_since, rd._last_alert = None, 0.0


# --------------------------------------------------------------------------- rate limits
async def test_rate_limits_are_shared_through_redis(real_redis):
    key = f"t-{uuid.uuid4().hex[:6]}"
    results = [(await ratelimit.check_rate_limit(key, 3))[0] for _ in range(4)]
    assert results == [True, True, True, False]
    ratelimit.reset()  # a different replica has an empty local memory: the limit must still hold
    assert (await ratelimit.check_rate_limit(key, 3))[0] is False
    assert rd.status()["state"] == "up"


async def test_login_lockout_is_shared_through_redis(real_redis):
    who = f"a-{uuid.uuid4().hex[:6]}@example.com"
    for _ in range(5):
        await ratelimit.login_failed(who)
    ratelimit.reset()
    assert await ratelimit.login_locked(who) is True
    await ratelimit.login_ok(who)
    assert await ratelimit.login_locked(who) is False


async def test_when_redis_is_down_limits_still_work_in_process_and_an_alert_is_logged(monkeypatch, caplog):
    use_redis(monkeypatch, "redis://127.0.0.1:1/0")  # nothing listens here
    ratelimit.reset()
    with caplog.at_level(logging.ERROR, logger="pramaan.redis"):
        results = [(await ratelimit.check_rate_limit("down-key", 2))[0] for _ in range(3)]
    assert results == [True, True, False]  # still limited, per process
    assert any("ALERT: Redis is unreachable" in r.message for r in caplog.records)
    assert rd.status() == {"configured": True, "state": "down", "fallback_active": True}
    assert sum("ALERT" in r.message for r in caplog.records) == 1  # once a minute, not once per request


async def test_without_a_redis_url_nothing_alerts(monkeypatch, caplog):
    use_redis(monkeypatch, "")
    with caplog.at_level(logging.ERROR, logger="pramaan.redis"):
        assert (await ratelimit.check_rate_limit("k", 1))[0] is True
    assert not caplog.records and rd.status()["state"] == "disabled"


# --------------------------------------------------------------------------- locks
@pytest.mark.parametrize("with_redis", [True, False])
async def test_a_short_lock_serialises_work(monkeypatch, with_redis):
    if with_redis:
        use_redis(monkeypatch)
        try:
            await rd.get_redis().ping()
        except Exception:
            pytest.skip("Redis not reachable")
    else:
        use_redis(monkeypatch, "")
    inside, overlap = 0, 0

    async def work():
        nonlocal inside, overlap
        async with short_lock("t-lock", ttl_seconds=5, wait_seconds=5):
            inside += 1
            overlap = max(overlap, inside)
            await asyncio.sleep(0.05)
            inside -= 1

    await asyncio.gather(*(work() for _ in range(4)))
    assert overlap == 1


async def test_a_lock_that_cannot_be_had_raises_instead_of_hanging(monkeypatch):
    use_redis(monkeypatch, "")
    async with short_lock("busy", wait_seconds=0.2):
        with pytest.raises(LockBusy):
            async with short_lock("busy", wait_seconds=0.1):
                pass


# --------------------------------------------------------------------------- live events across processes
async def test_events_from_another_process_reach_local_subscribers_through_redis(real_redis):
    from app.agents import events

    q = events.bus.subscribe()
    relay = asyncio.create_task(events.relay_from_redis())
    await asyncio.sleep(0.3)  # let it subscribe
    try:
        import json

        await real_redis.publish(events.CHANNEL, json.dumps({"id": 1, "message": "from the worker", "_origin": "another-process"}))
        await real_redis.publish(events.CHANNEL, json.dumps({"id": 2, "message": "my own echo", "_origin": events.ORIGIN}))
        got = await asyncio.wait_for(q.get(), 3)
        assert got["message"] == "from the worker" and "_origin" not in got
        await asyncio.sleep(0.2)
        assert q.empty()  # this process's own echo is ignored (it already delivered locally)
    finally:
        relay.cancel()
        events.bus.unsubscribe(q)


# --------------------------------------------------------------------------- jobs
SEEN: list[dict] = []


@jobs.task("test_echo")
async def _echo(payload: dict) -> None:
    SEEN.append(payload)


async def test_inline_jobs_run_and_unknown_tasks_are_refused():
    SEEN.clear()
    res = await jobs.enqueue("test_echo", {"n": 1})
    assert res.backend == "inline" and not res.deduped and SEEN == [{"n": 1}]  # JOB_INLINE_WAIT is on in tests
    with pytest.raises(ValueError):
        await jobs.enqueue("nope", {})


async def test_a_failing_inline_job_does_not_raise_into_the_request(caplog):
    @jobs.task("test_boom")
    async def boom(payload):
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="pramaan.jobs"):
        await jobs.enqueue("test_boom", {})
    assert any("job test_boom failed" in r.message for r in caplog.records)


def _in_selector_loop(make_coro):
    """psycopg's async mode needs a selector event loop; Windows' default (Proactor, which asyncpg and Playwright are
    happy with) cannot run it. Run the body in its own loop, on a thread, and talk to Postgres with psycopg there."""
    import selectors

    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    try:
        return loop.run_until_complete(make_coro())
    finally:
        loop.close()


async def test_the_postgres_queue_dedupes_survives_and_runs_each_job_once(monkeypatch):
    """The real Procrastinate backend against the test database."""
    import psycopg

    SEEN.clear()
    key = f"echo:{uuid.uuid4().hex}"
    await asyncio.to_thread(jobs.ensure_schema_sync)
    monkeypatch.setattr(get_settings(), "job_backend", "procrastinate")

    async def scenario():
        async with await psycopg.AsyncConnection.connect(jobs.psycopg_dsn(), autocommit=True) as conn:
            async def row(sql):
                cur = await conn.execute(sql, (key,))
                return (await cur.fetchone())[0]

            try:
                first = await jobs.enqueue("test_echo", {"n": 7}, idempotency_key=key)
                again = await jobs.enqueue("test_echo", {"n": 7}, idempotency_key=key)  # same key while still waiting
                assert first.backend == "procrastinate" and not first.deduped and first.job_id
                assert again.deduped is True
                assert SEEN == []  # queued, not run: a row in Postgres, not an in-memory task
                assert await row("SELECT count(*) FROM procrastinate_jobs WHERE queueing_lock = %s") == 1

                await jobs.run_worker(wait=False)  # what `python -m app.worker` does, until the queue is empty
                assert SEEN == [{"n": 7}]
                assert await row("SELECT status FROM procrastinate_jobs WHERE queueing_lock = %s") == "succeeded"
                # once it has run, the same key may be queued again
                assert (await jobs.enqueue("test_echo", {"n": 8}, idempotency_key=key)).deduped is False
            finally:
                await jobs.stop()

    try:
        await asyncio.to_thread(_in_selector_loop, scenario)
    finally:
        monkeypatch.setattr(get_settings(), "job_backend", "inline")
        jobs._app = jobs._run_task = None  # it was bound to the throwaway loop


async def test_procrastinate_refuses_to_start_on_a_loop_it_cannot_use(monkeypatch):
    monkeypatch.setattr(get_settings(), "job_backend", "procrastinate")
    loop_name = type(asyncio.get_running_loop()).__name__
    if "Proactor" not in loop_name:
        pytest.skip("only meaningful on Windows' default loop")
    with pytest.raises(RuntimeError, match="selector event loop"):
        await jobs.start()


async def test_verification_is_enqueued_as_a_job_and_deduped(client, make_user, monkeypatch):
    from app.agents.events import start_run
    from tests.test_agents import _interview, _start

    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    seen = []

    async def fake_enqueue(task_name, payload, idempotency_key=None):
        seen.append((task_name, payload["profile_id"], idempotency_key))
        return jobs.EnqueueResult(job_id="j1", deduped=False, backend="test")

    monkeypatch.setattr(jobs, "enqueue", fake_enqueue)
    r = await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert r.status_code == 202 and r.json()["status"] == "started"
    assert seen == [("verify_profile", profile["id"], f"verify:{profile['id']}")]
    run = await start_run("verify_profile", uuid.UUID(profile["id"]))  # something already running: not enqueued again
    again = await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert again.json() == {"run_id": str(run.run_id), "status": "already_running"} and len(seen) == 1


# --------------------------------------------------------------------------- telemetry (OPS-06)
async def test_live_model_calls_are_recorded_per_run_and_aggregated_for_admins(client, make_user, monkeypatch):
    from pydantic import BaseModel

    from app.agents.events import start_run
    from app.core import telemetry
    from app.llm.client import LLM

    class Out(BaseModel):
        ok: bool

    llm = LLM.__new__(LLM)  # a "live" LLM whose provider call is replaced: no network, no key
    llm.live, llm.provider, llm._s = True, "gemini", get_settings()

    async def fake(schema, **kw):
        telemetry.note_usage(120, 30)
        return Out(ok=True)

    monkeypatch.setattr(llm, "_structured", fake)
    run = await start_run("telemetry_test")  # binds the run to this task, so the call is attributed to it
    assert (await llm.structured(Out, system="s", user="u", tier="fast")).ok is True

    async def boom(schema, **kw):
        raise RuntimeError("model down")

    monkeypatch.setattr(llm, "_structured", boom)
    with pytest.raises(RuntimeError):
        await llm.structured(Out, system="s", user="u", tier="fast")
    await telemetry.settle()

    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    assert (await client.get("/v1/admin/agent-runs", headers=person)).status_code == 403
    rows = (await client.get("/v1/admin/agent-runs", headers=admin, params={"workflow": "telemetry_test"})).json()
    mine = next(r for r in rows if r["id"] == str(run.run_id))
    assert mine["llm"]["calls"] == 2 and mine["llm"]["errors"] == 1
    assert mine["llm"]["input_tokens"] == 120 and mine["llm"]["output_tokens"] == 30


def test_tracing_is_a_free_no_op_until_an_endpoint_is_configured():
    from app.core import telemetry

    assert get_settings().otel_exporter_otlp_endpoint == ""
    with telemetry.span("anything", k="v") as sp:
        assert sp is None


# --------------------------------------------------------------------------- fail closed (OPS-07)
def test_production_refuses_to_start_when_semantic_search_silently_degrades(monkeypatch):
    from types import SimpleNamespace

    from app import main
    from app.services import embeddings

    monkeypatch.setattr(embeddings, "get_embedder", lambda: SimpleNamespace(kind="hash"))  # the model failed to load
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "embeddings", "auto")
    with pytest.raises(RuntimeError, match="Refusing to start"):
        main._warn_if_degraded()
    monkeypatch.setattr(get_settings(), "embeddings", "hash")  # choosing lexical search on purpose is allowed
    main._warn_if_degraded()
    monkeypatch.setattr(get_settings(), "environment", "development")  # and local dev only warns
    monkeypatch.setattr(get_settings(), "embeddings", "auto")
    main._warn_if_degraded()


# --------------------------------------------------------------------------- checkpointed review (OPS-05)
async def test_an_escalated_case_pauses_the_graph_until_a_person_decides(client, make_user, monkeypatch):
    from app.agents.workflows import get_graph
    from app.services import wikipedia
    from tests.test_agents import _interview, _start

    async def nothing(name, limit=3):
        return []

    monkeypatch.setattr(wikipedia, "fetch_sources", nothing)
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert (await client.get("/v1/profiles/mine", headers=person)).json()[0]["status"] == "pending_review"

    item = next(i for i in (await client.get("/v1/admin/review", headers=admin)).json() if i["profile_id"] == profile["id"])
    thread = item["details"]["thread_id"]  # the review remembers which paused run it belongs to
    config = {"configurable": {"thread_id": thread}}
    graph = await get_graph()
    paused = await graph.aget_state(config)
    assert paused.next == ("await_review",)  # waiting for a human: this is the graph's own state, not a status flag
    assert paused.values["decision"]["decision"] == "escalate"

    await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "rejected"})
    done = await graph.aget_state(config)
    assert done.next == () and done.values["review_outcome"]["outcome"] == "rejected"  # the decision resumed the run


async def test_a_paused_review_survives_a_restart_with_the_postgres_checkpointer():
    """The point of checkpointing: pause, throw away every in-memory object, and resume from Postgres alone."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt
    from psycopg_pool import AsyncConnectionPool
    from typing_extensions import TypedDict

    class S(TypedDict, total=False):
        who: str
        outcome: dict

    async def prepare(state):
        return {"who": state["who"]}

    async def await_review(state):
        return {"outcome": interrupt({"who": state["who"]})}

    def build(saver):
        g = StateGraph(S)
        g.add_node("prepare", prepare)
        g.add_node("await_review", await_review)
        g.add_edge(START, "prepare")
        g.add_edge("prepare", "await_review")
        g.add_edge("await_review", END)
        return g.compile(checkpointer=saver)

    thread = f"restart-test:{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread}}

    async def scenario():
        async def open_graph():
            pool = AsyncConnectionPool(jobs.psycopg_dsn(), min_size=1, max_size=2, open=False, kwargs={"autocommit": True, "prepare_threshold": 0})
            await pool.open()
            saver = AsyncPostgresSaver(pool)
            await saver.setup()
            return pool, build(saver)

        pool1, graph1 = await open_graph()
        await graph1.ainvoke({"who": "Meera"}, config)
        assert (await graph1.aget_state(config)).next == ("await_review",)
        await pool1.close()  # "the process died": nothing in memory survives

        pool2, graph2 = await open_graph()  # a brand-new process, a brand-new graph object
        try:
            assert (await graph2.aget_state(config)).next == ("await_review",)  # still waiting, from Postgres alone
            await graph2.ainvoke(Command(resume={"outcome": "approved"}), config)
            final = await graph2.aget_state(config)
            assert final.next == () and final.values["outcome"] == {"outcome": "approved"}
        finally:
            await pool2.close()

    await asyncio.to_thread(_in_selector_loop, scenario)
