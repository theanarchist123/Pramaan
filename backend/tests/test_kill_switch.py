import uuid


from app.agents import workflows
from app.services import governed


class _Ctx:
    run_id = uuid.uuid4()

    def __init__(self):
        self.finished = None

    async def finish(self, status, summary):
        self.finished = (status, summary)


def test_kill_switch_is_a_governed_setting_off_by_default():
    assert governed.GOVERNED["agents_paused"].default() is False


async def test_paused_agents_never_run_and_escalate(monkeypatch):
    async def paused(key):
        return key == "agents_paused"

    async def boom():
        raise AssertionError("the workflow graph must not start while paused")

    escalated = []

    async def esc(ctx, pid, why):
        escalated.append(why)

    monkeypatch.setattr(governed, "get", paused)
    monkeypatch.setattr(workflows, "get_graph", boom)
    monkeypatch.setattr(workflows, "_escalate_on_failure", esc)
    ctx = _Ctx()
    out = await workflows.run_verification(ctx, uuid.uuid4())
    assert out["decision"] == "escalate" and escalated and ctx.finished[0] == "failed"
