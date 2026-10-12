from __future__ import annotations

import uuid

import keyring
from keyring.errors import KeyringError


class CredentialVaultError(RuntimeError):
    pass


class CredentialVault:
    """Store secrets in the OS credential vault; SQLite keeps only references."""

    SERVICE_NAME = "CompanyAIWorkbench"

    def put(self, secret: str, reference: str | None = None) -> str:
        credential_ref = reference or f"credential:{uuid.uuid4()}"
        try:
            keyring.set_password(self.SERVICE_NAME, credential_ref, secret)
        except KeyringError as exc:
            raise CredentialVaultError(f"无法写入系统凭据库: {exc}") from exc
        return credential_ref

    def get(self, reference: str) -> str:
        try:
            secret = keyring.get_password(self.SERVICE_NAME, reference)
        except KeyringError as exc:
            raise CredentialVaultError(f"无法读取系统凭据库: {exc}") from exc
        if secret is None:
            raise CredentialVaultError("系统凭据不存在或已被移除")
        return secret

    def delete(self, reference: str) -> None:
        try:
            keyring.delete_password(self.SERVICE_NAME, reference)
        except KeyringError as exc:
            raise CredentialVaultError(f"无法删除系统凭据: {exc}") from exc

