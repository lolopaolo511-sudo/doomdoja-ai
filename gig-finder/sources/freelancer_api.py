"""Freelancer.com API adapter — wymaga FREELANCER_TOKEN w .env.

JAK UZYSKAĆ TOKEN:
1. Idź na https://www.freelancer.com/developers/
2. Zaloguj się i utwórz aplikację → uzyskasz OAuth token
3. Wpisz do .env: FREELANCER_TOKEN=<token>
4. Ustaw freelancer_api.enabled: true w config.yaml
"""
from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone

import httpx

from . import Gig

_BASE = "https://www.freelancer.com/api/projects/0.1/projects/active/"
_KEYWORDS = [
    "scraping", "web scraper", "automation", "make.com", "zapier",
    "airtable", "data extraction", "python", "OCR", "data pipeline",
]


def fetch(cfg: dict) -> list[Gig]:
    token = os.getenv("FREELANCER_TOKEN", "")
    if not token:
        print("[freelancer] BRAK FREELANCER_TOKEN w .env — adapter pominięty")
        return []

    queries = cfg.get("queries", _KEYWORDS[:4])
    max_jobs = cfg.get("max_jobs", 30)
    headers = {
        "Freelancer-OAuth-V1": token,
        "Content-Type": "application/json",
    }

    gigs: list[Gig] = []
    seen: set[str] = set()

    for query in queries:
        if len(gigs) >= max_jobs:
            break
        try:
            time.sleep(0.5)
            r = httpx.get(
                _BASE,
                params={
                    "query": query,
                    "project_types[]": "fixed",
                    "job_details": "true",
                    "limit": 20,
                    "offset": 0,
                    "sort_field": "time_submitted",
                    "reverse_sort": "false",
                },
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[freelancer] błąd dla query='{query}': {e}")
            continue

        projects = data.get("result", {}).get("projects", [])
        for proj in projects:
            pid = str(proj.get("id", ""))
            if not pid or pid in seen:
                continue
            seen.add(pid)

            submit_ts = proj.get("time_submitted") or proj.get("submitdate")
            posted_dt = datetime.fromtimestamp(submit_ts, tz=timezone.utc) if submit_ts else None
            posted_at = posted_dt.strftime("%Y-%m-%d") if posted_dt else ""

            budget = _extract_budget(proj)
            title = proj.get("title", "")
            desc = proj.get("description", "")[:1200]
            url = f"https://www.freelancer.com/projects/{proj.get('seo_url', pid)}"

            gigs.append(Gig(
                id=f"fl_{hashlib.md5(pid.encode()).hexdigest()[:12]}",
                title=title,
                url=url,
                description=desc,
                budget=budget,
                source="Freelancer.com",
                posted_at=posted_at,
                posted_dt=posted_dt,
                open_status="otwarte",
                tags=[j.get("name", "") for j in proj.get("jobs", [])[:8]],
            ))

    return gigs[:max_jobs]


def _extract_budget(proj: dict) -> str:
    budget = proj.get("budget", {})
    lo = budget.get("minimum")
    hi = budget.get("maximum")
    currency = budget.get("currency", {}).get("sign", "$")
    if lo and hi:
        return f"{currency}{lo:.0f}–{currency}{hi:.0f}"
    if lo:
        return f"{currency}{lo:.0f}+"
    return "n/a"
