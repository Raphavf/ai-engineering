"""
security/secrets_manager.py

Loads database credentials without storing them in plaintext in the repo.
Credentials live in a Fernet-encrypted file; the decryption key lives in
the OS credential store (Windows Credential Manager / macOS Keychain /
Secret Service via `keyring`), not next to the encrypted file.

Helper to create the encrypted file:
    python -m fiscal_recon.security.secrets_manager encrypt credentials.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cryptography.fernet import Fernet

SERVICE_NAME = "fiscal-recon-mcp"
KEY_NAME = "encryption_key"


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str
    host: str = ""
    port: int = 0
    dsn: str = ""

    def __repr__(self) -> str:  # never print the password in logs/tracebacks
        return f"DatabaseCredentials(username={self.username!r}, host={self.host!r}, dsn={self.dsn!r})"


def _keyring_loader() -> bytes:
    import keyring

    key = keyring.get_password(SERVICE_NAME, KEY_NAME)
    if key is None:
        raise RuntimeError("No encryption key found in the OS credential store.")
    return key.encode("utf-8")


class SecretsManager:
    def __init__(self, encrypted_path: str | Path, key_loader: Callable[[], bytes] = _keyring_loader):
        self._path = Path(encrypted_path)
        self._key_loader = key_loader

    def _decrypt(self) -> dict:
        if not self._path.exists():
            raise FileNotFoundError(f"Encrypted credentials file not found at {self._path}.")
        fernet = Fernet(self._key_loader())
        return json.loads(fernet.decrypt(self._path.read_bytes()).decode("utf-8"))

    def get_credentials(self, system_name: str) -> DatabaseCredentials:
        all_credentials = self._decrypt()
        if system_name not in all_credentials:
            raise KeyError(f"No credentials stored for system '{system_name}'.")
        return DatabaseCredentials(**all_credentials[system_name])


def encrypt_file(plain_json_path: Path, out_path: Path) -> None:
    """Encrypt a plaintext credentials JSON and store a fresh key in the OS keyring."""
    import keyring

    key = Fernet.generate_key()
    out_path.write_bytes(Fernet(key).encrypt(plain_json_path.read_bytes()))
    keyring.set_password(SERVICE_NAME, KEY_NAME, key.decode("utf-8"))
    print(f"Wrote {out_path}. Key stored in OS keyring. Delete {plain_json_path} now.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "encrypt":
        sys.exit("usage: python -m fiscal_recon.security.secrets_manager encrypt <credentials.json>")
    encrypt_file(Path(sys.argv[2]), Path("credentials.enc"))
