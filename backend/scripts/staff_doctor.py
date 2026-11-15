"""Why can't this person sign in to the staff console? Read-only unless you pass --grant.

    cd backend
    .venv\\Scripts\\python scripts\\staff_doctor.py --list                 # every account that can use the staff console
    .venv\\Scripts\\python scripts\\staff_doctor.py you@example.com        # check one account; asks for the password at a hidden prompt (optional)
    .venv\\Scripts\\python scripts\\staff_doctor.py you@example.com --grant super_admin   # give that account a staff role (asks to confirm)

The staff sign-in answers "Incorrect email or password" for three different problems on purpose (so the form cannot be used to find out who is staff).
This tool, run by someone who already has the database, tells you which one it is: the account is missing, the password is wrong, or the account holds no
staff role. It uses the DATABASE_URL your .env sets (or the environment's), and prints which database host it is looking at.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.rbac import ROLE_PERMISSIONS, staff_roles  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.db import dispose_engine, get_sessionmaker  # noqa: E402
from app.models import User, UserRole  # noqa: E402


def db_host() -> str:
    url = get_settings().database_url
    return url.split("@")[-1].split("?")[0] if "@" in url else "(unknown)"


def diagnose(user, roles: set[str], password_ok: bool | None) -> list[str]:
    """Plain reasons this account cannot sign in to the staff console (empty = it can, after the authenticator step if enrolled). Pure, so it is tested."""
    if user is None:
        return ["No account with this email exists in this database. Register on the member site first (or check you are looking at the right database)."]
    out = []
    if not user.password_hash:
        out.append("This account has no password (it was created as a guest or without one). Set one with scripts/set_password.py.")
    elif password_ok is False:
        out.append("The password you typed does not match this account. Reset it with scripts/set_password.py.")
    if user.role != "admin" and not roles:
        out.append("The account exists but is not staff: it has no staff role. Give it one with --grant super_admin (or reviewer, auditor...).")
    return out


async def list_staff() -> int:
    async with get_sessionmaker()() as s:
        role_rows = (await s.execute(select(UserRole.user_id, func.array_agg(UserRole.role_key)).group_by(UserRole.user_id))).all()
        by_user = {uid: set(r) for uid, r in role_rows}
        users = (await s.execute(select(User).where((User.role == "admin") | (User.id.in_(list(by_user)))))).scalars().all()
    print(f"Database: {db_host()}")
    if not users:
        print("No account can use the staff console. Give one a role: staff_doctor.py you@example.com --grant super_admin")
        return 1
    for u in sorted(users, key=lambda x: x.email):
        roles = sorted(by_user.get(u.id, set())) + (["legacy admin"] if u.role == "admin" else [])
        print(f"  {u.email:<40} roles: {', '.join(roles):<30} password: {'set' if u.password_hash else 'NONE'}   authenticator: {'yes' if u.mfa_enrolled_at else 'no'}")
    return 0


async def check(email: str, ask_password: bool) -> int:
    email = email.lower().strip()
    async with get_sessionmaker()() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        roles = await staff_roles(s, user.id) if user else set()
    print(f"Database: {db_host()}   Account: {email}")
    password_ok = None
    if user is not None and user.password_hash and ask_password:
        typed = getpass.getpass("Password to test (hidden, optional: press Enter to skip): ")
        password_ok = verify_password(typed, user.password_hash) if typed else None
    problems = diagnose(user, roles, password_ok)
    if user is not None:
        print(f"  member role: {user.role}   staff roles: {', '.join(sorted(roles)) or 'none'}   authenticator: {'enrolled' if user.mfa_enrolled_at else 'not enrolled'}")
    if problems:
        print("Cannot sign in to the staff console:")
        for p in problems:
            print("  -", p)
        return 1
    print("This account can sign in to the staff console" + (" (it will ask for the authenticator code)." if user.mfa_enrolled_at else "."))
    if password_ok is None and user.password_hash:
        print("  (password not tested: run again and type it at the prompt to check it.)")
    return 0


async def grant(email: str, role: str) -> int:
    if role not in ROLE_PERMISSIONS:
        print(f"Unknown role {role!r}. Choose one of: {', '.join(sorted(ROLE_PERMISSIONS))}")
        return 2
    email = email.lower().strip()
    async with get_sessionmaker()() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No account with that email in the database at {db_host()}. Register on the member site first. (Nothing was changed.)")
            return 1
        if role in await staff_roles(s, user.id):
            print(f"{email} already holds {role}. Nothing to do.")
            return 0
        print(f"Database: {db_host()}   Account: {email}")
        if input(f"Give this account the staff role '{role}'? Type yes: ").strip().lower() != "yes":
            print("Cancelled.")
            return 1
        s.add(UserRole(user_id=user.id, role_key=role))
        try:
            from app.services import audit

            await audit.record(s, actor_id=None, actor_role="operator-cli", action="role.grant", target_type="user", target_id=str(user.id),
                               after={"role": role}, reason="granted with scripts/staff_doctor.py", ip="")
        except Exception:  # noqa: BLE001 - the grant itself must not depend on the audit helper's signature
            pass
        await s.commit()
    print(f"Done. {email} can now sign in to the staff console (it will be asked to set up an authenticator).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("email", nargs="?")
    ap.add_argument("--list", action="store_true", help="list every account that can use the staff console")
    ap.add_argument("--grant", metavar="ROLE", help="give the account a staff role (super_admin, reviewer, auditor, ...)")
    ap.add_argument("--no-password", action="store_true", help="do not prompt for a password to test")
    a = ap.parse_args()

    async def run() -> int:
        try:
            if a.list:
                return await list_staff()
            if not a.email:
                ap.print_help()
                return 2
            if a.grant:
                return await grant(a.email, a.grant)
            return await check(a.email, not a.no_password)
        finally:
            await dispose_engine()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
