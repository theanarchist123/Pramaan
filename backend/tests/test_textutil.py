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


# ---------------------------------------------------------------------------------- fact capture: the quote behind a chat claim is the person's own words
def test_a_chat_claim_stores_the_literal_words_it_came_from_and_never_an_invented_quote():
    import uuid

    from app.agents.schemas import ExtractedClaim
    from app.models import Profile
    from app.services.onboarding import apply_turn
    from app.agents.schemas import ProfileDelta, SaathiTurn

    def turn(*claims):
        return SaathiTurn(reply="ok", detected_language="English", profile_delta=ProfileDelta(), new_claims=list(claims), missing=[], ready_to_submit=False)

    message = "Last year I received the Sagar Samman award for marine research, and I also teach on Sundays."
    profile = Profile(id=uuid.uuid4(), full_name="Test Person", claims=[])
    created = apply_turn(
        profile,
        turn(
            ExtractedClaim(field="award", value="Sagar Samman award 2024", year=2024, source_quote="the SAGAR SAMMAN award for marine research"),
            ExtractedClaim(field="other", value="Teaches on Sundays", year=None, source_quote="a sentence the person never wrote"),
            ExtractedClaim(field="position", value="Professor", year=None, source_quote=""),
        ),
        message=message,
    )
    quotes = [next(e.quote for e in c.evidence if e.kind == "chat") for c in created]
    assert quotes[0] == "the Sagar Samman award for marine research"  # the message's own casing, a literal slice of it
    assert quotes[0] in message
    assert quotes[1] == "Teaches on Sundays"  # an invented quote is discarded: fall back to the claim's own value
    assert quotes[2] == "Professor"  # no quote given: same fallback


def test_the_quote_must_be_a_real_stretch_of_the_message_not_a_rewording():
    from app.services.onboarding import literal_span

    assert literal_span("I won the Padma award in 2019.", "padma award in 2019") == "Padma award in 2019"
    assert literal_span("I won the Padma award in 2019.", "Padma Bhushan") == ""
    assert literal_span("short", "ab") == "" and literal_span("", "anything long enough") == ""
