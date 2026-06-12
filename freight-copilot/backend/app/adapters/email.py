"""Email adapters.

Mock + manual-inbox implementations, with disabled placeholders for IMAP,
Gmail and Microsoft Graph. Email is imported and parsed into a freight source;
messages are NEVER sent automatically.
"""

from __future__ import annotations

from .base import AdapterCapabilities, BaseAdapter

SAMPLE_EMAIL = {
    "from": "spedizioni@example-it.com",
    "subject": "Carico Torino -> Cracovia 24/06",
    "body": "Buongiorno, abbiamo un carico Turin (IT) -> Kraków (PL), 18t, "
    "tautliner, ritiro 24/06. Tariffa 1500 EUR. Grazie.",
    "language": "it",
}


class EmailAdapter(BaseAdapter):
    name = "email"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self.name,
            read=self.read_enabled,
            write=self.write_enabled,
            features=["import_email", "parse_email", "draft_reply"],
        )

    def fetch(self) -> list[dict]:
        raise NotImplementedError


class MockEmailAdapter(EmailAdapter):
    def __init__(self) -> None:
        super().__init__(
            read_enabled=True, write_enabled=False, mock_enabled=True, credential_status="mock"
        )

    def fetch(self) -> list[dict]:
        return [SAMPLE_EMAIL]


class ManualInboxAdapter(EmailAdapter):
    """Operator pastes/forwards email text manually; the safest default."""

    def __init__(self) -> None:
        super().__init__(
            read_enabled=True, write_enabled=False, mock_enabled=True, credential_status="manual"
        )

    def fetch(self) -> list[dict]:
        return []  # populated by the operator via the UI


class DisabledImapAdapter(EmailAdapter):
    def __init__(self) -> None:
        super().__init__(credential_status="not_configured", mock_enabled=False)

    def fetch(self) -> list[dict]:  # pragma: no cover
        raise NotImplementedError("IMAP adapter not configured")


def get_email_adapter(enabled: bool, demo_mode: bool) -> EmailAdapter:
    if demo_mode:
        return MockEmailAdapter()
    if enabled:
        return ManualInboxAdapter()
    return DisabledImapAdapter()
