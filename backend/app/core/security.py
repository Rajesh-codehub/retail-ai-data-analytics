from pwdlib import PasswordHash


from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


password_hash = PasswordHash.recommended()


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


def hash_password(password: str) -> str:
    """Generate a secure password hash."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its stored hash."""
    return password_hash.verify(plain_password, hashed_password)