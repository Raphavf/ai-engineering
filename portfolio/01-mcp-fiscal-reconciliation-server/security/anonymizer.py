"""
security/anonymizer.py

Pseudonymizes sensitive identifiers before data leaves the trusted
boundary — specifically, before anything gets handed to an LLM through
an MCP tool response.

Why HMAC instead of a plain hash?
----------------------------------
A plain hash (e.g. `hashlib.sha256(value)`) is deterministic but crackable
by brute force if the space of possible inputs is small (like branch codes
or document numbers with a predictable format) — an attacker just hashes
every possible value and builds a lookup table.

HMAC mixes in a SECRET KEY before hashing. Without that key, you can't
rebuild the lookup table even if you know the *format* of the original
values. It's still deterministic — the same input always produces the
same output, which matters because we need `pseudonymize("BRANCH-001")`
to return the same string every time so joins and comparisons downstream
still work correctly on the pseudonymized data.

This is pseudonymization, not encryption: it's a one-way function.
There's no `de_pseudonymize()` here on purpose — if you need the real
value back, you look it up by its original key in the trusted system,
you don't try to reverse the hash.
"""

from __future__ import annotations

import hashlib
import hmac
import os

# In production this key is loaded from the same secrets store used for
# database credentials (see secrets_manager.py) — never hardcoded, and
# never the same key used for anything else.
_SECRET_KEY = os.environ.get("ANONYMIZER_SECRET_KEY", "").encode("utf-8")


def pseudonymize_identifier(value: str) -> str:
    """Deterministically pseudonymize a sensitive identifier (e.g. a
    document number, a customer/branch code) so it's safe to include in
    data that reaches an LLM, while still being consistent enough to use
    as a join key or to spot repeated occurrences of the same entity.
    """
    if not _SECRET_KEY:
        raise RuntimeError(
            "ANONYMIZER_SECRET_KEY is not set. Refusing to pseudonymize "
            "with an empty key, since that would make the output "
            "predictable and defeat the whole point."
        )

    digest = hmac.new(_SECRET_KEY, value.encode("utf-8"), hashlib.sha256)
    # Truncated to 12 hex characters: enough entropy to make collisions
    # practically irrelevant for this use case, short enough to stay
    # readable in logs and LLM tool responses.
    return digest.hexdigest()[:12]


def scale_monetary_value(value: float, scale_factor: float = 1.0) -> float:
    """Optionally scale monetary values by a fixed, secret factor before
    they reach an LLM — so relative comparisons (X is bigger than Y) and
    proportions still work, but the absolute numbers aren't the real
    figures. Used when even approximate real values are too sensitive to
    share, but the *shape* of the data still needs to be useful.

    A scale_factor of 1.0 (the default) means "don't actually obscure
    anything" — useful in tests and local development.
    """
    return round(value * scale_factor, 2)
