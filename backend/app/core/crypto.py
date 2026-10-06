"""Credential encryption helpers using Fernet symmetric encryption.

Uses MultiFernet-compatible design (single key now) so key rotation
can be added later by extending to multiple keys.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

# Build a MultiFernet with a single key so rotation can be added later
# by simply prepending a new key to the list.
_fernet = MultiFernet([Fernet(settings.ENCRYPTION_KEY.encode())])


def encrypt_json(data: dict[str, Any]) -> str:
    """Serialize *data* to JSON and encrypt it.

    Returns the Fernet token as a UTF-8 string suitable for database storage.
    """
    plaintext = json.dumps(data).encode("utf-8")
    return _fernet.encrypt(plaintext).decode("utf-8")


def decrypt_json(token: str) -> dict[str, Any]:
    """Decrypt a Fernet token and deserialize the JSON payload.

    Raises ``ValueError`` with a generic, safe message on any failure
    (wrong key, tampered data, etc.) — never exposes plaintext or ciphertext.
    """
    try:
        plaintext = _fernet.decrypt(token.encode("utf-8"))
        result: dict[str, Any] = json.loads(plaintext)
        return result
    except (InvalidToken, json.JSONDecodeError, Exception):
        raise ValueError(
            "Failed to decrypt credentials: data is invalid or corrupted"
        ) from None
