from app.agents.textutil import claim_names_in_quote, distinctive_names


def test_distinctive_names_skip_the_persons_own_name_and_generic_words():
    assert distinctive_names("Dr. Asha Rao received the Sahitya Akademi Award in Kerala", "Asha Rao") == {"sahitya", "akademi", "kerala"}


def test_a_quote_about_something_else_does_not_back_the_claim():
    claim = "Won the Sahitya Akademi Award in 2019"
    assert claim_names_in_quote(claim, "Asha Rao was honoured with the Sahitya Akademi prize", "Asha Rao")
    assert not claim_names_in_quote(claim, "Asha Rao was honoured with the Padma Shri", "Asha Rao")


def test_claims_with_no_distinctive_name_are_not_blocked_by_this_check():
    assert claim_names_in_quote("won an award in 2019", "she won something that year", "Asha Rao")
