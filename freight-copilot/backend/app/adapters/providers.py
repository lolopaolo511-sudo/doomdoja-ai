"""Pluggable service-provider interfaces.

Distance, Toll, Currency, Tracking and OCR providers. Each ships an offline
default plus a real implementation that can be switched on by configuration,
without touching the domain model.

Routing/toll defaults are OFFLINE so ``make demo`` needs no network:
  * DistanceProvider default = ``mock`` (geographic estimate, app/geo.py).
  * Set ``DISTANCE_PROVIDER=osrm`` to call a real OSRM routing server for true
    driving distance (falls back to the geo estimate on any failure).
  * TollProvider default = ``country_rate`` (per-country EUR/km truck-toll
    estimate). Exact tolls require an authorised provider (e.g. TollGuru) —
    add it behind this same interface later.
"""

from __future__ import annotations

from typing import Protocol

from ..config import get_settings
from ..geo import CITY_COORDS, estimate_distance_km


# --------------------------------------------------------------------------- #
# Distance
# --------------------------------------------------------------------------- #
class DistanceProvider(Protocol):
    name: str

    def distance_km(self, origin: str, destination: str) -> float | None: ...


class MockDistanceProvider:
    """Offline geographic estimate (haversine x road-factor) over EU hubs."""

    name = "mock"

    def distance_km(self, origin: str, destination: str) -> float | None:
        return estimate_distance_km(origin, destination)


class ManualDistanceProvider:
    name = "manual"

    def distance_km(self, origin: str, destination: str) -> float | None:
        return None  # operator supplies the value


class OSRMDistanceProvider:
    """Real driving distance via an OSRM routing server (no API key).

    Resolves city names to coordinates (app/geo.py), queries OSRM, and returns
    the driving distance in km. Falls back to the offline geographic estimate
    on any network/parse failure or unknown city, so pricing never breaks.
    """

    name = "osrm"

    def __init__(self) -> None:
        self.base_url = get_settings().osrm_base_url.rstrip("/")

    def distance_km(self, origin: str, destination: str) -> float | None:
        fallback = estimate_distance_km(origin, destination)
        a = CITY_COORDS.get((origin or "").strip().lower())
        b = CITY_COORDS.get((destination or "").strip().lower())
        if not a or not b:
            return fallback
        try:
            import httpx

            url = f"{self.base_url}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
            resp = httpx.get(url, params={"overview": "false"}, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return fallback
            meters = data["routes"][0]["distance"]
            return round(meters / 1000.0)
        except Exception:
            return fallback


def get_distance_provider(settings=None) -> DistanceProvider:
    settings = settings or get_settings()
    choice = settings.distance_provider
    if choice == "osrm":
        return OSRMDistanceProvider()
    if choice == "manual":
        return ManualDistanceProvider()
    return MockDistanceProvider()


# --------------------------------------------------------------------------- #
# Toll
# --------------------------------------------------------------------------- #
# Approximate motorway truck-toll rates (EUR/km, ~40t) by country. Estimates —
# replace with an authorised toll provider for exact, route-accurate tolls.
TOLL_EUR_PER_KM_BY_COUNTRY: dict[str, float] = {
    "DE": 0.19,
    "FR": 0.20,
    "IT": 0.18,
    "AT": 0.40,
    "PL": 0.10,
    "CZ": 0.20,
    "SK": 0.22,
    "ES": 0.15,
    "BE": 0.16,
    "NL": 0.0,
    "CH": 0.55,
    "SI": 0.25,
    "HU": 0.25,
}
_DEFAULT_TOLL_EUR_PER_KM = 0.15


class TollProvider(Protocol):
    name: str

    def toll_eur(
        self, distance_km: float, origin_country: str | None, dest_country: str | None
    ) -> float: ...


class CountryRateTollProvider:
    """Estimate tolls by blending the origin and destination countries' rates."""

    name = "country_rate"

    def toll_eur(
        self, distance_km: float, origin_country: str | None, dest_country: str | None
    ) -> float:
        rates = [
            TOLL_EUR_PER_KM_BY_COUNTRY.get((c or "").upper(), _DEFAULT_TOLL_EUR_PER_KM)
            for c in (origin_country, dest_country)
            if c
        ]
        rate = sum(rates) / len(rates) if rates else _DEFAULT_TOLL_EUR_PER_KM
        return round(distance_km * rate, 2)


class NoTollProvider:
    name = "none"

    def toll_eur(self, distance_km: float, origin_country=None, dest_country=None) -> float:
        return 0.0


def get_toll_provider(settings=None) -> TollProvider:
    settings = settings or get_settings()
    if settings.toll_provider == "none":
        return NoTollProvider()
    return CountryRateTollProvider()


# --------------------------------------------------------------------------- #
# Currency / tracking / OCR (offline mocks; pluggable later)
# --------------------------------------------------------------------------- #
class MockCurrencyProvider:
    name = "mock"
    _RATES = {"EUR": 1.0, "PLN": 0.23}  # PLN->EUR illustrative

    def to_eur(self, amount: float, currency: str) -> float:
        return round(amount * self._RATES.get(currency, 1.0), 2)


class MockTrackingProvider:
    name = "mock"

    def events(self, shipment_ref: str) -> list[dict]:
        return []  # mock events are seeded directly in demo data


class MockOCRProvider:
    name = "mock"

    def extract_text(self, filename: str) -> str:
        return ""  # placeholder; real OCR added via OCRProvider later
