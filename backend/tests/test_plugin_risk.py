from app.services.plugin_risk import assess

LOW = '''"""Count profiles per state."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from app.plugin_api import get_readonly_session
from app.public_views import PublicProfile
router = APIRouter(prefix="/v1/plugins/bystate", tags=["plugin:bystate"])
@router.get("")
async def go(limit: int = Query(20, le=50), s=Depends(get_readonly_session)):
    rows = await s.execute(select(PublicProfile.state, func.count()).group_by(PublicProfile.state).limit(limit))
    return [{"state": a, "n": b} for a, b in rows]
'''

HIGH = '''"""Everything."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from app.plugin_api import get_readonly_session
from app.public_views import PublicProfile, PublicClaim, PublicEvidence, PublicCertificate
router = APIRouter(prefix="/v1/plugins/all", tags=["plugin:all"])
@router.get("")
async def go(s=Depends(get_readonly_session)):
    a = (await s.execute(select(PublicProfile))).scalars().all()
    b = (await s.execute(select(PublicClaim).join(PublicEvidence, PublicEvidence.claim_id == PublicClaim.profile_id))).scalars().all()
    c = (await s.execute(select(PublicCertificate))).scalars().all()
    return {"a": a, "b": b, "c": c}
'''


def test_a_small_bounded_aggregate_is_low_risk():
    r = assess({"plugins/bystate.py": LOW})
    assert r["level"] == "low" and r["tables"] == ["PublicProfile"] and r["bounded"] and r["score"] < 40


def test_many_tables_joins_and_no_limit_is_high_risk():
    r = assess({"plugins/all.py": HIGH})
    assert r["level"] == "high" and len(r["tables"]) == 4 and not r["bounded"] and any("limit" in x.lower() for x in r["reasons"])


def test_assess_never_raises_on_garbage_and_treats_it_as_high():
    r = assess({"plugins/x.py": "def ("})
    assert r["level"] == "high"
    assert assess({})["level"] == "high"
