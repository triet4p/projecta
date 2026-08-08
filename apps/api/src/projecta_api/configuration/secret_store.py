"""Application-encrypted operational secret store for the Compose baseline."""

from __future__ import annotations

from secrets import token_urlsafe

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from projecta_api.configuration.errors import SecretStoreUnavailable
from projecta_api.configuration.storage import OperationalDatabase, utc_now


class ApplicationEncryptedSecretStore:
    """Encrypt credentials before SQLite persistence using a deployment key."""

    def __init__(self, database: OperationalDatabase, master_key: SecretStr | None) -> None:
        self._database = database
        self._master_key = master_key

    def create(self, secret: SecretStr) -> str:
        """Encrypt and persist one secret, returning only an opaque reference."""
        value = secret.get_secret_value()
        if not value or len(value) > 16_384:
            raise SecretStoreUnavailable()
        fernet = self._fernet()
        reference = f"secret_{token_urlsafe(18)}"
        ciphertext = fernet.encrypt(value.encode("utf-8"))
        try:
            self._database.execute(
                "INSERT INTO secret_records(secret_reference, ciphertext, created_at) VALUES (?, ?, ?)",
                (reference, ciphertext, utc_now()),
            )
        except Exception as error:
            raise SecretStoreUnavailable() from error
        return reference

    def resolve(self, reference: str) -> SecretStr:
        """Resolve one opaque reference or fail closed without revealing details."""
        if not reference or len(reference) > 128:
            raise SecretStoreUnavailable()
        row = self._database.execute(
            "SELECT ciphertext FROM secret_records WHERE secret_reference = ?", (reference,)
        ).fetchone()
        if row is None:
            raise SecretStoreUnavailable()
        plaintext = b""
        try:
            plaintext = self._fernet().decrypt(bytes(row["ciphertext"]))
            value = plaintext.decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError) as error:
            raise SecretStoreUnavailable() from error
        finally:
            del plaintext
        if not value:
            raise SecretStoreUnavailable()
        return SecretStr(value)

    def delete(self, reference: str | None) -> None:
        """Delete an opaque secret reference idempotently."""
        if not reference:
            return
        self._database.execute("DELETE FROM secret_records WHERE secret_reference = ?", (reference,))

    def _fernet(self) -> Fernet:
        """Build the cipher only when the deployment-owned master key is valid."""
        key = self._master_key.get_secret_value() if self._master_key else ""
        if not key:
            raise SecretStoreUnavailable()
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise SecretStoreUnavailable() from error
