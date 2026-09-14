"""
Password hashing and JWT helpers.

Password hashing is done with the standard library's PBKDF2-HMAC-SHA256
(via `hashlib`) rather than bcrypt/argon2, purely so this project has
zero compiled/native dependencies and installs cleanly everywhere
(including restricted or offline hackathon judging machines). It is
still salted, slow-by-design, and safe for real use — if you want
argon2/bcrypt instead, swap `hash_password` / `verify_password` only,
nothing else in the codebase needs to change.
"""
import datetime
import hashlib
import hmac
import os
import secrets

import jwt

from .config import settings

PBKDF2_ITERATIONS = 260_000


def hash_password(plain_password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt, int(iterations)
    )
    return hmac.compare_digest(candidate, expected)


def create_access_token(subject: str) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the username (subject) encoded in the token, or None if the
    token is missing, malformed, or expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
