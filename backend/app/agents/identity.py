"""Deterministic identity and issuer checks. The model never decides these.

Two weaknesses these close:

* A forged award letter with the right name used to earn document-level confidence. Now the *issuer* must be a
  body we recognise (plus any the operator adds via TRUSTED_ISSUERS_EXTRA); otherwise the document is flagged
  and a human decides.
* A Wikipedia page with the same name is not the same person. For common names (Kumar, Singh, Patel…) the source
  must also mention a second, independent detail of the applicant (an institution, city or state).
"""

from __future__ import annotations

import re

from app.config import get_settings

# Substrings (lower-case) of issuers that can plausibly confer an award, degree or position. Deliberately broad
# on institutions and narrow on "random company/club": anything else goes to a human.
TRUSTED_ISSUER_HINTS = (
    "government of india", "govt of india", "president of india", "prime minister", "ministry", "department of",
    "padma", "bharat ratna", "rashtrapati", "lok sabha", "rajya sabha", "supreme court", "high court",
    "reserve bank", "election commission", "niti aayog", "union public service", "state government",
    "government of ", "govt. of", "council of scientific", "csir", "drdo", "isro", "icmr", "icar", "dst",
    "indian national science academy", "insa", "indian academy of sciences", "sahitya akademi",
    "sangeet natak", "lalit kala", "national film", "bcci", "olympic", "sports authority",
    "university", "institute of technology", "institute of management", "indian institute", "iit ", "iim ",
    "aiims", "iisc", "nit ", "college of", "unesco", "united nations", "nobel", "royal society", "who ",
)

# Document types that talk ABOUT someone but are not issued TO them: never proof of who the applicant is.
NON_CREDENTIAL_TYPES = ("clipping", "article", "news", "press", "blog", "post", "screenshot", "interview", "wikipedia")

COMMON_SURNAMES = {
    "kumar", "singh", "patel", "sharma", "devi", "kaur", "khan", "gupta", "das", "yadav", "verma", "shah",
    "reddy", "mishra", "joshi", "ali", "ahmed", "begum", "pandey", "chauhan",
}

_STOP = {"the", "and", "for", "with", "from", "india", "indian", "national", "professor", "doctor", "former"}


def issuer_is_recognised(issuer: str) -> bool:
    text = f" {issuer.lower().strip()} "
    if not issuer.strip():
        return False
    extra = [e.strip().lower() for e in get_settings().trusted_issuers_extra.split(",") if e.strip()]
    return any(h in text for h in (*TRUSTED_ISSUER_HINTS, *extra))


def is_credential(doc_type: str) -> bool:
    kind = doc_type.lower()
    return not any(k in kind for k in NON_CREDENTIAL_TYPES)


def is_common_name(full_name: str) -> bool:
    return any(t in COMMON_SURNAMES for t in re.findall(r"[a-z]+", full_name.lower()))


def secondary_signals(profile) -> list[str]:
    """Details about the applicant that are independent of the claim being checked."""
    raw = [*profile.institutions, profile.city, profile.state]
    signals = [s.strip() for s in raw if s and len(s.strip()) >= 3]
    # Headline words are weaker (a namesake may share a profession) but still narrow things down.
    signals += [w for w in re.findall(r"[A-Za-z]{6,}", profile.headline or "") if w.lower() not in _STOP]
    return signals


def corroborates(profile, source_text: str) -> tuple[bool, bool]:
    """-> (could_check, matched): did the source mention any second detail about this applicant?"""
    signals = secondary_signals(profile)
    if not signals:
        return False, False
    hay = source_text.lower()
    return True, any(s.lower() in hay for s in signals)
