"""Operator command-line tools. They need access to the DATABASE (DATABASE_URL), which is the point: they are the break-glass
path when someone has lost both their authenticator and their recovery codes.

    python -m app.cli reset-mfa --email staff@example.org --reason "Lost phone, identity confirmed by phone call"
    python -m app.cli mfa-status --email staff@example.org
    python -m app.cli seed-images [--dry-run] [--budget 40] [--cache image-seed-cache.json]

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


async def seed_images_command(dry_run: bool, budget: int, cache_path: str) -> dict:
    """Pick and approve a tile and a cover photograph for every field, automatically (see app/services/image_seed.py)."""
    import json
    from pathlib import Path

    from app.services import images as svc
    from app.services.image_seed import seed_images

    cache_file = Path(cache_path)
    cache: dict = json.loads(cache_file.read_text(encoding="utf8")) if cache_file.exists() else {}
    async with get_sessionmaker()() as session:
        try:
            report = await seed_images(session, search=svc.search_candidates, ping=svc._get, budget=budget, dry_run=dry_run, cache=cache)
        except svc.ImagesUnavailable as exc:
            raise SystemExit(f"Cannot reach Unsplash: {exc}. Set UNSPLASH_ACCESS_KEY in .env.") from exc
        if not dry_run:
            await session.commit()
    cache_file.write_text(json.dumps(cache), encoding="utf8")  # searches are reused by the next run, so a trial run costs nothing extra
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset-mfa", help="remove a staff member's authenticator and recovery codes (audited)")
    r.add_argument("--email", required=True)
    r.add_argument("--reason", required=True)
    r.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    st = sub.add_parser("mfa-status", help="show whether someone is enrolled and how many recovery codes remain")
    st.add_argument("--email", required=True)
    si = sub.add_parser("seed-images", help="automatically approve a tile and a cover photograph for every field (hotlinked, never people)")
    si.add_argument("--dry-run", action="store_true", help="choose and show the photos, approve nothing")
    si.add_argument("--budget", type=int, default=40, help="most Unsplash requests to spend this run (a demo key allows 50 an hour)")
    si.add_argument("--cache", default="image-seed-cache.json", help="where searches are remembered between runs")
    args = ap.parse_args(argv)

    async def run() -> dict:
        try:
            if args.cmd == "seed-images":
                return await seed_images_command(args.dry_run, args.budget, args.cache)
            if args.cmd == "mfa-status":
                return await mfa_status(args.email)
            if not args.yes and input(f"Reset MFA for {args.email}? This signs them out. Type 'reset' to continue: ") != "reset":
                raise SystemExit("Cancelled")
            return await reset_mfa(args.email, args.reason)
        finally:
            await dispose_engine()

    result = asyncio.run(run())
    if args.cmd == "seed-images":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # photographers' names are not always ASCII; a console must not crash on them
        for e in result["chosen"] + result["would_approve"]:
            print(f"  {e['sector']:<15} {e['purpose']:<6} by {e['photographer']:<28} {e['alt'][:60]}")
        print({k: v for k, v in result.items() if k not in ("chosen", "would_approve")})
        return 0
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
