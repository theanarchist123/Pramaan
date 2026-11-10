from app.core import ratelimit
from app.core.security import (
    create_access_token,
    create_scoped_token,
    decode_access_token,
    decode_scoped_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    parse_api_key_prefix,
    verify_password,
)


def test_password_roundtrip_and_salting():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert h1 != h2  # unique salts
    assert verify_password("correct horse", h1)
    assert not verify_password("wrong", h1)
    assert not verify_password("x", None)
    assert not verify_password("x", "garbage")


def test_jwt_roundtrip_and_tamper():
    token = create_access_token("user-1", "admin")
    claims = decode_access_token(token)
    assert claims and claims["sub"] == "user-1" and claims["role"] == "admin"
    assert decode_access_token(token + "x") is None


def test_expired_token_rejected():
    assert decode_access_token(create_access_token("u", "person", minutes=-1)) is None


def test_scoped_token_purpose_is_enforced():
    t = create_scoped_token("profile-9", "approve", 10)
    assert decode_scoped_token(t, "approve") == "profile-9"
    assert decode_scoped_token(t, "other") is None
    # a purpose token must not work as a login token elsewhere (checked in deps via 'purpose')
    assert "purpose" in decode_access_token(t)


def test_api_key_format_and_hashing():
    full, prefix, key_hash = generate_api_key()
    assert full.startswith("pk_live_") and prefix in full
    assert parse_api_key_prefix(full) == prefix
    assert hash_api_key(full) == key_hash and len(key_hash) == 64
    assert parse_api_key_prefix("not-a-key") is None


async def test_rate_limit_window():
    ratelimit.reset()
    results = [(await ratelimit.check_rate_limit("k", 3))[0] for _ in range(5)]
    assert results == [True, True, True, False, False]
    assert (await ratelimit.check_rate_limit("other", 3))[0]
