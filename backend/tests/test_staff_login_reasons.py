"""The staff sign-in tells the PUBLIC one thing ("Incorrect email or password") for every failure, so the form cannot be used to find out who is staff.
The OPERATOR must still be able to tell why a sign-in failed, or a wrong password looks exactly like a broken deployment. So the server logs the specific reason,
with the email masked and never the password; and scripts/staff_doctor.py explains it from the database."""
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from app.api.admin_auth import mask_email

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import staff_doctor  # noqa: E402

SECRET = "correct-horse-battery-9"


def test_mask_email_keeps_enough_to_recognise_but_not_the_address():
    assert mask_email("nikhilrkadam2005@gmail.com") == "ni***@gmail.com"
    assert mask_email("a@b.co") == "a***@b.co"
    assert mask_email("not-an-email") == "***"


async def _staff(client, make_user):
    import uuid

    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import User

    _, me = await make_user()
    async with get_sessionmaker()() as s:
        from app.core.security import hash_password

        await s.execute(update(User).where(User.id == uuid.UUID(me["id"])).values(role="admin", password_hash=hash_password(SECRET)))
        await s.commit()
    return me["email"]


async def test_each_failure_is_logged_with_its_real_reason_and_never_the_password(client, make_user, caplog):
    email = await _staff(client, make_user)
    _, member = await make_user()
    caplog.set_level(logging.WARNING, logger="pramaan.staff_auth")
    cases = [
        ({"email": "nobody-here@example.com", "password": "whatever-123"}, "no account"),
        ({"email": email, "password": "wrong-password-1"}, "wrong password"),
        ({"email": member["email"], "password": "password123"}, "not staff"),
    ]
    for body, reason in cases:
        caplog.clear()
        r = await client.post("/v1/admin/auth/login", json=body)
        assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password"  # the public answer is the same for all three
        text = " ".join(rec.getMessage() for rec in caplog.records)
        assert reason in text, (reason, text)
        assert body["password"] not in text and body["email"] not in text  # never the password, never the full address
    ok = await client.post("/v1/admin/auth/login", json={"email": email, "password": SECRET})
    assert ok.status_code == 200


def test_the_doctor_names_the_reason():
    assert "No account" in staff_doctor.diagnose(None, set(), None)[0]
    staff = SimpleNamespace(role="admin", password_hash="scrypt$x$y")
    assert staff_doctor.diagnose(staff, set(), True) == []
    assert "does not match" in staff_doctor.diagnose(staff, set(), False)[0]
    member = SimpleNamespace(role="person", password_hash="scrypt$x$y")
    assert "not staff" in staff_doctor.diagnose(member, set(), None)[0]
    assert staff_doctor.diagnose(member, {"reviewer"}, None) == []
    assert "no password" in staff_doctor.diagnose(SimpleNamespace(role="admin", password_hash=None), set(), None)[0]
