"""Introduction requests and privacy-safe profile insights (v3 Phase 4).

Rules under test: an introduction message can never carry a link or an address (invariant I-7's spirit: nothing outward-facing the sender
did not author through our code), you cannot ask yourself for an introduction (I-10's spirit), and insights count visits without storing
who visited.
"""
from app.services.intros import IntroRejected, clean_message


def test_links_and_addresses_are_removed_from_the_message():
    out = clean_message("Hi! Please see https://evil.example/x or www.evil.example, mail me at a.b@evil.example or call +91 98765 43210.")
    assert "http" not in out and "www." not in out and "@" not in out and "98765" not in out
    assert out.startswith("Hi!")


def test_empty_or_link_only_messages_are_rejected():
    for bad in ["", "   ", "https://evil.example", "a@b.co"]:
        try:
            clean_message(bad)
        except IntroRejected:
            continue
        raise AssertionError(f"{bad!r} should have been rejected")


def test_message_length_is_capped():
    assert len(clean_message("word " * 1000)) <= 1000
