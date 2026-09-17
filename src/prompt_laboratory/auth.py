"""Password hashing and signed access tokens for Prompt Laboratory."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    expires_at: int


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode(),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(derived, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def token_secret() -> str:
    secret = os.getenv("PROMPT_LAB_AUTH_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("PROMPT_LAB_AUTH_SECRET must contain at least 32 characters")
    return secret


def create_access_token(user_id: str, secret: str, lifetime_seconds: int = 28_800) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + lifetime_seconds,
        "nonce": secrets.token_hex(8),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64encode(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def decode_access_token(token: str, secret: str) -> TokenClaims:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _b64encode(
            hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("Invalid access token")
        payload = json.loads(_b64decode(encoded))
        user_id = str(payload["sub"])
        expires_at = int(payload["exp"])
        if expires_at <= int(time.time()):
            raise ValueError("Access token has expired")
        return TokenClaims(user_id=user_id, expires_at=expires_at)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired access token") from exc
