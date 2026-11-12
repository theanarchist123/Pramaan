from app.agents.khoji import chips, rule_plan
from app.agents.schemas import SearchPlan


def test_rule_plan_finds_a_named_state_without_a_model():
    assert rule_plan("physicists from Kerala, please").state == "Kerala"
    assert rule_plan("anyone who won an award").state is None
    assert rule_plan("who is in Tamil Nadu?").state == "Tamil Nadu"


def test_chips_show_exactly_what_was_understood():
    assert chips(SearchPlan(state="Kerala", sector="Science", semantic_query="x")) == [
        {"kind": "state", "label": "Kerala", "value": "Kerala"}, {"kind": "sector", "label": "Science", "value": "Science"}]
    assert chips(SearchPlan(state=None, sector=None, semantic_query="x")) == []


async def test_search_returns_chips(client):
    r = await client.post("/v1/search", json={"query": "scientists in Kerala"})
    assert r.status_code == 200 and isinstance(r.json()["chips"], list)
