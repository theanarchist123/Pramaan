"""Custom profile fields: the zero-deploy half of "feature on demand".

An admin (or Shilpkar, with an admin's approval) defines a field; from that moment forms, profiles,
the interviewer and search all understand it — no code change, no restart. Values live in
`Profile.custom` and are validated against the definition, never trusted.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FieldDefinition

TYPES = ("text", "number", "date", "select", "url", "list")
# A custom field must never shadow something the platform already means.
RESERVED = {
    "id", "slug", "full_name", "name", "headline", "sector", "state", "city", "bio", "languages",
    "institutions", "photo_url", "custom", "status", "claims", "owner", "email", "password",
    "is_demo", "created_at", "updated_at", "award", "position", "education", "publication",
    "achievement", "membership",
}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
MAX_TEXT, MAX_LIST_ITEMS, MAX_ITEM_LEN, MAX_OPTIONS = 500, 20, 100, 20


class FieldError(ValueError):
    pass


def slugify_key(text: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not key or not key[0].isalpha():
        key = "f_" + key
    return key[:40].rstrip("_")


def validate_definition(key: str, label: str, type_: str, options: list[str]) -> list[str]:
    errors = []
    if not KEY_RE.match(key):
        errors.append("key must be 2-40 chars: lowercase letters, digits, underscores, starting with a letter")
    if key in RESERVED:
        errors.append(f"'{key}' is reserved by the platform")
    if not label.strip() or len(label) > 120:
        errors.append("label is required (max 120 characters)")
    if type_ not in TYPES:
        errors.append(f"type must be one of {', '.join(TYPES)}")
    if type_ == "select" and not (2 <= len(options) <= MAX_OPTIONS):
        errors.append(f"a select field needs 2-{MAX_OPTIONS} options")
    if type_ != "select" and options:
        errors.append("only select fields take options")
    return errors


def _clean_one(d: FieldDefinition, value: Any) -> Any:
    """Return the normalised value or raise FieldError. Empty values mean 'clear this field'."""
    if value in (None, "", []):
        return None
    t = d.type
    if t == "text":
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            raise FieldError(f"{d.label}: text up to {MAX_TEXT} characters")
        return value.strip()
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise FieldError(f"{d.label}: must be a number")
        try:
            n = float(value)
        except ValueError as exc:
            raise FieldError(f"{d.label}: must be a number") from exc
        if n != n or n in (float("inf"), float("-inf")):
            raise FieldError(f"{d.label}: must be a finite number")
        return int(n) if n.is_integer() else n
    if t == "date":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise FieldError(f"{d.label}: use YYYY-MM-DD") from exc
    if t == "select":
        if value not in d.options:
            raise FieldError(f"{d.label}: choose one of {', '.join(d.options)}")
        return value
    if t == "url":
        if not isinstance(value, str) or not re.match(r"^https?://[^\s]+$", value) or len(value) > 500:
            raise FieldError(f"{d.label}: must be an http(s) link")
        return value
    if t == "list":
        if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
            raise FieldError(f"{d.label}: a list of up to {MAX_LIST_ITEMS} items")
        items = [str(i).strip() for i in value if str(i).strip()]
        if any(len(i) > MAX_ITEM_LEN for i in items):
            raise FieldError(f"{d.label}: each item up to {MAX_ITEM_LEN} characters")
        return items or None
    raise FieldError(f"{d.label}: unsupported type")  # pragma: no cover


def clean_values(values: dict[str, Any], defs: list[FieldDefinition], *, strict: bool) -> dict[str, Any]:
    """strict (API input): unknown keys and bad values raise. lenient (AI output): bad ones are dropped."""
    by_key = {d.key: d for d in defs if d.active}
    out: dict[str, Any] = {}
    for key, raw in values.items():
        d = by_key.get(key)
        if d is None:
            if strict:
                raise FieldError(f"Unknown field '{key}'")
            continue
        try:
            cleaned = _clean_one(d, raw)
        except FieldError:
            if strict:
                raise
            continue
        if cleaned is not None:
            out[key] = cleaned
    return out


async def active_definitions(session: AsyncSession) -> list[FieldDefinition]:
    rows = await session.execute(
        select(FieldDefinition).where(FieldDefinition.active.is_(True)).order_by(FieldDefinition.created_at)
    )
    return list(rows.scalars().all())


def merge_custom(existing: dict[str, Any], incoming: dict[str, Any], defs: list[FieldDefinition]) -> dict[str, Any]:
    """Apply a patch: values of fields that are no longer active are preserved untouched."""
    merged = {**existing, **incoming}
    return {k: v for k, v in merged.items() if v is not None}
