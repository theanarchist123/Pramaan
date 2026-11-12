"""Deterministic offline stand-ins for each agent's LLM call.

Used when LLM_MODE=mock or no API key is set, so the whole product (and every test) runs
without network or cost. They are intentionally simple heuristics, not pretend-intelligence:
the live model replaces them with no change to the surrounding code.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.agents.schemas import (
    BioAudit,
    ClaimVerdict,
    DiscoveryDraft,
    DocumentExtraction,
    DraftClaim,
    ExtractedClaim,
    FactCheckReport,
    SetuEdgeProposal,
    SetuProposals,
    ProfileDelta,
    SaathiTurn,
)
from app.domain import INDIAN_STATES, SECTORS

_STOP = {
    "the", "a", "an", "of", "in", "for", "and", "to", "at", "on", "by", "with", "from",
    "was", "is", "he", "she", "her", "his", "their", "received", "awarded", "won", "got",
}

_SECTOR_KEYWORDS = {
    "Science": ["scientist", "physicist", "research", "isro", "marine", "biolog", "chemist", "astronom"],
    "Technology": ["software", "engineer", "startup", "ai ", "tech", "developer", "computer"],
    "Healthcare": ["doctor", "surgeon", "medical", "hospital", "physician", "health"],
    "Education": ["professor", "teacher", "university", "educat", "school"],
    "Arts & Culture": ["artist", "musician", "dancer", "singer", "painter", "actor", "film"],
    "Literature": ["author", "writer", "poet", "novel"],
    "Sports": ["cricket", "athlete", "olympic", "footballer", "player", "wrestler"],
    "Business": ["founder", "entrepreneur", "ceo", "business", "industrialist"],
    "Public Service": ["ias", "officer", "minister", "civil servant", "policy"],
    "Law": ["lawyer", "judge", "advocate", "justice"],
    "Media": ["journalist", "editor", "anchor", "broadcast"],
    "Social Work": ["activist", "ngo", "social work", "community"],
    "Agriculture": ["farmer", "agricultur", "agronom", "crop"],
    "Energy": ["solar", "renewable", "energy", "wind power", "clean-energy"],
}

_CLAIM_HINTS = [
    ("award", r"\b(award|prize|medal|samman|puraskar|padma|bharat ratna|fellowship|honou?r)\b"),
    ("education", r"\b(ph\.?d|b\.?tech|m\.?tech|degree|graduat|studied|msc|mba|iit|iim)\b"),
    ("position", r"\b(professor|director|chairman|ceo|founder|head of|secretary|president)\b"),
    ("publication", r"\b(published|authored|paper|book|journal)\b"),
    ("membership", r"\b(member of|fellow of|academy)\b"),
    ("achievement", r"\b(led|built|launched|discovered|invented|pioneered|founded)\b"),
]


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", "", text.lower())).strip()


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _year(text: str) -> int | None:
    m = re.search(r"\b(19[0-9]{2}|20[0-4][0-9])\b", text)
    return int(m.group(1)) if m else None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 12]


# --------------------------------------------------------------------------- #
def saathi(ctx: dict[str, Any]) -> SaathiTurn:
    text: str = ctx.get("user_text", "")
    profile: dict = ctx.get("profile", {})
    delta = ProfileDelta()

    m = re.search(
        r"(?i:my name is|i am|i'm|this is)\s+((?i:dr\.?\s+|prof\.?\s+)?[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})",
        text,
    )
    if m and not profile.get("name_known"):
        delta.full_name = m.group(1).strip()

    low = text.lower()
    for state in INDIAN_STATES:
        if state.lower() in low:
            delta.state = state
            break
    for sector, words in _SECTOR_KEYWORDS.items():
        if any(w in low for w in words) and not profile.get("sector"):
            delta.sector = sector
            break
    if profile.get("sector") is None and delta.sector is None:
        for sector in SECTORS:
            if sector.lower() in low:
                delta.sector = sector
                break

    claims: list[ExtractedClaim] = []
    for sentence in _sentences(text):
        for field, pattern in _CLAIM_HINTS:
            if re.search(pattern, sentence, re.I):
                claims.append(ExtractedClaim(field=field, value=sentence[:300], year=_year(sentence), source_quote=sentence.strip()))
                break

    known_name = profile.get("name_known") or delta.full_name
    sector = profile.get("sector") or delta.sector
    state = profile.get("state") or delta.state
    n_claims = profile.get("claims_count", 0) + len(claims)
    missing = []
    if not known_name:
        missing.append("name")
    if not sector:
        missing.append("sector")
    if not state:
        missing.append("state")
    if n_claims < 1:
        missing.append("achievements")

    prompts = {
        "name": "Namaste! May I know your full name?",
        "sector": "Thank you. Which field do you work in — science, arts, business, public service, or something else?",
        "state": "Which state or union territory do you work from?",
        "achievements": "Please tell me about one achievement or award you're proud of, and the year.",
    }
    reply = prompts[missing[0]] if missing else (
        "That's everything I need. Please review your profile on the right and submit it for verification."
    )
    return SaathiTurn(
        reply=reply,
        detected_language="English",
        profile_delta=delta,
        new_claims=claims,
        missing=missing,
        ready_to_submit=not missing,
    )


def discovery(ctx: dict[str, Any]) -> DiscoveryDraft:
    name: str = ctx.get("name", "")
    pages: list[dict] = ctx.get("pages", [])
    best, best_score = -1, 0.0
    for i, page in enumerate(pages):
        score = name_similarity(re.sub(r"\(.*?\)", "", page["title"]), name)
        if score > best_score:
            best, best_score = i, score
    if best < 0 or best_score < 0.8:
        return DiscoveryDraft(
            chosen_index=-1, confidence=best_score, headline="", sector="", state="", city="",
            claims=[], reason="No public page clearly matches this name.",
        )
    extract = pages[best]["extract"]
    claims = []
    for sentence in _sentences(extract):
        for field, pattern in _CLAIM_HINTS:
            if re.search(pattern, sentence, re.I):
                claims.append(
                    DraftClaim(field=field, value=sentence[:200], year=_year(sentence), source_quote=sentence)
                )
                break
        if len(claims) >= 4:
            break
    low = extract.lower()
    sector = next((s for s, words in _SECTOR_KEYWORDS.items() if any(w in low for w in words)), "")
    state = next((s for s in INDIAN_STATES if s.lower() in low), "")
    first = _sentences(extract)[:1]
    return DiscoveryDraft(
        chosen_index=best,
        confidence=round(best_score, 2),
        headline=(first[0][:120] if first else ""),
        sector=sector, state=state, city="", claims=claims,
        reason=f"Page title closely matches '{name}'.",
    )


def factcheck(ctx: dict[str, Any]) -> FactCheckReport:
    verdicts = []
    for claim in ctx.get("claims", []):
        want = _tokens(claim["value"])
        best_i, best_overlap, best_sentence = -1, 0.0, ""
        for i, src in enumerate(ctx.get("sources", [])):
            for sentence in _sentences(src["text"]):
                have = _tokens(sentence)
                if not want:
                    continue
                overlap = len(want & have) / len(want)
                if overlap > best_overlap:
                    best_i, best_overlap, best_sentence = i, overlap, sentence
        if best_overlap >= 0.6:
            verdicts.append(
                ClaimVerdict(
                    claim_id=claim["id"], verdict="supported", source_index=best_i,
                    quote=best_sentence, confidence=round(min(0.85, 0.5 + best_overlap * 0.4), 2),
                    note=f"{int(best_overlap*100)}% of the claim's key terms appear in the source.",
                )
            )
        else:
            verdicts.append(
                ClaimVerdict(
                    claim_id=claim["id"], verdict="unverifiable", source_index=-1, quote="",
                    confidence=0.0, note="No public source found that supports this claim.",
                )
            )
    return FactCheckReport(verdicts=verdicts)


def document(ctx: dict[str, Any]) -> DocumentExtraction:
    """Offline mode cannot OCR images. It reads simple text documents ('Key: value' lines)
    so the document pipeline stays testable; anything else is reported as unreadable."""
    text = ctx.get("text")
    if not text:
        return DocumentExtraction(
            doc_type="unknown", holder_name="", issuer="", title="", issued_year=None,
            legibility=0.0, suspicious=False,
            notes="Offline mode cannot read image/PDF documents; enable live mode for OCR.",
        )
    fields = {k.strip().lower(): v.strip() for k, v in re.findall(r"^([A-Za-z ]+):\s*(.+)$", text, re.M)}
    return DocumentExtraction(
        doc_type=fields.get("type", "certificate"),
        holder_name=fields.get("name", fields.get("holder", "")),
        issuer=fields.get("issuer", ""),
        title=fields.get("title", ""),
        issued_year=_year(fields.get("year", fields.get("date", ""))),
        legibility=1.0,
        suspicious=False,
        notes="Parsed from plain-text document (offline mode).",
    )


def bio_audit(ctx: dict[str, Any]) -> BioAudit:
    return BioAudit(unsupported_sentences=[])


def setu(ctx: dict[str, Any]) -> SetuProposals:
    """Offline stand-in: propose a connection wherever a statement contains another person's full name next to a collaboration word."""
    import re as _re

    edges = []
    for line in str(ctx.get("corpus", "")).split("\n"):
        low = line.lower()
        for name in ctx.get("candidates", []):
            if name.lower() in low:
                if _re.search(r"co-?author|paper|published|wrote", low):
                    kind = "co_author"
                elif _re.search(r"co-?found|founded", low):
                    kind = "co_founder"
                elif "board" in low:
                    kind = "board"
                else:
                    kind = "joint_project"
                edges.append(SetuEdgeProposal(other_name=name, kind=kind, span=line.strip()))
    return SetuProposals(edges=edges)


