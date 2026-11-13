"""A person's name is recorded exactly as they wrote it, in their own script. A model that transliterates or translates it (a live eval showed Saathi writing Devanagari,
Marathi, Tamil and Bengali names in Latin letters) must not change what is recorded as their name."""
from types import SimpleNamespace

import pytest

from app.agents.schemas import ExtractedClaim, ProfileDelta, SaathiTurn
from app.services.onboarding import PLACEHOLDER_NAME, apply_turn, literal_name


@pytest.mark.parametrize("message,proposed,expected", [
    ("मेरा नाम सुनीता शर्मा है, मैं शिक्षिका हूँ।", "सुनीता शर्मा", "सुनीता शर्मा"),
    ("My name is  meera   iyer, a physicist", "Meera Iyer", "meera   iyer"),
    ("I am Dr. Raj Kumar from Goa", "Dr Raj Kumar", "Dr. Raj Kumar"),
    ("என் பெயர் லக்ஷ்மி ஐயர்", "லக்ஷ்மி ஐயர்", "லக்ஷ்மி ஐயர்"),
    ("আমার নাম অনিল চ্যাটার্জি", "অনিল চ্যাটার্জি", "অনিল চ্যাটার্জি"),
    ("मेरा नाम सुनीता शर्मा है", "Sunita Sharma", ""),             # transliterated by the model: not what they wrote
    ("My name is Meera Iyer", "Meera Iyar", ""),                    # a different spelling
    ("I live in Kerala", "Meera Iyer", ""),                         # not in the message at all
    ("", "Meera Iyer", ""),
    ("My name is Meera Iyer", "M", ""),                             # too short to be a name
])
def test_literal_name_returns_the_peoples_own_words_or_nothing(message, proposed, expected):
    assert literal_name(message, proposed) == expected


def profile():
    return SimpleNamespace(full_name=PLACEHOLDER_NAME, slug="x", headline="", sector="", state="", city="", bio="", languages=[], institutions=[], custom={}, claims=[], id=None)


def turn(name):
    return SaathiTurn(reply="ok", detected_language="Hindi", profile_delta=ProfileDelta(full_name=name), new_claims=[], missing=[], ready_to_submit=False)


def test_the_recorded_name_is_the_literal_one_and_a_transliterated_one_is_dropped():
    p = profile()
    apply_turn(p, turn("Sunita Sharma"), message="मेरा नाम सुनीता शर्मा है")
    assert p.full_name == PLACEHOLDER_NAME  # nothing recorded: the person is asked again
    apply_turn(p, turn("सुनीता शर्मा"), message="मेरा नाम सुनीता शर्मा है")
    assert p.full_name == "सुनीता शर्मा"


def test_the_recorded_name_uses_the_messages_own_spelling_and_casing():
    p = profile()
    apply_turn(p, turn("Meera Iyer"), message="my name is meera iyer")
    assert p.full_name == "meera iyer" or p.full_name == "Meera Iyer"  # either is the person's words: case only differs
    assert p.full_name.lower() == "meera iyer"


def test_without_a_message_nothing_changes_for_existing_callers():
    p = profile()
    apply_turn(p, turn("Meera Iyer"))  # no message given (older callers): behaves as before
    assert p.full_name == "Meera Iyer"


async def test_the_turn_tells_the_person_when_their_name_was_not_recorded(client, make_user, monkeypatch):
    from app.agents import saathi

    async def fake(ctx, *, profile, history, user_text, fields=()):
        return SaathiTurn(reply="Nice to meet you, Sunita!", detected_language="Hindi", profile_delta=ProfileDelta(full_name="Sunita Sharma"),
                          new_claims=[], missing=[], ready_to_submit=False)

    monkeypatch.setattr(saathi, "interview_turn", fake)
    person, _ = await make_user()
    p = (await client.post("/v1/onboarding/start", headers=person, json={"consent_public_listing": True, "consent_web_research": True})).json()["profile"]
    r = await client.post(f"/v1/onboarding/{p['id']}/message", headers=person, json={"text": "मेरा नाम सुनीता शर्मा है"})
    body = r.json()
    assert body["profile"]["full_name"] == "New Profile" and "name" in body["missing"]
    assert "exactly" in body["reply"].lower() or "ठीक" in body["reply"]
