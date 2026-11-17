"""JWT creation and decoding."""

from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"


def create_access_token(user_id: int, secret: str, expiry_days: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=expiry_days),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_user_id(token: str, secret: str) -> int | None:
    """Return the user id in a valid token, or None if the token is invalid or expired."""
    try:
        payload = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
