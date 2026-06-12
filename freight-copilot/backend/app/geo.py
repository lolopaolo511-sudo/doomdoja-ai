"""Offline geographic distance estimation for European road freight.

Used by the pricing agent and the mock distance provider so that *any* lane —
not just a hand-coded handful — gets a realistic distance without an external
maps API. A road-winding factor converts great-circle distance into an
approximate driving distance. This is clearly an estimate (see ASSUMPTIONS.md);
plug in an authorised DistanceProvider for exact tolled routing later.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# Major European freight hubs (lat, lon). Lowercased keys for lookup.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "warsaw": (52.2297, 21.0122),
    "warszawa": (52.2297, 21.0122),
    "poznań": (52.4064, 16.9252),
    "poznan": (52.4064, 16.9252),
    "wrocław": (51.1079, 17.0385),
    "wroclaw": (51.1079, 17.0385),
    "kraków": (50.0647, 19.9450),
    "krakow": (50.0647, 19.9450),
    "łódź": (51.7592, 19.4560),
    "lodz": (51.7592, 19.4560),
    "katowice": (50.2649, 19.0238),
    "gdansk": (54.3520, 18.6466),
    "gdańsk": (54.3520, 18.6466),
    "milan": (45.4642, 9.1900),
    "milano": (45.4642, 9.1900),
    "verona": (45.4384, 10.9916),
    "turin": (45.0703, 7.6869),
    "torino": (45.0703, 7.6869),
    "rome": (41.9028, 12.4964),
    "roma": (41.9028, 12.4964),
    "bologna": (44.4949, 11.3426),
    "naples": (40.8518, 14.2681),
    "berlin": (52.5200, 13.4050),
    "munich": (48.1351, 11.5820),
    "münchen": (48.1351, 11.5820),
    "hamburg": (53.5511, 9.9937),
    "frankfurt": (50.1109, 8.6821),
    "cologne": (50.9375, 6.9603),
    "köln": (50.9375, 6.9603),
    "stuttgart": (48.7758, 9.1829),
    "prague": (50.0755, 14.4378),
    "praha": (50.0755, 14.4378),
    "brno": (49.1951, 16.6068),
    "vienna": (48.2082, 16.3738),
    "wien": (48.2082, 16.3738),
    "bratislava": (48.1486, 17.1077),
    "budapest": (47.4979, 19.0402),
    "paris": (48.8566, 2.3522),
    "lyon": (45.7640, 4.8357),
    "marseille": (43.2965, 5.3698),
    "barcelona": (41.3851, 2.1734),
    "madrid": (40.4168, -3.7038),
    "amsterdam": (52.3676, 4.9041),
    "rotterdam": (51.9244, 4.4777),
    "brussels": (50.8503, 4.3517),
    "antwerp": (51.2194, 4.4025),
    "zurich": (47.3769, 8.5417),
    "ljubljana": (46.0569, 14.5058),
    "zagreb": (45.8150, 15.9819),
}

# Great-circle → road distance multiplier (European motorway average).
ROAD_FACTOR = 1.27


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(h))


def estimate_distance_km(origin: str | None, destination: str | None) -> float | None:
    """Approximate road distance between two cities, or None if either is unknown."""
    if not origin or not destination:
        return None
    a = CITY_COORDS.get(origin.strip().lower())
    b = CITY_COORDS.get(destination.strip().lower())
    if not a or not b:
        return None
    return round(_haversine_km(a, b) * ROAD_FACTOR)
