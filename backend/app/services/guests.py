"""Guest accounts: let a visitor talk to Saathi before creating an account.

A guest is an ordinary user row whose address is `guest-<random>@guest.invalid` (`.invalid` can never be a real mailbox) and who has no
password, so nobody can log in as one. A guest can build a draft but is never listed, verified or certified: those paths already require a
verified e-mail address (invariant I-5), and `require_verified_email` refuses guests outright. Creating an account (`/v1/auth/upgrade`)
turns the same user into a normal one, so the draft is kept. Guests older than a set number of days, with their drafts, are deleted.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, User

GUEST_DOMAIN = "guest.invalid"


def new_guest_email() -> str:
    return f"guest-{secrets.token_hex(8)}@{GUEST_DOMAIN}"


def is_guest_email(email: str) -> bool:
    return email.lower().endswith(f"@{GUEST_DOMAIN}")


async def purge_stale_guests(session: AsyncSession, days: int = 14) -> int:
    """Delete guests (and the drafts they own) created more than `days` ago. Real accounts are never touched."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    ids = [
        u.id
        for u in (await session.execute(select(User).where(User.created_at < cutoff, User.email.like(f"%@{GUEST_DOMAIN}")))).scalars()
        if is_guest_email(u.email)
    ]
    if not ids:
        return 0
    await session.execute(delete(Profile).where(Profile.owner_id.in_(ids)))
    await session.execute(delete(User).where(User.id.in_(ids)))
    return len(ids)