_DISPATCH = {
    "SetuProposals": setu,
    "SaathiTurn": saathi,
    "DiscoveryDraft": discovery,
    "FactCheckReport": factcheck,
    "DocumentExtraction": document,
    "BioAudit": bio_audit,
}


def respond(schema: type, ctx: dict[str, Any]):
    return _DISPATCH[schema.__name__](ctx)


def search_plan(ctx: dict[str, Any]):
    from app.agents.schemas import SearchPlan

    q: str = ctx.get("query", "")
    low = q.lower()
    state = next((s for s in INDIAN_STATES if s.lower() in low), None)
    sector = next((s for s, words in _SECTOR_KEYWORDS.items() if any(w in low for w in words)), None)
    return SearchPlan(state=state, sector=sector, semantic_query=q)


_DISPATCH["SearchPlan"] = search_plan


def field_proposal(ctx: dict[str, Any]):
    from app.agents.schemas import FieldProposal
    import re as _re

    req: str = ctx.get("request", "")
    low = req.lower()
    m = _re.search(r"(?:add|create|track|collect|capture)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?(?:field\s+(?:for|called|named)?\s*)?(.+?)(?:\s+field)?(?:\s*(?:\(|:|,|\bwith\b|\bone of\b)|$)", req, _re.I)
    name = (m.group(1) if m else req).strip(" .")
    name = _re.sub(r"\b(?:to|on|for)\s+(?:profiles?|people|everyone)\b", "", name, flags=_re.I).strip()
    key = _re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "extra_info"
    if not key[0].isalpha():
        key = "f_" + key
    options: list[str] = []
    ftype = "text"
    words = set(_re.findall(r"[a-z]+", low))  # whole words only: "age" must not match "stage" or "manage"
    if "one of" in low or "choose" in words or "select" in words:
        tail = req.lower().split("one of", 1)[-1] if "one of" in low else req.split(":", 1)[-1]
        options = [o.strip(" .") for o in _re.split(r",|/| or ", tail) if o.strip(" .")][:20]
        ftype = "select" if len(options) >= 2 else "text"
    elif words & {"url", "link", "website", "webpage"}:
        ftype = "url"
    elif "number of" in low or "how many" in low or words & {"year", "count", "age"}:
        ftype = "number"
    elif words & {"list", "several", "multiple", "patents", "publications", "languages", "skills", "awards", "books"}:
        ftype = "list"
    elif words & {"date", "birthday", "born"}:
        ftype = "date"
    return FieldProposal(
        key=key, label=name[:1].upper() + name[1:] if name else "Extra info", type=ftype,
        options=options if ftype == "select" else [], help_text="", searchable=ftype in ("text", "list", "select"),
        reasoning=f"Inferred a {ftype} field from the request.",
    )


