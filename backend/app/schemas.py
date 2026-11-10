from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----- auth -----
class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=255)
    role: Literal["person", "delegate"] = "person"


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: uuid.UUID
    email: str
    name: str
    role: str
    email_verified: bool = False

    @model_validator(mode="before")
    @classmethod
    def _from_user(cls, v):
        if hasattr(v, "email_verified_at"):  # an ORM User
            return {"id": v.id, "email": v.email, "name": v.name, "role": v.role,
                    "email_verified": v.email_verified_at is not None}
        return v


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ----- claims / evidence -----
class EvidenceOut(ORM):
    id: uuid.UUID
    kind: str
    url: str
    quote: str


class ClaimIn(BaseModel):
    field: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=2000)
    year: int | None = Field(default=None, ge=1800, le=2200)


class ClaimOut(ORM):
    id: uuid.UUID
    field: str
    value: str
    year: int | None
    status: str
    confidence: float
    evidence: list[EvidenceOut] = []


# ----- profiles -----
class ProfileIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    headline: str = Field(default="", max_length=300)
    sector: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=80)
    city: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=5000)
    languages: list[str] = []
    institutions: list[str] = []
    photo_url: str = Field(default="", max_length=500)
    custom: dict[str, Any] = {}
    # Explicit opt-in to appear in the public directory (DPDP-style consent record).
    consent_public_listing: bool = False


class ProfilePatch(BaseModel):
    headline: str | None = Field(default=None, max_length=300)
    sector: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=5000)
    languages: list[str] | None = None
    institutions: list[str] | None = None
    photo_url: str | None = Field(default=None, max_length=500)
    custom: dict[str, Any] | None = None


class ProfileOut(ORM):
    id: uuid.UUID
    slug: str
    full_name: str
    headline: str
    sector: str
    state: str
    city: str
    bio: str
    languages: list[str]
    institutions: list[str]
    photo_url: str
    custom: dict[str, Any]
    status: str
    decision_basis: str = ""
    wikidata_qid: str = ""
    is_demo: bool
    created_at: datetime
    claims: list[ClaimOut] = []


class ProfileSummary(ORM):
    id: uuid.UUID
    slug: str
    full_name: str
    headline: str
    sector: str
    state: str
    city: str
    photo_url: str
    status: str


class StatusChangeIn(BaseModel):
    status: Literal["approved", "rejected", "pending_review"]
    note: str = ""


# ----- certificates / verification -----
class CertificateOut(ORM):
    code: str
    profile_id: uuid.UUID | None
    digest: str
    signature: str
    key_id: str
    art_seed: str
    photo_id: str
    issued_at: datetime
    revoked_at: datetime | None
    payload: dict[str, Any]


class VerifyOut(BaseModel):
    valid: bool
    code: str
    reason: str
    revoked: bool = False
    digest: str = ""
    key_id: str = ""
    issued_at: str = ""
    chain_ok: bool = True
    payload: dict[str, Any] | None = None
    changed_fields: list[str] = []
    # Evidence of *how* it was checked, so a viewer can see (and redo) each step.
    signature_ok: bool = False
    signature: str = ""
    public_key: str = ""
    log_position: int | None = None  # 1-based position in the transparency log
    log_size: int = 0
    entry_hash: str = ""


class VerifyCheckIn(BaseModel):
    code: str
    payload: dict[str, Any]


class TransparencyEntry(ORM):
    id: int
    certificate_code: str
    digest: str
    prev_hash: str
    entry_hash: str
    issued_at: str


# ----- api keys -----
class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = ["profiles:read", "verify:read"]
    rate_limit_per_min: int = Field(default=60, ge=1, le=6000)


class ApiKeyOut(ORM):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    rate_limit_per_min: int
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str  # shown exactly once
