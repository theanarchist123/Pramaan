"""Calibration from human decisions (TRU-07). A REPORT only: it never changes a threshold (invariant I-1; the auto-approve threshold is a
governed setting with a floor of 0.90, changed only by two people)."""

from __future__ import annotations

import uuid

from app.services.calibration import Case, calibrate
from tests.test_review_workbench import staff


def _cases() -> list[Case]:
    # (confidence Prahari gave, what the human decided, the escalation reason codes)
    return [
        Case(0.93, "approved", ["FIRST_LISTING"]),
        Case(0.93, "approved", ["FIRST_LISTING"]),
        Case(0.92, "rejected", ["DOC_NAME_MISMATCH"]),
        Case(0.91, "approved", ["AWARD_CLAIM"]),
        Case(0.60, "rejected", ["CLAIM_NO_EVIDENCE"]),
        Case(0.40, "rejected", ["CLAIM_NO_EVIDENCE", "BIO_UNSUPPORTED"]),
        Case(0.0, "approved", ["USER_REQUESTED"]),
    ]


def test_it_reports_how_humans_actually_decided_per_reason_code():
    r = calibrate(_cases(), current_threshold=0.95)
    by = {row["reason_code"]: row for row in r["by_reason_code"]}
    assert by["FIRST_LISTING"] == {"reason_code": "FIRST_LISTING", "cases": 2, "approved": 2, "rejected": 0, "approval_rate": 1.0}
    assert by["CLAIM_NO_EVIDENCE"]["cases"] == 2 and by["CLAIM_NO_EVIDENCE"]["approval_rate"] == 0.0
    assert by["BIO_UNSUPPORTED"]["cases"] == 1  # a case with two reasons counts under each
    assert r["cases"] == 7 and r["approved"] == 4 and r["rejected"] == 3


def test_the_shadow_run_says_what_a_lower_threshold_would_have_done_to_past_cases():
    r = calibrate(_cases(), current_threshold=0.95)
    shadow = {row["threshold"]: row for row in r["shadow"]}
    # at 0.92 the cases scoring 0.92-0.949 would have been approved without a person: 0.93, 0.93 (humans approved) and 0.92 (humans REJECTED)
    assert shadow[0.92]["would_auto_approve"] == 3 and shadow[0.92]["humans_rejected"] == 1
    assert shadow[0.92]["humans_rejected_share"] == round(1 / 3, 3)
    # at 0.90 the 0.91 case (humans approved) joins them
    assert shadow[0.90]["would_auto_approve"] == 4 and shadow[0.90]["humans_rejected"] == 1
    # at the current threshold nothing changes
    assert shadow[0.95]["would_auto_approve"] == 0
    # never offers a threshold under the governed floor
    assert min(shadow) >= 0.90


def test_it_makes_no_recommendation_it_could_act_on_and_says_so_when_there_is_too_little_history():
    r = calibrate(_cases()[:2], current_threshold=0.95)
    assert r["enough_history"] is False and "applies nothing" in r["note"]
    full = calibrate(_cases() * 10, current_threshold=0.95)
    assert full["enough_history"] is True and "applies nothing" in full["note"]
    assert calibrate([], current_threshold=0.95)["cases"] == 0  # no history: an empty, honest report


async def test_the_endpoint_reads_real_closed_cases_and_is_staff_only(client, make_user):
    from app.db import get_sessionmaker
    from app.models import ReviewItem

    person, _ = await make_user()
    mk = lambda: client.post("/v1/profiles", headers=person, json={"full_name": f"Cal {uuid.uuid4().hex[:6]}", "consent_public_listing": True})  # noqa: E731
    p1, p2 = (await mk()).json(), (await mk()).json()
    async with get_sessionmaker()() as s:
        s.add_all([
            ReviewItem(profile_id=uuid.UUID(p1["id"]), reason="First public listing", confidence=0.93, status="approved", details={"reason_codes": ["FIRST_LISTING"]}),
            ReviewItem(profile_id=uuid.UUID(p2["id"]), reason="First public listing", confidence=0.92, status="rejected", details={"reason_codes": ["FIRST_LISTING"]}),
            ReviewItem(profile_id=uuid.UUID(p2["id"]), reason="still open", confidence=0.5, status="open", details={}),  # open cases are not history
        ])
        await s.commit()
    auditor, _ = await staff(make_user, "auditor")
    r = (await client.get("/v1/admin/calibration", headers=auditor)).json()
    row = next(x for x in r["by_reason_code"] if x["reason_code"] == "FIRST_LISTING")
    assert row["cases"] >= 2 and row["approved"] >= 1 and row["rejected"] >= 1
    assert r["current_threshold"] == 0.95 and r["floor"] == 0.9
    reviewer, _ = await staff(make_user, "reviewer")
    assert (await client.get("/v1/admin/calibration", headers=reviewer)).status_code == 403  # a reviewer is not shown this
    member, _ = await make_user()
    assert (await client.get("/v1/admin/calibration", headers=member)).status_code in (401, 403)
