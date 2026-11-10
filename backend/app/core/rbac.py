"""Staff roles and permissions (spec 7.2). Roles are bundles of fine-grained permission strings.

Rules that are enforced in code, not just documented:
  * least privilege: a staff member has exactly the permissions of the roles granted to them;
  * the legacy `users.role == "admin"` keeps every permission, so existing deployments do not lose access
    (grant real roles, then demote the legacy admins);
  * separation of duties lives in the callers: nobody reviews their own profile (I-10), and a four-eyes action
    needs a second person (services/approvals.py).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

REVIEWER = {"review.read", "review.claim", "review.decide", "review.request_info"}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "reviewer": set(REVIEWER),
    "senior_verifier": REVIEWER | {"review.decide_high_risk", "appeal.decide", "claim.override"},
    "registry_manager": {"review.read", "profile.suspend", "profile.merge", "profile.correct", "takedown.process", "certificate.revoke"},
    "builder_approver": {"plugin.review", "plugin.approve", "plugin.disable", "field.publish"},
    "outreach_manager": {"outreach.template.write", "outreach.approve", "outreach.send", "suppression.manage"},
    "compliance": {"dsr.process", "consent.read", "grievance.handle", "retention.manage", "pii.reveal", "audit.read"},
    "auditor": {"audit.read", "agent_run.read", "review.read", "role.read", "approval.read", "consent.read"},
    "super_admin": {"role.assign", "role.read", "settings.write", "key.rotate", "flag.write", "audit.read", "agent_run.read",
                    "approval.read", "images.curate"},
}
ALL_PERMISSIONS: set[str] = set().union(*ROLE_PERMISSIONS.values())

# Four-eyes actions: the permission both the requester and the approver need.
ACTION_PERMISSION = {"certificate.revoke": "certificate.revoke", "role.assign": "role.assign"}


async def staff_roles(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    from app.models import UserRole

    return set((await session.execute(select(UserRole.role_key).where(UserRole.user_id == user_id))).scalars().all())


def permissions_of(roles: set[str], *, legacy_admin: bool = False) -> set[str]:
    if legacy_admin:
        return set(ALL_PERMISSIONS)
    out: set[str] = set()
    for r in roles:
        out |= ROLE_PERMISSIONS.get(r, set())
    return out


async def permissions_for_user(session: AsyncSession, user) -> set[str]:
    return permissions_of(await staff_roles(session, user.id), legacy_admin=user.role == "admin")
