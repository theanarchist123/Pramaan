from app.agents.textutil import name_similarity, quote_in_source, token_overlap

SOURCE = "Meera Iyer is an Indian marine scientist. She received the Sagar Samman award in 2024."


def test_quote_must_appear_in_source():
    assert quote_in_source("She received the Sagar Samman award in 2024", SOURCE)
    assert quote_in_source("she RECEIVED the sagar samman award in 2024!", SOURCE)  # case/punct tolerant
    assert not quote_in_source("She received the Padma Vibhushan in 2024", SOURCE)  # invented
    assert not quote_in_source("short", SOURCE)  # too short to be evidence
    assert not quote_in_source("", SOURCE)


def test_name_similarity_ignores_parenthetical_and_catches_namesakes():
    assert name_similarity("Meera Iyer (scientist)", "Meera Iyer") > 0.95
    assert name_similarity("Meera Iyer", "Meera Iyengar") < 0.95
    assert name_similarity("Rahul Dravid", "Meera Iyer") < 0.5


def test_token_overlap():
    assert token_overlap("Sagar Samman award", "She won the Sagar Samman award") == 1.0
    assert token_overlap("Padma Shri", "Sagar Samman award") == 0.0
    assert token_overlap("", "anything") == 0.0