def plugin_proposal(ctx: dict[str, Any]):
    from app.agents.schemas import PluginFile, PluginProposal
    import re as _re

    if ctx.get("repair"):  # offline stand-in can't actually reason about errors: return the files as they were
        files = ctx["files"]
        slug = next(k for k in files if not k.rsplit("/", 1)[-1].startswith("test_"))[len("plugins/"):-3]
        return PluginProposal(slug=slug, summary="(unchanged)", files=[PluginFile(path=k, content=v) for k, v in files.items()])

    words = [w for w in _re.findall(r"[a-z]+", ctx.get("request", "").lower()) if w not in {
        "a", "an", "the", "add", "create", "make", "build", "an", "endpoint", "api", "for", "of", "to", "show", "me", "by", "with"}]
    slug = "_".join(words[:3]) or "registry_stats"
    slug = _re.sub(r"[^a-z0-9_]", "", slug)[:30].strip("_") or "registry_stats"
    if not slug[0].isalpha():
        slug = "p_" + slug
    src = f'''"""Plugin: {slug} — approved members per state (read-only)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugin_api import get_readonly_session
from app.public_views import PublicProfile

router = APIRouter(prefix="/v1/plugins/{slug}", tags=["plugin:{slug}"])


def summarise(rows):
    """[(state, count), ...] -> sorted list of dicts, biggest first."""
    return sorted(({{"state": s or "Unknown", "count": c}} for s, c in rows), key=lambda r: (-r["count"], r["state"]))


@router.get("")
async def handler(session: AsyncSession = Depends(get_readonly_session)):
    rows = (
        await session.execute(
            select(PublicProfile.state, func.count()).group_by(PublicProfile.state)
        )
    ).all()
    return {{"plugin": "{slug}", "data": summarise(rows)}}
'''
    test = f'''from plugins.{slug} import summarise


def test_summarise_orders_by_count_then_name():
    out = summarise([("Kerala", 2), ("Goa", 2), ("Assam", 5), (None, 1)])
    assert [r["state"] for r in out] == ["Assam", "Goa", "Kerala", "Unknown"]


def test_summarise_empty():
    assert summarise([]) == []
'''
    return PluginProposal(slug=slug, summary="Counts approved members per state (read-only endpoint).",
                          files=[PluginFile(path=f"plugins/{slug}.py", content=src),
                                 PluginFile(path=f"plugins/test_{slug}.py", content=test)])


