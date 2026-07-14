"""Geographic distance estimation tests."""

from __future__ import annotations

from app.geo import estimate_distance_km


def test_known_lane_is_in_realistic_range():
    # Warsaw → Milan is ~1300 km by road; estimate should be in a sane band.
    d = estimate_distance_km("Warsaw", "Milan")
    assert d is not None
    assert 1100 <= d <= 1500


def test_short_lane():
    # Berlin → Wrocław is ~350 km.
    d = estimate_distance_km("Berlin", "Wrocław")
    assert d is not None
    assert 250 <= d <= 450


def test_is_symmetric():
    assert estimate_distance_km("Turin", "Kraków") == estimate_distance_km("Kraków", "Turin")


def test_case_and_diacritic_insensitive():
    assert estimate_distance_km("kraków", "milan") == estimate_distance_km("Krakow", "Milan")


def test_unknown_city_returns_none():
    assert estimate_distance_km("Atlantis", "Milan") is None
    assert estimate_distance_km("Warsaw", None) is None
