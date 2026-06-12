"""Common adapter contract.

Every external integration exposes the same capability + status surface so the
UI can show integration health and so safety gates (writes disabled by default,
dry-run, idempotency, audit) are uniform across providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AdapterCapabilities:
    name: str
    read: bool = False
    write: bool = False
    features: list[str] = field(default_factory=list)


@dataclass
class AdapterStatus:
    name: str
    configured: bool
    read_enabled: bool
    write_enabled: bool
    mock_enabled: bool
    credential_status: str  # never reveals the actual secret
    last_successful_sync: datetime | None = None
    last_failure: str | None = None


class ExternalWriteBlocked(RuntimeError):
    """Raised when a write is attempted without approval / while disabled."""


class BaseAdapter:
    """Base adapter enforcing the safety contract.

    Concrete adapters override the capability methods. Writes always pass
    through ``_guard_write`` which refuses unless the adapter is explicitly
    write-enabled AND an approval token is supplied (dry-run otherwise).
    """

    name = "base"

    def __init__(
        self,
        *,
        read_enabled: bool = False,
        write_enabled: bool = False,
        mock_enabled: bool = True,
        credential_status: str = "not_configured",
    ) -> None:
        self.read_enabled = read_enabled
        self.write_enabled = write_enabled
        self.mock_enabled = mock_enabled
        self.credential_status = credential_status
        self.last_successful_sync: datetime | None = None
        self.last_failure: str | None = None
        self._seen_idempotency_keys: set[str] = set()

    def capabilities(self) -> AdapterCapabilities:  # pragma: no cover - overridden
        return AdapterCapabilities(name=self.name)

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            name=self.name,
            configured=self.credential_status != "not_configured",
            read_enabled=self.read_enabled,
            write_enabled=self.write_enabled,
            mock_enabled=self.mock_enabled,
            credential_status=self.credential_status,
            last_successful_sync=self.last_successful_sync,
            last_failure=self.last_failure,
        )

    def _guard_write(
        self,
        action: str,
        payload: dict,
        *,
        approval_token: str | None,
        idempotency_key: str | None,
        dry_run: bool,
    ) -> dict:
        """Uniform write gate. Returns a result envelope; never raises in demo."""
        if idempotency_key and idempotency_key in self._seen_idempotency_keys:
            return {"status": "duplicate_ignored", "action": action}
        if dry_run or not self.write_enabled:
            return {
                "status": "dry_run",
                "action": action,
                "would_send": payload,
                "reason": "writes disabled or dry-run requested",
            }
        if not approval_token:
            raise ExternalWriteBlocked(
                f"{self.name}.{action} requires an approved ApprovalRequest token"
            )
        if idempotency_key:
            self._seen_idempotency_keys.add(idempotency_key)
        self.last_successful_sync = datetime.utcnow()
        return {"status": "submitted", "action": action, "payload": payload}
