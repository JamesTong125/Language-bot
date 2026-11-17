from datetime import UTC, datetime, timedelta

import jwt

from app.security.passwords import hash_password, verify_password
from app.security.tokens import ALGORITHM, create_access_token, decode_user_id

SECRET = "unit-test-secret-that-is-long-enough-for-hs256"


def test_token_round_trip() -> None:
    token = create_access_token(42, SECRET, expiry_days=1)
    assert decode_user_id(token, SECRET) == 42


def test_token_with_wrong_secret_is_rejected() -> None:
    token = create_access_token(42, SECRET, expiry_days=1)
    assert decode_user_id(token, SECRET + "x") is None


def test_expired_token_is_rejected() -> None:
    past = datetime.now(UTC) - timedelta(days=2)
    token = jwt.encode(
        {"sub": "42", "iat": past, "exp": past + timedelta(days=1)}, SECRET, algorithm=ALGORITHM
    )
    assert decode_user_id(token, SECRET) is None


def test_token_with_none_algorithm_is_rejected() -> None:
    token = jwt.encode({"sub": "42", "exp": datetime.now(UTC) + timedelta(days=1)}, "", "none")
    assert decode_user_id(token, SECRET) is None


def test_password_hash_verifies_and_is_salted() -> None:
    first, second = hash_password("pässwörd-1"), hash_password("pässwörd-1")
    assert first != second
    assert first.startswith("$argon2id$")
    assert verify_password("pässwörd-1", first)
    assert not verify_password("pässwörd-2", first)


def test_verify_against_missing_hash_fails() -> None:
    assert not verify_password("anything", None)
