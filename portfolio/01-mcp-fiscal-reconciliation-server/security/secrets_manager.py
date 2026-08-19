"""
security/secrets_manager.py

Loads database credentials without storing them in plaintext anywhere in
the repo. Credentials live in a file encrypted with Fernet (AES-based
symmetric encryption); the decryption key itself lives in the OS
credential store (Windows Credential Manager / macOS Keychain / etc. via
`keyring`), not next to the encrypted file.
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
    """Plain connection values, decrypted and ready to hand to a DB driver."""

    username: str
    password: str
    host: str = ""
    port: int = 0
    dsn: str = ""


def _load_decryption_key() -> bytes:
    """Fetch the Fernet key from the OS credential store."""
    key = keyring.get_password(_CREDENTIAL_STORE_SERVICE_NAME, "encryption_key")
    if key is None:
        raise RuntimeError("No encryption key found in the OS credential store.")
    return key.encode("utf-8")


def _decrypt_credentials_file() -> dict:
    """Decrypt the credentials file into a dict keyed by system name."""
    if not _ENCRYPTED_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Encrypted credentials file not found at {_ENCRYPTED_CREDENTIALS_PATH}.")

    fernet = Fernet(_load_decryption_key())
    encrypted_bytes = _ENCRYPTED_CREDENTIALS_PATH.read_bytes()
    decrypted_bytes = fernet.decrypt(encrypted_bytes)
    return json.loads(decrypted_bytes.decode("utf-8"))


def get_credentials(system_name: str) -> DatabaseCredentials:
    """Return decrypted credentials for one named system (e.g. "legacy_system")."""
    all_credentials = _decrypt_credentials_file()
    if system_name not in all_credentials:
        raise KeyError(f"No credentials stored for system '{system_name}'.")
    return DatabaseCredentials(**all_credentials[system_name])
