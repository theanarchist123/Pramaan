import uuid
from types import SimpleNamespace

import pytest

from app.agents import pariksha
from app.agents.schemas import ClaimVerdict, EntailmentVerdict
from app.domain import STATUS_SELF, STATUS_WEB
from app.evidence.base import EvidenceDoc
from app.llm.client import LLMError


class Ctx:
    def __init__(self):
        self.events = []

    async def emit(self, *a, **kw):
        self.events.append(a)


def claim(value="Won the Sahitya Akademi Award in 2019", year=2019):
    return SimpleNamespace(id=uuid.uuid4(), field="award", value=value, year=year, status=STATUS_SELF, confidence=0.0, evidence=[])


PROFILE = SimpleNamespace(full_name="Asha Rao", institutions=[], city="", state="")
QUOTE = "Asha Rao won the Sahitya Akademi Award in 2019 for her poetry."


def doc(reliability=0.9):
    return EvidenceDoc(title="Asha Rao", url="https://en.wikipedia.org/wiki/Asha_Rao", text=f"Biography. {QUOTE} More text.",
                       source="wikipedia", reliability=reliability)


async def run(monkeypatch, label, reliability=0.9, conf=0.97):
    async def fake(ctx, text, quote):
        if isinstance(label, Exception):
            raise label
        return label

    monkeypatch.setattr(pariksha, "entails", fake)
    c, counts = claim(), {"supported": 0, "contradicted": 0, "unverifiable": 0, "rejected_quote": 0}
    v = ClaimVerdict(claim_id=str(c.id), verdict="supported", source_index=0, quote=QUOTE, confidence=conf, note="")
    await pariksha._apply_verdict(Ctx(), c, v, [doc(reliability)], counts, PROFILE)
    return c, counts


async def test_supports_is_accepted_and_confidence_is_capped_by_the_sources_reliability(monkeypatch):
    c, counts = await run(monkeypatch, "supports", reliability=0.8)
    assert c.status == STATUS_WEB and counts["supported"] == 1 and c.confidence == 0.8
    c, _ = await run(monkeypatch, "supports", reliability=0.99)
    assert c.confidence == 0.9  # and never above the web cap


@pytest.mark.parametrize("label", ["unrelated", "contradicts"])
async def test_unrelated_or_contradicting_never_raises_confidence(monkeypatch, label):
    c, counts = await run(monkeypatch, label)
    assert c.status == STATUS_SELF and c.confidence == 0.0 and counts["supported"] == 0 and not c.evidence
    assert counts["contradicted" if label == "contradicts" else "unverifiable"] == 1


async def test_if_the_entailment_check_cannot_run_the_claim_is_not_accepted(monkeypatch):
    class Down:
        async def structured(self, schema, **kw):
            raise LLMError("down")

    monkeypatch.setattr(pariksha, "get_llm", lambda: Down())
    c, counts = claim(), {"supported": 0, "contradicted": 0, "unverifiable": 0, "rejected_quote": 0}
    v = ClaimVerdict(claim_id=str(c.id), verdict="supported", source_index=0, quote=QUOTE, confidence=0.97, note="")
    await pariksha._apply_verdict(Ctx(), c, v, [doc()], counts, PROFILE)
    assert c.status == STATUS_SELF and counts["supported"] == 0 and not c.evidence  # I-2: no model answer means no approval path


async def test_entails_asks_the_model_and_maps_its_answer(monkeypatch):
    seen = {}

    class FakeLLM:
        async def structured(self, schema, **kw):
            seen["user"] = kw["user"]
            return EntailmentVerdict(label="supports", note="")

    monkeypatch.setattr(pariksha, "get_llm", lambda: FakeLLM())
    assert await pariksha.entails(Ctx(), "won an award", "quote <b>x</b>") == "supports"
    assert "<claim>" in seen["user"] and "<quote>" in seen["user"]


async def test_the_offline_mock_judges_by_overlap_so_evals_stay_meaningful():
    from app.llm import mock

    ok = mock.respond(EntailmentVerdict, {"claim": "Won the Sahitya Akademi Award in 2019", "quote": QUOTE})
    bad = mock.respond(EntailmentVerdict, {"claim": "Won the Sahitya Akademi Award in 2019", "quote": "Asha Rao enjoys long walks."})
    assert ok.label == "supports" and bad.label == "unrelated"
