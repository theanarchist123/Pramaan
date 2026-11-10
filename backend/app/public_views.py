"""Read-only, approved-data-only views for plugins.

AI-written plugins (Shilpkar) may NOT touch the real tables. They import these classes instead, which map
to SQL views that expose only what the public site already shows:

  * public_profiles      approved profiles that consented to a public listing (no owner, no status, no demo flag)
  * public_claims        claims of those profiles that are verified (self-reported claims are not public)
  * public_evidence      web/document evidence of public claims (chat quotes and uploaded-file hashes are not)
  * public_certificates  non-revoked certificates of those profiles (the signed payload is public by design)

The view definitions live here so `init_db` and the Alembic migration create exactly the same thing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PublicBase(DeclarativeBase):
    """Separate metadata: create_all never tries to make these views into tables."""


VIEW_SQL = [
    """CREATE OR REPLACE VIEW public_profiles AS
       SELECT p.id, p.slug, p.full_name, p.headline, p.sector, p.state, p.city, p.bio,
              p.languages, p.institutions, p.created_at
         FROM profiles p
        WHERE p.status = 'approved'
          AND COALESCE((SELECT c.granted FROM consents c
                         WHERE c.profile_id = p.id AND c.kind = 'public_listing'
                         ORDER BY c.created_at DESC LIMIT 1), false)""",
    """CREATE OR REPLACE VIEW public_claims AS
       SELECT c.id, c.profile_id, c.field, c.value, c.year, c.status, c.confidence
         FROM claims c JOIN public_profiles p ON p.id = c.profile_id
        WHERE c.status IN ('web', 'document') AND c.confidence >= 0.5""",
    """CREATE OR REPLACE VIEW public_evidence AS
       SELECT e.id, e.claim_id, e.kind, e.url, e.quote
         FROM evidence e JOIN public_claims c ON c.id = e.claim_id
        WHERE e.kind IN ('web', 'document')""",
    """CREATE OR REPLACE VIEW public_certificates AS
       SELECT x.id, x.code, x.profile_id, x.issued_at, x.key_id
         FROM certificates x JOIN public_profiles p ON p.id = x.profile_id
        WHERE x.revoked_at IS NULL""",
]


class PublicProfile(PublicBase):
    __tablename__ = "public_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String)
    headline: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    bio: Mapped[str] = mapped_column(Text)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String))
    institutions: Mapped[list[str]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicClaim(PublicBase):
    __tablename__ = "public_claims"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    field: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)


class PublicEvidence(PublicBase):
    __tablename__ = "public_evidence"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    quote: Mapped[str] = mapped_column(Text)


class PublicCertificate(PublicBase):
    __tablename__ = "public_certificates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    key_id: Mapped[str] = mapped_column(String)