_DISPATCH["FieldProposal"] = field_proposal
_DISPATCH["PluginProposal"] = plugin_proposal


def outreach_draft(ctx: dict[str, Any]):
    from app.agents.schemas import OutreachDraft

    return outreach_template(ctx["kind"], ctx["facts"])


def outreach_template(kind: str, f: dict[str, Any]):
    """Deterministic wording — also the fallback whenever the model is unavailable."""
    from app.agents.schemas import OutreachDraft

    name = f.get("first_name") or "there"
    if kind == "welcome_share":
        return OutreachDraft(
            subject="You're verified on Pramaan — here's how to share it",
            body=(f"Hello {name},\n\nCongratulations: your profile has been verified and your signed certificate is "
                  "live. Anyone can now check it — and see that it can't be forged.\n\nShare your verification page "
                  "or add the live badge to your website or email signature. If your credentials ever change, the "
                  "badge updates by itself."))
    if kind == "needs_document":
        why = f.get("reasons") or "we couldn't confirm your identity automatically"
        return OutreachDraft(
            subject="One step left to get your Pramaan profile verified",
            body=(f"Hello {name},\n\nThanks for completing your profile. Our agents couldn't verify it on their own: "
                  f"{why}.\n\nThe quickest fix is to upload a certificate, award letter or degree that carries your "
                  "name. It takes a minute, and a matching document is what unlocks automatic approval."))
    return OutreachDraft(
        subject="Your Pramaan profile is waiting for you",
        body=(f"Hello {name},\n\nYou started a Pramaan profile and it's nearly there. It only takes a few minutes "
              "to finish — just talk to Saathi (voice or text, in any language) and your achievements are added for "
              "you.\n\nPick up exactly where you left off."))


_DISPATCH["OutreachDraft"] = outreach_draft
