"""Pluggable service-provider interfaces.

Distance, Toll, Currency, Tracking and OCR providers. Each ships a mock and a
manual-input fallback; real providers are added later without touching the
domain model. No paid services are required for the MVP.
"""

from __future__ import annotations

from typing import Protocol


class DistanceProvider(Protocol):
    def distance_km(self, origin: str, destination: str) -> float | None: ...


class MockDistanceProvider:
    name = "mock"
    _TABLE = {
        ("Warsaw", "Milan"): 1330,
        ("Poznań", "Verona"): 1150,
        ("Berlin", "Wrocław"): 350,
        ("Turin", "Kraków"): 1300,
        ("Łódź", "Munich"): 950,
        ("Prague", "Bologna"): 870,
        ("Katowice", "Rome"): 1500,
        ("Hamburg", "Warsaw"): 750,
    }

    def distance_km(self, origin: str, destination: str) -> float | None:
        return float(self._TABLE.get((origin, destination), 0)) or None


class ManualDistanceProvider:
    name = "manual"

    def distance_km(self, origin: str, destination: str) -> float | None:
        return None  # operator supplies the value


class MockCurrencyProvider:
    name = "mock"
    _RATES = {"EUR": 1.0, "PLN": 0.23}  # PLN→EUR illustrative

    def to_eur(self, amount: float, currency: str) -> float:
        return round(amount * self._RATES.get(currency, 1.0), 2)


class MockTollProvider:
    name = "mock"

    def toll_estimate(self, distance_km: float) -> float:
        return round(distance_km * 0.12, 2)


class MockTrackingProvider:
    name = "mock"

    def events(self, shipment_ref: str) -> list[dict]:
        return []  # mock events are seeded directly in demo data


class MockOCRProvider:
    name = "mock"

    def extract_text(self, filename: str) -> str:
        return ""  # placeholder; real OCR added via OCRProvider later


def get_distance_provider(demo_mode: bool) -> DistanceProvider:
    return MockDistanceProvider() if demo_mode else ManualDistanceProvider()
