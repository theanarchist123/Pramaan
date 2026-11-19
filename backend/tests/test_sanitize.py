"""Text that reaches a stranger by email must not carry anything the sender typed that could take them elsewhere (I-7): links, addresses, bare domains, phone numbers."""
import pytest

from app.agents.doot import sanitize


@pytest.mark.parametrize("raw,gone", [
    ("See http://evil.example/x now", "evil.example"),
    ("mail bad@evil.example please", "bad@"),
    ("call +91 98765 43210 today", "98765"),
    ("call 022-2345-6789 today", "2345"),
    ("call (022) 2345 6789", "2345"),
    ("visit evil.example/path now", "evil.example"),
    ("visit www.evil.com now", "evil.com"),
    ("visit evil.co.in now", "evil.co.in"),
])
def test_links_addresses_domains_and_phone_numbers_are_removed(raw, gone):
    assert gone not in sanitize(raw)


@pytest.mark.parametrize("text", [
    "She won the Kaveri Prize in 2024 and again in 2026.",
    "Served 1998 2004 2010 as an advisor.",          # years are not a phone number
    "Dr. Rao leads the lab at the Pune institute.",   # abbreviations are not domains
    "Raised Rs 25,00,000 for the school.",
])
def test_ordinary_sentences_are_left_alone(text):
    assert sanitize(text) == text
