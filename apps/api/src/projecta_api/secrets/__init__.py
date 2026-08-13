"""Runtime secret boundary adapters."""

from projecta_api.secrets.openbao import OpenBaoSecretError, OpenBaoSecretStore

__all__ = ["OpenBaoSecretError", "OpenBaoSecretStore"]
