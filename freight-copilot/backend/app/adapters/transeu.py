"""Trans.eu adapter.

Production-shaped interface + mock implementation. Trans.eu publishes public API
documentation covering creating/publishing freight, updating, cancelling,
archiving, statuses, proposals, price negotiation, accepted-freight details and
monitoring tasks. We ship an interface, a mock, a disabled variant and an
unimplemented official placeholder. No endpoint URLs or credentials are invented
here. See docs/TRANSEU_INTEGRATION_CHECKLIST.md.
"""

from __future__ import annotations

from .base import AdapterCapabilities, BaseAdapter

TRANSEU_FEATURES = [
    "create_freight",
    "publish_freight",
    "update_freight",
    "cancel_publication",
    "archive_freight",
    "retrieve_freight_status",
    "retrieve_proposals",
    "retrieve_proposal_details",
    "negotiation_state",
    "retrieve_accepted_freight",
    "create_monitoring_task",
]


class TransEuAdapter(BaseAdapter):
    name = "transeu"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self.name,
            read=self.read_enabled,
            write=self.write_enabled,
            features=TRANSEU_FEATURES,
        )

    def retrieve_proposals(self, freight_id: str) -> list[dict]:
        raise NotImplementedError


class MockTransEuAdapter(TransEuAdapter):
    def __init__(self) -> None:
        super().__init__(
            read_enabled=True, write_enabled=False, mock_enabled=True, credential_status="mock"
        )

    def retrieve_proposals(self, freight_id: str) -> list[dict]:
        return [
            {
                "carrier": "Demo Trans Sp. z o.o.",
                "price": 1450,
                "currency": "EUR",
                "state": "negotiation",
            },
        ]

    def publish_freight(
        self, payload: dict, *, approval_token=None, idempotency_key=None, dry_run=True
    ) -> dict:
        return self._guard_write(
            "publish_freight",
            payload,
            approval_token=approval_token,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
        )


class DisabledTransEuAdapter(TransEuAdapter):
    def __init__(self) -> None:
        super().__init__(
            read_enabled=False,
            write_enabled=False,
            mock_enabled=False,
            credential_status="not_configured",
        )

    def retrieve_proposals(self, freight_id: str) -> list[dict]:
        self.last_failure = "Trans.eu disabled — use manual import"
        return []


class OfficialTransEuAdapter(TransEuAdapter):
    """Placeholder for the real integration. Intentionally not implemented.

    Enable only after the employer confirms API scopes, credentials and a
    sandbox. Implement against official Trans.eu API docs — never via scraping.
    """

    def __init__(self) -> None:
        super().__init__(
            read_enabled=False,
            write_enabled=False,
            mock_enabled=False,
            credential_status="not_configured",
        )

    def retrieve_proposals(self, freight_id: str) -> list[dict]:  # pragma: no cover
        raise NotImplementedError(
            "OfficialTransEuAdapter not implemented — see docs/TRANSEU_INTEGRATION_CHECKLIST.md"
        )


def get_transeu_adapter(enabled: bool, demo_mode: bool) -> TransEuAdapter:
    if enabled:
        return OfficialTransEuAdapter()
    if demo_mode:
        return MockTransEuAdapter()
    return DisabledTransEuAdapter()
