"""Set a new password for an EXISTING account, from your own terminal. The password is typed at a hidden prompt: it is never an argument, never printed, never logged.

    cd backend
    .venv\\Scripts\\python scripts\\set_password.py you@example.com
    $env:DATABASE_URL = "postgresql+asyncpg://pramaan:pramaan@localhost:5432/pramaan"   # first, to target the LOCAL Docker database instead

It uses the DATABASE_URL from your .env unless the environment already sets one, and tells you which database host it is about to change.
It only changes an account that already exists (it never creates one), and it revokes that account's open sessions.
"""
from __future__ import annotations

import asyncio
import getpass
import sys

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import dispose_engine, get_sessionmaker  # noqa: E402
from app.models import User  # noqa: E402


def db_host() -> str:
    url = get_settings().database_url
    return url.split("@")[-1].split("/")[0] if "@" in url else "(unknown)"


async def main(email: str) -> int:
    email = email.lower().strip()
    Session = get_sessionmaker()
    async with Session() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No account with that email in the database at {db_host()}. (Nothing was changed.)")
            return 1
        print(f"Database: {db_host()}   Account: {user.email} ({user.role})")
        if input("Change this account's password? Type yes: ").strip().lower() != "yes":
            print("Cancelled.")
            return 1
        pw, again = getpass.getpass("New password (8+ characters, hidden): "), getpass.getpass("Again: ")
        if pw != again or not 8 <= len(pw) <= 128:
            print("The two entries differ, or the length is not 8 to 128 characters. Nothing was changed.")
            return 1
        user.password_hash = hash_password(pw)
        # Sign out anywhere this account is logged in (the same switch logout uses).
        if hasattr(user, "tokens_valid_after"):
            from datetime import datetime, timezone

            user.tokens_valid_after = datetime.now(timezone.utc)
        await s.commit()
    print("Done. Sign in with the new password.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    async def run() -> int:
        try:
            return await main(sys.argv[1])
        finally:
            await dispose_engine()

    raise SystemExit(asyncio.run(run()))
