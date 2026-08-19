"""
security/secrets_manager.py

Loads database credentials without ever storing them in plaintext in a
config file or in source control.

How it works
------------
1. Credentials (username, password, host, dsn, ...) are stored on disk
   ENCRYPTED with a symmetric key (Fernet, from the `cryptography`
   library — AES under the hood with built-in integrity checking).
2. The DECRYPTION KEY itself is not stored next to the encrypted data.
   It lives in the OS-level credential store (Windows Credential Manager
   in this project's real environment; `keyring` supports macOS Keychain
   and Linux Secret Service too).
3. At runtime, this module reads the key from the OS credential store,
   uses it to decrypt the credentials file, and hands back a plain
   Python object — the decrypted values only ever exist in memory, for
   as long as the process is running.

Why bother with two layers instead of just encrypting with a hardcoded
key? Because a hardcoded key defeats the purpose — anyone with the source
code would have the key too. Splitting "encrypted data" and "the key to
read it" across two different storage mechanisms means a leak of the
repository alone isn't enough to recover any credentials.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import keyring
from cryptography.fernet import Fernet

_CREDENTIAL_STORE_SERVICE_NAME = "fiscal-reconciliation-mcp"
_ENCRYPTED_CREDENTIALS_PATH = Path(
    os.environ.get("ENCRYPTED_CREDENTIALS_PATH", "credentials.enc")
)


@dataclass
class DatabaseCredentials:
    """Plain-value container returned to callers. Deliberately simple —
    this is the *last* stop for these values before they're handed to a
    database driver; no further transformation happens here.
    """

    username: str
    password: str
    host: str = ""
    port: int = 0
    dsn: str = ""


def _load_decryption_key() -> bytes:
    """Fetch the Fernet key from the OS-level credential store.

    `keyring.get_password` returns None if nothing is stored under that
    service/username pair — we fail loudly instead of silently
    proceeding with a missing key, since a missing key almost always
    means "this machine was never set up" rather than "there are no
    credentials to load".
    """
    key = keyring.get_password(_CREDENTIAL_STORE_SERVICE_NAME, "encryption_key")
    if key is None:
        raise RuntimeError(
            "No encryption key found in the OS credential store. Run the "
            "setup script to generate and store one before starting the "
            "server."
        )
    return key.encode("utf-8")


def _decrypt_credentials_file() -> dict:
    """Decrypt the credentials file into a plain dict of connection
    profiles, keyed by system name (e.g. "legacy_system", "erp_system").
    """
    if not _ENCRYPTED_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Encrypted credentials file not found at "
            f"{_ENCRYPTED_CREDENTIALS_PATH}. Nothing to decrypt."
        )

    fernet = Fernet(_load_decryption_key())
    encrypted_bytes = _ENCRYPTED_CREDENTIALS_PATH.read_bytes()
    decrypted_bytes = fernet.decrypt(encrypted_bytes)
    return json.loads(decrypted_bytes.decode("utf-8"))


def get_credentials(system_name: str) -> DatabaseCredentials:
    """Public entry point used by connectors.py: give me the credentials
    for one named system, already decrypted.

    Credentials are decrypted fresh on every call rather than cached at
    module level, trading a small amount of performance for never
    keeping decrypted secrets around longer than the moment they're
    needed.
    """
    all_credentials = _decrypt_credentials_file()
    if system_name not in all_credentials:
        raise KeyError(
            f"No credentials stored for system '{system_name}'. Known "
            f"systems: {list(all_credentials.keys())}"
        )
    return DatabaseCredentials(**all_credentials[system_name])
