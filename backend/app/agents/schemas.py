"""Structured outputs the agents must return (enforced by the API's JSON-schema mode)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ----- Saathi (interviewer) -----
class ExtractedClaim(BaseModel):
    field: Literal["award", "position", "education", "publication", "achievement", "membership", "other"]
    value: str = Field(description="One concise factual statement, in English, as the person said it")
    year: int | None = Field(description="Year if stated, else null")
    source_quote: str = Field(
        default="",
        description="The EXACT words from the person's latest message that this fact came from, copied character for character (a short stretch, not the whole message). Empty if you cannot point to specific words.",
    )


class CustomValue(BaseModel):
    key: str = Field(description="The extra field's key, exactly as listed in the prompt")
    value: str = Field(description="What the person said, as text. Lists: comma-separated.")


class ProfileDelta(BaseModel):
    full_name: str | None = None
    headline: str | None = Field(default=None, description="One line, max 120 chars")
    sector: str | None = Field(default=None, description="One of the allowed sectors")
    state: str | None = Field(default=None, description="Indian state or union territory")
    city: str | None = None
    bio: str | None = Field(default=None, description="2-4 sentences using ONLY facts the person stated")
    languages: list[str] | None = None
    institutions: list[str] | None = None
    custom: list[CustomValue] | None = Field(
        default=None, description="Values for the registry's extra fields, ONLY if the person stated them"
    )


class SaathiTurn(BaseModel):
    reply: str = Field(description="Your next message to the person, in THEIR language, warm and brief")
    detected_language: str = Field(description="ISO-ish language name, e.g. English, Hindi, Marathi")
    profile_delta: ProfileDelta
    new_claims: list[ExtractedClaim]
    missing: list[str] = Field(description="What you still need: name, sector, state, achievements, institutions")
    ready_to_submit: bool


# ----- Khoji-Pehle (discovery from public sources) -----
class DraftClaim(BaseModel):
    field: Literal["award", "position", "education", "publication", "achievement", "membership", "other"]
    value: str
    year: int | None
    source_quote: str = Field(description="Verbatim text copied from the source supporting this claim")


class DiscoveryDraft(BaseModel):
    chosen_index: int = Field(description="Index of the source that is this person, or -1 if none is clearly them")
    confidence: float = Field(description="0-1 that the chosen source is the same person")
    headline: str
    sector: str
    state: str
    city: str
    claims: list[DraftClaim]
    reason: str


# ----- Pariksha (fact-checker) -----
class ClaimVerdict(BaseModel):
    claim_id: str
    verdict: Literal["supported", "contradicted", "unverifiable"]
    source_index: int = Field(description="Index of the source used, or -1")
    quote: str = Field(description="Verbatim quote from that source, or empty")
    confidence: float = Field(description="0-1")
    note: str


class FactCheckReport(BaseModel):
    verdicts: list[ClaimVerdict]


# ----- Lipik (document reader) -----
class DocumentExtraction(BaseModel):
    doc_type: str = Field(description="certificate, award letter, degree, ID, press clipping, other")
    holder_name: str = Field(description="Full name of the person the document was issued TO; empty if it is only about someone")
    issuer: str
    title: str = Field(description="What the document certifies, e.g. 'Padma Shri' or 'PhD in Physics'")
    issued_year: int | None
    legibility: float = Field(description="0-1 how clearly the document could be read")
    suspicious: bool = Field(description="True if it looks edited, templated or inconsistent")
    notes: str


# ----- Prahari (auditor) -----
class BioAudit(BaseModel):
    unsupported_sentences: list[str] = Field(
        description="Sentences in the bio that are not supported by the verified claims"
    )


# ----- Khoji (search) -----
class SearchPlan(BaseModel):
    state: str | None = Field(default=None, description="Indian state/UT ONLY if the query names one, else null")
    sector: str | None = Field(default=None, description="One allowed sector ONLY if clearly implied, else null")
    semantic_query: str = Field(description="The query rewritten in English for semantic matching")


# ----- Shilpkar (builder) -----
class FieldProposal(BaseModel):
    key: str = Field(description="snake_case identifier, e.g. patents_held")
    label: str = Field(description="Human label, e.g. 'Patents held'")
    type: Literal["text", "number", "date", "select", "url", "list"]
    options: list[str] = Field(description="Only for type=select (2-20 options), else empty")
    help_text: str
    searchable: bool = Field(description="True if the value helps find the person in search")
    reasoning: str = Field(description="One sentence: why this key/type fits the request")


class PluginFile(BaseModel):
    path: str = Field(description="Exactly plugins/<slug>.py or plugins/test_<slug>.py")
    content: str


class PluginProposal(BaseModel):
    slug: str = Field(description="snake_case, 3-30 chars")
    summary: str = Field(description="What the plugin does, in two sentences")
    files: list[PluginFile]


# ----- Doot (outreach) -----
class OutreachDraft(BaseModel):
    subject: str = Field(description="Under 70 characters, specific, no clickbait")
    body: str = Field(description="Plain text, 60-140 words, warm and brief, no links (links are added for you)")


# ----- Setu (connections between people) -----
class SetuEdgeProposal(BaseModel):
    other_name: str = Field(description="The other person's name, exactly as given in <others>")
    kind: Literal["co_author", "co_founder", "board", "joint_project"]
    span: str = Field(description="The EXACT words from the person's own statements that say this, copied character for character; must name the other person")


class SetuProposals(BaseModel):
    edges: list[SetuEdgeProposal] = Field(default_factory=list)
