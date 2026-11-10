"""The admin audit log: every staff action, hash-chained and append-only (spec 7.9).

Each entry stores prev_hash and entry_hash = sha256(prev_hash | canonical JSON of the entry), the same idea as the public
transparency log. A database trigger refuses UPDATE and DELETE, so history cannot be quietly edited even by the app
itself; `verify_chain` recomputes every link and reports the first broken one.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.signing import GENESIS_HASH, canonical_json
from app.models import AdminAuditLog

_CHAIN_LOCK_ID = 7002  # distinct from the certificate log's lock

TRIGGER_SQL = [
    """CREATE OR REPLACE FUNCTION admin_audit_log_immutable() RETURNS trigger AS $$
       BEGIN RAISE EXCEPTION 'admin_audit_log is append-only'; END; $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS admin_audit_log_no_change ON admin_audit_log",
    """CREATE TRIGGER admin_audit_log_no_change BEFORE UPDATE OR DELETE ON admin_audit_log
       FOR EACH ROW EXECUTE FUNCTION admin_audit_log_immutable()""",
]


def _entry_hash(prev: str, body: dict[str, Any]) -> str:
    return hashlib.sha256(prev.encode() + b"|" + canonical_json(body)).hexdigest()


def _body(at: str, actor_id: str | None, actor_role: str, action: str, target_type: str, target_id: str,
          before: Any, after: Any, reason: str, ip: str, request_id: str) -> dict[str, Any]:
    return {"at": at, "actor_id": actor_id, "actor_role": actor_role, "action": action, "target_type": target_type,
            "target_id": target_id, "before": before, "after": after, "reason": reason, "ip": ip, "request_id": request_id}


async def record(
    session: AsyncSession, *, actor_id, actor_role: str, action: str, target_type: str = "", target_id: str = "",
    before: Any = None, after: Any = None, reason: str = "", ip: str = "", request_id: str = "",
) -> AdminAuditLog:
    """Append one entry. Call inside the same transaction as the action it describes, so they commit together."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_ID})  # serialise: the chain cannot fork
    last = (await session.execute(select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(1))).scalar_one_or_none()
    prev = last.entry_hash if last else GENESIS_HASH
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    aid = str(actor_id) if actor_id else None
    body = _body(at, aid, actor_role, action, target_type, target_id, before, after, reason, ip, request_id)
    row = AdminAuditLog(at_iso=at, actor_id=actor_id, actor_role=actor_role, action=action, target_type=target_type,
                        target_id=target_id, before=before, after=after, reason=reason, ip=ip, request_id=request_id,
                        prev_hash=prev, entry_hash=_entry_hash(prev, body))
    session.add(row)
    await session.flush()
    return row


async def verify_chain(session: AsyncSession) -> tuple[bool, int | None, int]:
    """-> (ok, id of the first bad entry, entries checked)."""
    rows = (await session.execute(select(AdminAuditLog).order_by(AdminAuditLog.id))).scalars().all()
    prev = GENESIS_HASH
    for r in rows:
        body = _body(r.at_iso, str(r.actor_id) if r.actor_id else None, r.actor_role, r.action, r.target_type, r.target_id,
                     r.before, r.after, r.reason, r.ip, r.request_id)
        if r.prev_hash != prev or _entry_hash(prev, body) != r.entry_hash:
            return False, r.id, len(rows)
        prev = r.entry_hash
    return True, None, len(rows)
