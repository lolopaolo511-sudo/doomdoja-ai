"""Adapter contract tests: mock works, disabled is safe, official is placeholder."""

from __future__ import annotations

import pytest

from app.adapters import (
    DisabledTimocomAdapter,
    MockTimocomAdapter,
    MockTransEuAdapter,
    OfficialTimocomAdapter,
    get_email_adapter,
    get_timocom_adapter,
)


def test_mock_timocom_returns_offers_and_dry_runs_writes():
    a = MockTimocomAdapter()
    assert a.search_freight_offers({})  # returns demo offers
    out = a.publish_freight_offer({"x": 1}, dry_run=True)
    assert out["status"] == "dry_run"
    assert a.status().write_enabled is False


def test_disabled_timocom_is_inert():
    a = DisabledTimocomAdapter()
    assert a.search_freight_offers({}) == []
    assert a.status().credential_status == "not_configured"


def test_official_timocom_is_unimplemented_placeholder():
    a = OfficialTimocomAdapter()
    with pytest.raises(NotImplementedError):
        a.search_freight_offers({})


def test_transeu_mock_proposals():
    assert MockTransEuAdapter().retrieve_proposals("F1")


def test_adapter_selection_respects_flags():
    assert isinstance(get_timocom_adapter(enabled=False, demo_mode=True), MockTimocomAdapter)
    assert isinstance(get_timocom_adapter(enabled=False, demo_mode=False), DisabledTimocomAdapter)
    assert isinstance(get_timocom_adapter(enabled=True, demo_mode=True), OfficialTimocomAdapter)
    # Email mock available in demo
    assert get_email_adapter(enabled=False, demo_mode=True).fetch()
