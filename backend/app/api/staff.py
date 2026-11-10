"""Staff administration: roles, four-eyes approvals and the audit log (spec 7.2, 7.6, 7.9).

Four-eyes actions never run on one person's say-so: the first person files an approval request, a DIFFERENT person who
also holds the permission approves it, and only then does the action execute. Both identities land in the audit log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import ACTION_PERMISSION, ROLE_PERMISSIONS, permissions_for_user, staff_roles
from app.db import get_session
from app.deps import Principal, get_principal, require_admin, require_permission, require_stepup
from app.models import ApprovalRequest, Certificate, User, UserRole
from app.services import audit

router = APIRouter(prefix="/v1/admin", tags=["staff"])
APPROVAL_HOURS = 72


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


async def _actor_role(session: AsyncSession, principal: Principal) -> str:
    roles = await staff_roles(session, principal.user.id)
    return ",".join(sorted(roles)) or ("legacy_admin" if principal.is_admin else "")


@router.get("/me/permissions")
async def my_permissions(principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return {"roles": sorted(await staff_roles(session, principal.user.id)), "legacy_admin": principal.is_admin,
            "permissions": sorted(await permissions_for_user(session, principal.user))}


# ------------------------------------------------------------------------------------------------ roles
@router.get("/staff")
async def list_staff(_: Principal = Depends(require_permission("role.read")), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(UserRole))).scalars().all()
    by_user: dict[uuid.UUID, list[str]] = {}
    for r in rows:
        by_user.setdefault(r.user_id, []).append(r.role_key)
    users = (await session.execute(select(User).where((User.id.in_(by_user)) | (User.role == "admin")))).scalars().all()
    return [{"id": str(u.id), "email": u.email, "name": u.name, "legacy_admin": u.role == "admin",
             "roles": sorted(by_user.get(u.id, []))} for u in users]


class RoleIn(BaseModel):
    role: str
    reason: str = Field(min_length=10, max_length=500)


@router.post("/staff/{user_id}/roles", status_code=status.HTTP_202_ACCEPTED)
async def request_role(
    user_id: uuid.UUID, body: RoleIn, request: Request,
    principal: Principal = Depends(require_permission("role.assign")), session: AsyncSession = Depends(get_session),
):
    """Granting a role is a four-eyes action: this files the request; a second person approves it."""
    require_stepup(principal)
    if body.role not in ROLE_PERMISSIONS:
        raise HTTPException(422, f"Unknown role. Choose one of: {', '.join(sorted(ROLE_PERMISSIONS))}")
    if await session.get(User, user_id) is None:
        raise HTTPException(404, "User not found")
    return await _file(session, principal, request, "role.assign", {"user_id": str(user_id), "role": body.role}, body.reason)


# ------------------------------------------------------------------------------------------------ certificate revocation
class RevokeIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


@router.post("/certificates/{code}/revoke", status_code=status.HTTP_202_ACCEPTED)
async def request_revocation(
    code: str, body: RevokeIn, request: Request,
    principal: Principal = Depends(require_permission("certificate.revoke")), session: AsyncSession = Depends(get_session),
):
    """Revoking a certificate is public and permanent for that code, so it needs two people."""
    require_stepup(principal)
    cert = (await session.execute(select(Certificate).where(Certificate.code == code))).scalar_one_or_none()
    if cert is None:
        raise HTTPException(404, "Certificate not found")
    if cert.revoked_at is not None:
        raise HTTPException(409, "Already revoked")
    return await _file(session, principal, request, "certificate.revoke", {"code": code}, body.reason)


# ------------------------------------------------------------------------------------------------ approvals
async def _file(session, principal, request, action: str, payload: dict, reason: str) -> dict:
    row = ApprovalRequest(action=action, payload=payload, reason=reason, requested_by=principal.user.id,
                          expires_at=datetime.now(timezone.utc) + timedelta(hours=APPROVAL_HOURS))
    session.add(row)
    await session.flush()
    await audit.record(session, actor_id=principal.user.id, actor_role=await _actor_role(session, principal),
                       action=f"{action}.requested", target_type="approval", target_id=str(row.id), after=payload,
                       reason=reason, ip=_ip(request))
    await session.commit()
    return {"approval_id": str(row.id), "status": "pending", "needs": "a second authorised person"}


def _out(a: ApprovalRequest) -> dict:
    return {"id": str(a.id), "action": a.action, "payload": a.payload, "reason": a.reason, "status": a.status,
            "requested_by": str(a.requested_by), "decided_by": str(a.decided_by) if a.decided_by else None,
            "created_at": a.created_at, "expires_at": a.expires_at, "executed_at": a.executed_at}


@router.get("/approvals")
async def list_approvals(status_filter: str | None = None, _: Principal = Depends(require_permission("approval.read")),
                         session: AsyncSession = Depends(get_session)):
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).limit(100)
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    return [_out(a) for a in (await session.execute(stmt)).scalars().all()]


class DecideIn(BaseModel):
    note: str = Field(default="", max_length=500)


async def _load_decidable(session, approval_id: uuid.UUID, principal: Principal) -> ApprovalRequest:
    a = await session.get(ApprovalRequest, approval_id)
    if a is None:
        raise HTTPException(404, "Approval request not found")
    if a.status != "pending":
        raise HTTPException(409, f"Already {a.status}")
    if a.expires_at < datetime.now(timezone.utc):
        a.status = "expired"
        await session.commit()
        raise HTTPException(409, "This request has expired")
    if a.requested_by == principal.user.id:
        raise HTTPException(403, "A second person must decide: you cannot approve your own request")
    needed = ACTION_PERMISSION[a.action]
    if needed not in await permissions_for_user(session, principal.user):
        raise HTTPException(403, f"Your role does not allow deciding this ({needed})")
    return a


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal),
                  session: AsyncSession = Depends(get_session)):
    if principal.via != "jwt":
        raise HTTPException(403, "Staff session required")
    require_stepup(principal)
    a = await _load_decidable(session, approval_id, principal)
    result = await _execute(session, a)
    a.status, a.decided_by = "approved", principal.user.id
    a.decided_at = a.executed_at = datetime.now(timezone.utc)
    await audit.record(session, actor_id=principal.user.id, actor_role=await _actor_role(session, principal),
                       action=f"{a.action}.approved", target_type="approval", target_id=str(a.id),
                       before={"requested_by": str(a.requested_by)}, after=result, reason=a.reason, ip=_ip(request))
    await session.commit()
    return _out(a)


@router.post("/approvals/{approval_id}/reject")
async def reject(approval_id: uuid.UUID, body: DecideIn, request: Request, principal: Principal = Depends(get_principal),
                 session: AsyncSession = Depends(get_session)):
    if principal.via != "jwt":
        raise HTTPException(403, "Staff session required")
    require_stepup(principal)
    a = await _load_decidable(session, approval_id, principal)
    a.status, a.decided_by, a.decided_at = "rejected", principal.user.id, datetime.now(timezone.utc)
    await audit.record(session, actor_id=principal.user.id, actor_role=await _actor_role(session, principal),
                       action=f"{a.action}.rejected", target_type="approval", target_id=str(a.id), reason=body.note, ip=_ip(request))
    await session.commit()
    return _out(a)


async def _execute(session: AsyncSession, a: ApprovalRequest) -> dict:
    """Run the approved action. Each executor re-checks its own preconditions: the world may have changed."""
    if a.action == "role.assign":
        uid, role = uuid.UUID(a.payload["user_id"]), a.payload["role"]
        if (await session.get(UserRole, (uid, role))) is None:
            session.add(UserRole(user_id=uid, role_key=role, granted_by=a.requested_by))
        return {"user_id": str(uid), "granted": role}
    if a.action == "certificate.revoke":
        cert = (await session.execute(select(Certificate).where(Certificate.code == a.payload["code"]))).scalar_one_or_none()
        if cert is None:
            raise HTTPException(409, "Certificate no longer exists")
        if cert.revoked_at is None:
            cert.revoked_at = datetime.now(timezone.utc)
        return {"code": cert.code, "revoked": True}
    if a.action == "setting.change":
        from app.models import GovernedSetting, GovernedSettingChange
        from app.services import governed

        key = a.payload["key"]
        try:
            new = governed.validate(key, a.payload["value"])  # re-validated: the floor holds whatever was approved
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        row = await session.get(GovernedSetting, key)
        old = row.value["v"] if row else governed.GOVERNED[key].default()
        if row is None:
            session.add(GovernedSetting(key=key, value={"v": new}, version=1, updated_by=a.requested_by))
        else:
            row.value, row.version, row.updated_by = {"v": new}, row.version + 1, a.requested_by
        session.add(GovernedSettingChange(key=key, old={"v": old}, new={"v": new}, approval_request_id=a.id,
                                          changed_by=a.requested_by))
        governed.clear_cache()
        return {"key": key, "old": old, "new": new}
    raise HTTPException(500, "Unknown approval action")


# ------------------------------------------------------------------------------------------------ governed settings
@router.get("/settings")
async def list_settings(_: Principal = Depends(require_permission("approval.read")), session: AsyncSession = Depends(get_session)):
    from app.services import governed

    return await governed.snapshot(session)


class SettingIn(BaseModel):
    value: bool | float
    reason: str = Field(min_length=10, max_length=500)


@router.post("/settings/{key}", status_code=status.HTTP_202_ACCEPTED)
async def propose_setting(
    key: str, body: SettingIn, request: Request,
    principal: Principal = Depends(require_permission("settings.write")), session: AsyncSession = Depends(get_session),
):
    """Safety switches change only through a four-eyes approval (and with a fresh MFA code)."""
    from app.services import governed

    require_stepup(principal)
    try:
        value = governed.validate(key, body.value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await _file(session, principal, request, "setting.change", {"key": key, "value": value}, body.reason)


# ------------------------------------------------------------------------------------------------ PII reveal
class RevealIn(BaseModel):
    profile_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)


@router.post("/pii/reveal")
async def reveal_owner_contact(
    body: RevealIn, request: Request,
    principal: Principal = Depends(require_permission("pii.reveal")), session: AsyncSession = Depends(get_session),
):
    """Staff screens mask contact details by default. Revealing one needs a reason, a fresh MFA code, and is logged."""
    from app.core.ratelimit import check_rate_limit
    from app.models import Profile

    require_stepup(principal)
    ok, _ = await check_rate_limit(f"pii:{principal.user.id}", 20)
    if not ok:
        raise HTTPException(429, "Too many reveals; try again later")
    profile = await session.get(Profile, body.profile_id)
    if profile is None or profile.owner_id is None:
        raise HTTPException(404, "No owner on record for that profile")
    owner = await session.get(User, profile.owner_id)
    await audit.record(session, actor_id=principal.user.id, actor_role=await _actor_role(session, principal),
                       action="pii.reveal", target_type="profile", target_id=str(profile.id), reason=body.reason,
                       ip=_ip(request))
    await session.commit()
    return {"profile_id": str(profile.id), "email": owner.email}


# ------------------------------------------------------------------------------------------------ audit log
@router.get("/audit")
async def audit_log(limit: int = 100, action: str | None = None, _: Principal = Depends(require_permission("audit.read")),
                    session: AsyncSession = Depends(get_session)):
    from app.models import AdminAuditLog

    stmt = select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(min(max(limit, 1), 500))
    if action:
        stmt = stmt.where(AdminAuditLog.action == action)
    return [{"id": r.id, "at": r.at_iso, "actor_id": str(r.actor_id) if r.actor_id else None, "actor_role": r.actor_role,
             "action": r.action, "target_type": r.target_type, "target_id": r.target_id, "before": r.before,
             "after": r.after, "reason": r.reason, "entry_hash": r.entry_hash}
            for r in (await session.execute(stmt)).scalars().all()]


@router.get("/audit/verify")
async def audit_verify(_: Principal = Depends(require_permission("audit.read")), session: AsyncSession = Depends(get_session)):
    ok, bad_id, n = await audit.verify_chain(session)
    return {"valid": ok, "first_bad_entry": bad_id, "entries": n}
