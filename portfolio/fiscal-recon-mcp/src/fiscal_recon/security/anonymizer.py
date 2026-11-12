"""
security/anonymizer.py

Pseudonymizes sensitive identifiers before data reaches an LLM through an
MCP tool response. Uses HMAC (a secret-keyed hash) instead of a plain
hash, so the mapping can't be brute-forced by guessing likely values.

Deterministic on purpose: the same input always maps to the same output,
so an agent can take an ID from one tool's output and pass it to another.
One-way -- there is no function to reverse it.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ENV_VAR = "ANONYMIZER_SECRET_KEY"
_MIN_KEY_BYTES = 16


class Pseudonymizer:
    def __init__(self, secret_key: bytes | str):
        key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
        if len(key) < _MIN_KEY_BYTES:
            raise ValueError(f"Secret key must be at least {_MIN_KEY_BYTES} bytes.")
        self._key = key

    @classmethod
    def from_env(cls) -> "Pseudonymizer":
        """Read the key when the server starts, not at import time."""
        key = os.environ.get(_ENV_VAR, "")
        if not key:
            raise RuntimeError(f"{_ENV_VAR} is not set.")
        return cls(key)

    def pseudonymize(self, value: str) -> str:
        digest = hmac.new(self._key, value.encode("utf-8"), hashlib.sha256)
        return digest.hexdigest()[:16]
