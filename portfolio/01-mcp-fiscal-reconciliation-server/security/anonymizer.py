"""
security/anonymizer.py

Pseudonymizes sensitive identifiers before data reaches an LLM through an
MCP tool response. Uses HMAC (a secret-keyed hash) instead of a plain
hash, so the mapping can't be brute-forced by guessing likely values.

Deterministic on purpose: the same input always maps to the same output,
so joins and comparisons downstream still work on the pseudonymized data.
This is one-way -- there's no function to reverse it.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_SECRET_KEY = os.environ.get("ANONYMIZER_SECRET_KEY", "").encode("utf-8")


def pseudonymize_identifier(value: str) -> str:
    """Deterministically pseudonymize an identifier (document number, branch code, etc.)."""
    if not _SECRET_KEY:
        raise RuntimeError("ANONYMIZER_SECRET_KEY is not set.")

    digest = hmac.new(_SECRET_KEY, value.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:12]


def scale_monetary_value(value: float, scale_factor: float = 1.0) -> float:
    """Scale a monetary value by a fixed factor, so relative comparisons
    still work without exposing the real figure.
    """
    return round(value * scale_factor, 2)
