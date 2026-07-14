"""TIMOCOM adapter.

Production-shaped interface + mock implementation. TIMOCOM publicly describes a
freight-exchange API split into searching and inserting offers, plus
integrations for transport orders and tracking; the available scope DEPENDS ON
THE USER'S CONTRACT. We therefore ship an interface, a mock, a disabled variant
and an unimplemented official placeholder. No endpoint URLs or credentials are
invented here. See docs/TIMOCOM_INTEGRATION_CHECKLIST.md.
"""

from __future__ import annotations

from .base import AdapterCapabilities, BaseAdapter

TIMOCOM_FEATURES = [
    "search_freight_offers",
    "retrieve_matching_offers",
    "publish_freight_offer",  # if authorised
    "create_transport_order",  # if authorised
    "retrieve_tracking_updates",  # if authorised
    "price_overview",  # if contract allows
    "carrier_verification_data",  # if authorised
]


class TimocomAdapter(BaseAdapter):
    name = "timocom"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            name=self.name,
            read=self.read_enabled,
            write=self.write_enabled,
            features=TIMOCOM_FEATURES,
        )

    def search_freight_offers(self, query: dict) -> list[dict]:
        raise NotImplementedError


class MockTimocomAdapter(TimocomAdapter):
    """Reproducible mock returning demo offers; safe for the local MVP."""

    def __init__(self) -> None:
        super().__init__(
            read_enabled=True, write_enabled=False, mock_enabled=True, credential_status="mock"
        )

    def search_freight_offers(self, query: dict) -> list[dict]:
        return [
            {
                "source_platform": "timocom",
                "source_reference": "TC-MOCK-001",
                "raw_text": "Warsaw (PL) -> Milan (IT), 22t tautliner, ADR, 12/06",
                "language": "en",
            }
        ]

    def publish_freight_offer(
        self, payload: dict, *, approval_token=None, idempotency_key=None, dry_run=True
    ) -> dict:
        return self._guard_write(
            "publish_freight_offer",
            payload,
            approval_token=approval_token,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
        )


class DisabledTimocomAdapter(TimocomAdapter):
    """All operations refuse; surfaces a clear 'unavailable' state to the UI."""

    def __init__(self) -> None:
        super().__init__(
            read_enabled=False,
            write_enabled=False,
            mock_enabled=False,
            credential_status="not_configured",
        )

    def search_freight_offers(self, query: dict) -> list[dict]:
        self.last_failure = "TIMOCOM disabled — use manual import"
        return []


class OfficialTimocomAdapter(TimocomAdapter):
    """Placeholder for the real integration. Intentionally not implemented.

    Enable only after the employer confirms contract scope, credentials and a
    sandbox. Implement against official TIMOCOM API docs — never via scraping.
    """

    def __init__(self) -> None:
        super().__init__(
            read_enabled=False,
            write_enabled=False,
            mock_enabled=False,
            credential_status="not_configured",
        )

    def search_freight_offers(self, query: dict) -> list[dict]:  # pragma: no cover
        raise NotImplementedError(
            "OfficialTimocomAdapter not implemented — see docs/TIMOCOM_INTEGRATION_CHECKLIST.md"
        )


def get_timocom_adapter(enabled: bool, demo_mode: bool) -> TimocomAdapter:
    if enabled:
        return OfficialTimocomAdapter()
    if demo_mode:
        return MockTimocomAdapter()
    return DisabledTimocomAdapter()
