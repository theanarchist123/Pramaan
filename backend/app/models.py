"""All Pramaan tables in one place (see build plan: Data model)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBED_DIM = 384  # multilingual-e5-small


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)


def ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=_now)


# --------------------------------------------------------------------------- #
# Identity + access
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(16), default="person")  # person|delegate|admin
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = ts()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = ts()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    events: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    secret: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = ts()


class WebhookDelivery(Base):
    """One HTTP attempt to a subscriber, kept so developers can debug their endpoint."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = pk()
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    delivery_id: Mapped[str] = mapped_column(String(40), index=True)  # same across retries
    event: Mapped[str] = mapped_column(String(60))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(String(300), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = ts()


# --------------------------------------------------------------------------- #
# Registry core
# --------------------------------------------------------------------------- #
class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    headline: Mapped[str] = mapped_column(String(300), default="")
    sector: Mapped[str] = mapped_column(String(80), default="", index=True)
    state: Mapped[str] = mapped_column(String(80), default="", index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    institutions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    custom: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # draft | pending_review | approved | rejected
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = ts()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    claims: Mapped[list[Claim]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class Claim(Base):
    """One fact about a person, with its own verification status and evidence trail."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(60))  # award, position, education, publication...
    value: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="self")  # self|web|document
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = ts()

    profile: Mapped[Profile] = relationship(back_populates="claims")
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", lazy="selectin"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(12))  # chat|web|document
    url: Mapped[str] = mapped_column(String(600), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = ts()

    claim: Mapped[Claim] = relationship(back_populates="evidence")


class ChatMessage(Base):
    """Onboarding conversation with Saathi, kept so the interview can resume anywhere."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(12))  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = ts()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    path: Mapped[str] = mapped_column(String(500))
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = ts()


# --------------------------------------------------------------------------- #
# Certificates + transparency
# --------------------------------------------------------------------------- #
class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)  # public id in QR
    # SET NULL (not CASCADE): erasing a profile revokes + redacts its certificates but keeps
    # the row, so a scan reports "revoked" instead of "never existed".
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(200))
    key_id: Mapped[str] = mapped_column(String(32))
    art_seed: Mapped[str] = mapped_column(String(64))
    photo_id: Mapped[str] = mapped_column(String(80), default="")
    issued_at: Mapped[datetime] = ts()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransparencyLog(Base):
    __tablename__ = "transparency_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    certificate_code: Mapped[str] = mapped_column(String(24), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[str] = mapped_column(String(32))


# --------------------------------------------------------------------------- #
# Network + search
# --------------------------------------------------------------------------- #
class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (UniqueConstraint("a_id", "b_id", "type", name="uq_edge"),)

    id: Mapped[uuid.UUID] = pk()
    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # alumni|org|sector|city|collab
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str] = mapped_column(Text, default="")


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[Any] = mapped_column(Vector(EMBED_DIM))
    text_hash: Mapped[str] = mapped_column(String(64), default="")


# --------------------------------------------------------------------------- #
# Governance + agents
# --------------------------------------------------------------------------- #
class ReviewItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[uuid.UUID] = pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(300))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)  # open|approved|rejected
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = pk()
    workflow: Mapped[str] = mapped_column(String(60))
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(12), default="running")  # running|done|failed
    summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = ts()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))  # thought|tool|result|handoff|error
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = ts()


class FieldDefinition(Base):
    """Admin/agent-defined fields: the zero-deploy path of feature-on-demand."""

    __tablename__ = "field_definitions"

    id: Mapped[uuid.UUID] = pk()
    key: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="text")  # text|number|date|select|url|list
    options: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    help_text: Mapped[str] = mapped_column(String(300), default="")
    searchable: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(60), default="admin")
    created_at: Mapped[datetime] = ts()


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))  # public_listing|web_research|outreach
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = ts()


class OutboxMessage(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = pk()
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), default="custom")  # welcome_share|needs_document|finish_profile
    to_email: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str] = mapped_column(String(300), default="")
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|scheduled|sent|discarded
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = ts()


class CodeChange(Base):
    """An AI-written plugin proposed by Shilpkar. It only ever goes live after passing the code guard,
    the sandbox checks, and a human clicking approve."""

    __tablename__ = "code_changes"

    id: Mapped[uuid.UUID] = pk()
    request: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    files: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # {"plugins/x.py": "<source>"}
    # proposed | rejected_by_guard | checks_failed | ready | applied | rejected
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = ts()
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
