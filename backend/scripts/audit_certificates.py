"""Find certificates that print a claim status their evidence does not support (invariant I-8) and optionally revoke them.

    python backend/scripts/audit_certificates.py            # report only (safe: read-only)
    python backend/scripts/audit_certificates.py --revoke   # also revoke the offenders (a public, logged action)

Why: before Phase 0a an admin could set any claim to `document` at 97% with no evidence, and the certificate then
printed it as "Document-verified". This re-checks every active certificate against the evidence that exists now.
A revoked certificate can be re-issued (POST /v1/profiles/{id}/certificate) with only the claims that ARE backed.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.db import dispose_engine, get_sessionmaker  # noqa: E402
from app.models import Certificate, Profile  # noqa: E402
from app.services.certificates import backed_claims  # noqa: E402


async def schema_is_current() -> bool:
    """The script reads the same models as the API, so the database must have the Phase 0a columns (migration 0004)."""
    async with get_sessionmaker()() as session:
        n = (await session.execute(text(
            "SELECT count(*) FROM information_schema.columns WHERE table_name = 'profiles' "
            "AND column_name IN ('decision_basis', 'wikidata_qid')"
        ))).scalar_one()
    return n == 2


async def audit(revoke: bool) -> list[dict]:
    bad = []
    async with get_sessionmaker()() as session:
        certs = (await session.execute(select(Certificate).where(Certificate.revoked_at.is_(None)))).scalars().all()
        for cert in certs:
            profile = await session.get(Profile, cert.profile_id) if cert.profile_id else None
            if profile is None:
                continue
            backed = {(c["field"], c["value"], c["status"]) for c in await backed_claims(session, profile)}
            printed = [(c["field"], c["value"], c["status"]) for c in cert.payload.get("claims", [])]
            unbacked = [c for c in printed if c not in backed]
            if unbacked:
                bad.append({"code": cert.code, "person": cert.payload.get("full_name"), "unbacked": unbacked})
                if revoke:
                    cert.revoked_at = datetime.now(timezone.utc)
        if revoke:
            await session.commit()
    return bad


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revoke", action="store_true")
    args = ap.parse_args()
    if not await schema_is_current():
        await dispose_engine()
        raise SystemExit(
            "This database has not been migrated to the latest schema yet (missing profiles.decision_basis).\n"
            "Apply the migration first (it only ADDS two columns), from the backend folder:\n"
            "    python -m alembic upgrade head\n"
            "or start the API once with AUTO_MIGRATE=true. Then run this script again."
        )
    bad = await audit(args.revoke)
    for b in bad:
        print(f"{b['code']}  {b['person']}")
        for field, value, status in b["unbacked"]:
            print(f"    printed as {status!r} without matching evidence: {value[:70]}")
    print(f"\n{len(bad)} certificate(s) print an unbacked status." + (" Revoked." if args.revoke and bad else ""))
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
