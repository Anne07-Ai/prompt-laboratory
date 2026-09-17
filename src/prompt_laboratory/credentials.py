"""Authenticated encryption for user-owned provider credentials."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialCipher:
    """Encrypt credentials with AES-256-GCM and identity-bound associated data."""

    VERSION = "v1"

    def __init__(self, master_secret: str) -> None:
        if len(master_secret) < 32:
            raise ValueError("PROMPT_LAB_CREDENTIAL_KEY must contain at least 32 characters")
        self._key = hashlib.sha256(master_secret.encode()).digest()

    @staticmethod
    def _aad(user_id: str, provider: str) -> bytes:
        return f"{user_id}:{provider}".encode()

    def encrypt(self, value: str, *, user_id: str, provider: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Provider API key cannot be empty")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(
            nonce,
            normalized.encode(),
            self._aad(user_id, provider),
        )
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode()
        return f"{self.VERSION}.{payload}"

    def decrypt(self, value: str, *, user_id: str, provider: str) -> str:
        try:
            version, payload = value.split(".", 1)
            if version != self.VERSION:
                raise ValueError("Unsupported credential encryption version")
            decoded = base64.urlsafe_b64decode(payload.encode())
            plaintext = AESGCM(self._key).decrypt(
                decoded[:12],
                decoded[12:],
                self._aad(user_id, provider),
            )
            return plaintext.decode()
        except Exception as exc:
            raise ValueError("Stored provider credential cannot be decrypted") from exc
