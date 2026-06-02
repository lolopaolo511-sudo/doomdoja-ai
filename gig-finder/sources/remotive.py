"""Remotive.com API adapter — publiczne API, bez logowania.

https://remotive.com/api/remote-jobs?search=python+scraping
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from . import Gig

_BASE = "https://remotive.com/api/remote-jobs"


def fetch(cfg: dict) -> list[Gig]:
    categories = cfg.get("categories", ["software-dev", "data"])
    max_jobs = cfg.get("max_jobs", 30)
    extra_search = cfg.get("search", "python scraping automation")
    gigs: list[Gig] = []
    seen: set[str] = set()

    for category in categories:
        try:
            r = httpx.get(
                _BASE,
                params={"category": category, "search": extra_search, "limit": max_jobs},
                timeout=15,
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"[remotive] błąd dla category={category}: {e}")
            continue

        for job in jobs:
            job_id = str(job.get("id", ""))
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)

            pub_date = job.get("publication_date", "")
            posted_dt = _parse_date(pub_date)

            salary = job.get("salary", "") or "n/a"

            gigs.append(Gig(
                id=f"rmv_{job_id}",
                title=job.get("title", ""),
                url=job.get("url", ""),
                description=_clean(job.get("description", ""))[:1200],
                budget=salary,
                source="Remotive",
                posted_at=pub_date[:10] if pub_date else "",
                posted_dt=posted_dt,
                tags=job.get("tags", []),
            ))

        if len(gigs) >= max_jobs:
            break

    return gigs[:max_jobs]


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
