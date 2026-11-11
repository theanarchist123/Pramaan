"""Operator command-line tools. They need access to the DATABASE (DATABASE_URL), which is the point: they are the break-glass
path when someone has lost both their authenticator and their recovery codes.

    python -m app.cli reset-mfa --email staff@example.org --reason "Lost phone, identity confirmed by phone call"
    python -m app.cli mfa-status --email staff@example.org

`reset-mfa` removes the authenticator and every recovery code, ends all of the person's sessions, and writes an entry to the
tamper-evident admin audit log naming the operating-system user who ran it. The person must then enrol again.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app.db import dispose_engine, get_sessionmaker
from app.models import MfaRecoveryCode, User
from app.services import audit


async def find_user(session, email: str) -> User | None:
    return (await session.execute(select(User).where(User.email == email.lower().strip()))).scalar_one_or_none()


async def mfa_status(email: str) -> dict:
    async with get_sessionmaker()() as s:
        user = await find_user(s, email)
        if user is None:
            raise SystemExit(f"No user with email {email}")
        left = (await s.execute(select(func.count()).select_from(MfaRecoveryCode)
                                .where(MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.used_at.is_(None)))).scalar_one()
        return {"email": user.email, "enrolled": user.mfa_enrolled_at is not None, "recovery_codes_left": left}


async def reset_mfa(email: str, reason: str, operator: str | None = None) -> dict:
    if len(reason.strip()) < 10:
        raise SystemExit("Give a reason of at least 10 characters (it goes into the audit log)")
    operator = operator or getpass.getuser()
    async with get_sessionmaker()() as s:
        user = await find_user(s, email)
        if user is None:
            raise SystemExit(f"No user with email {email}")
        before = {"enrolled": user.mfa_enrolled_at is not None}
        user.totp_secret_enc = None
        user.mfa_enrolled_at = None
        user.stepup_until = None
        user.tokens_valid_after = datetime.now(timezone.utc)  # signs out every session
        await s.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
        await audit.record(s, actor_id=None, actor_role=f"cli:{operator}", action="mfa.reset", target_type="user",
                           target_id=str(user.id), before=before, after={"enrolled": False}, reason=reason)
        await s.commit()
        return {"email": user.email, "reset": True, "operator": operator}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset-mfa", help="remove a staff member's authenticator and recovery codes (audited)")
    r.add_argument("--email", required=True)
    r.add_argument("--reason", required=True)
    r.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    st = sub.add_parser("mfa-status", help="show whether someone is enrolled and how many recovery codes remain")
    st.add_argument("--email", required=True)
    args = ap.parse_args(argv)

    async def run() -> dict:
        try:
            if args.cmd == "mfa-status":
                return await mfa_status(args.email)
            if not args.yes and input(f"Reset MFA for {args.email}? This signs them out. Type 'reset' to continue: ") != "reset":
                raise SystemExit("Cancelled")
            return await reset_mfa(args.email, args.reason)
        finally:
            await dispose_engine()

    print(asyncio.run(run()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
