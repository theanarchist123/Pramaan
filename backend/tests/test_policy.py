from app.agents import policy


def test_policy_numbers_are_pinned():
    # Changing any of these changes who gets auto-approved. Edit them deliberately, bump policy.VERSION, and update this test with a reason.
    assert policy.FLAG_CAPS == {"identity_mismatch": 0.4, "suspicious": 0.5, "unreadable": 0.7, "partial_match": 0.7,
                                "not_a_credential": 0.7, "issuer_unrecognised": 0.7}
    assert (policy.NO_IDENTITY_CAP, policy.CONTRADICTED_CAP, policy.UNSUPPORTED_BIO_CAP) == (0.9, 0.4, 0.8)
    assert all(v < 0.9 for v in policy.FLAG_CAPS.values()), "a flagged document must always keep a profile below the 0.90 floor"


def test_decide_needs_score_and_no_reasons():
    assert policy.decide(0.95, [], 0.9) == "auto_approve"
    assert policy.decide(0.95, ["a person must look"], 0.9) == "escalate"
    assert policy.decide(0.85, [], 0.9) == "escalate"


def test_shadow_reports_but_cannot_go_below_the_floor():
    r = policy.shadow(0.91, [], 0.95, 0.5, actual="escalate")
    assert r["candidate_threshold"] == 0.90 and r["would_be"] == "auto_approve" and r["differs"]
