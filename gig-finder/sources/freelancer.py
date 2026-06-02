"""Freelancer.com adapter — public projects API.

Wymaga tokena OAuth do pełnych wyników.
Bez tokena próbuje publicznych endpointów i łapie błąd gracefully.

Konfiguracja:
  1. Zarejestruj app: https://developers.freelancer.com/
  2. Wpisz FREELANCER_OAUTH_TOKEN do .env
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx

from . import Gig

_BASE = "https://www.freelancer.com/api/projects/0.1/projects/active/"
_SEARCH_QUERIES = [
    "python web scraping",
    "data extraction automation",
    "airtable n8n automation",
    "lead generation scraper",
]


def fetch(cfg: dict) -> list[Gig]:
    max_jobs = cfg.get("max_jobs", 20)
    token = os.environ.get("FREELANCER_OAUTH_TOKEN", "")

    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (compatible; gig-finder/1.0)",
        "Accept": "application/json",
    }
    if token:
        headers["Freelancer-OAuth-V1"] = token

    gigs: list[Gig] = []
    seen: set[str] = set()

    for query in _SEARCH_QUERIES:
        try:
            r = httpx.get(
                _BASE,
                params={
                    "query": query,
                    "limit": 10,
                    "offset": 0,
                    "job_details": "true",
                    "full_description": "true",
                    "compact": "true",
                },
                headers=headers,
                timeout=15,
                follow_redirects=True,
            )
            r.raise_for_status()
            result = r.json().get("result", {})
            projects = result.get("projects", [])
        except Exception as e:
            status = getattr(e, "response", None)
            code = status.status_code if status else "?"
            if code in (401, 403):
                print(f"[freelancer] wymaga FREELANCER_OAUTH_TOKEN w .env (HTTP {code})")
            else:
                print(f"[freelancer] błąd dla query='{query}': {e}")
            break

        for proj in projects:
            pid = str(proj.get("id", ""))
            if not pid or pid in seen:
                continue
            seen.add(pid)

            submitdate = proj.get("submitdate", 0)
            posted_dt = datetime.fromtimestamp(submitdate, tz=timezone.utc) if submitdate else None
            posted_at = posted_dt.strftime("%Y-%m-%d") if posted_dt else ""

            seo_url = proj.get("seo_url", pid)
            url = f"https://www.freelancer.com/projects/{seo_url}"

            gigs.append(Gig(
                id=f"fl_{pid}",
                title=proj.get("title", ""),
                url=url,
                description=(proj.get("description") or "")[:1200],
                budget=_extract_budget(proj),
                source="Freelancer.com",
                posted_at=posted_at,
                posted_dt=posted_dt,
                tags=[j.get("name", "") for j in proj.get("jobs", []) if j.get("name")],
            ))

        if len(gigs) >= max_jobs:
            break

    return gigs[:max_jobs]


def _extract_budget(proj: dict) -> str:
    budget = proj.get("budget") or {}
    lo = budget.get("minimum")
    hi = budget.get("maximum")
    sign = (proj.get("currency") or {}).get("sign", "$")
    if lo and hi:
        return f"{sign}{int(lo)}–{sign}{int(hi)}"
    if lo:
        return f"{sign}{int(lo)}+"
    return "n/a"
