"""Distance/toll provider tests — offline default + OSRM fallback + toll rates."""

from __future__ import annotations

from app.adapters.providers import (
    CountryRateTollProvider,
    MockDistanceProvider,
    OSRMDistanceProvider,
    get_distance_provider,
    get_toll_provider,
)


def test_mock_distance_is_offline_geo_estimate():
    d = MockDistanceProvider().distance_km("Warsaw", "Milan")
    assert d is not None and 1100 <= d <= 1500


def test_osrm_falls_back_to_geo_estimate_on_failure():
    # Point OSRM at an unroutable host so the HTTP call fails fast; the provider
    # must fall back to the offline geographic estimate (never raise).
    p = OSRMDistanceProvider()
    p.base_url = "http://127.0.0.1:9"  # nothing listening
    d = p.distance_km("Warsaw", "Milan")
    assert d is not None and 1100 <= d <= 1500


def test_osrm_unknown_city_returns_none():
    p = OSRMDistanceProvider()
    p.base_url = "http://127.0.0.1:9"
    assert p.distance_km("Atlantis", "Milan") is None


def test_country_rate_toll_blends_origin_and_dest():
    toll = CountryRateTollProvider().toll_eur(1000, "PL", "IT")
    # PL ~0.10 + IT ~0.18 -> blended ~0.14 * 1000 km ≈ 140 EUR.
    assert 120 <= toll <= 160


def test_toll_default_when_country_unknown():
    toll = CountryRateTollProvider().toll_eur(1000, None, None)
    assert toll > 0


def test_provider_selection_respects_config(monkeypatch):
    import app.config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("DISTANCE_PROVIDER", "osrm")
    assert isinstance(get_distance_provider(cfg.Settings()), OSRMDistanceProvider)
    monkeypatch.setenv("DISTANCE_PROVIDER", "mock")
    assert isinstance(get_distance_provider(cfg.Settings()), MockDistanceProvider)
    assert get_toll_provider(cfg.Settings()).name == "country_rate"


def test_pricing_uses_toll_and_geo_distance():
    from app.agents import PricingAgent

    res = PricingAgent().estimate(
        {
            "origin_city": "Warsaw",
            "origin_country": "PL",
            "dest_city": "Milan",
            "dest_country": "IT",
            "vehicle_type": "tautliner",
            "currency": "EUR",
        }
    )
    assert res.output["loaded_km"] >= 1100  # geo estimate, not flat 800
    assert res.output["toll"] > 0
