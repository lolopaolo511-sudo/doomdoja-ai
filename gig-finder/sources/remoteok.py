"""RemoteOK API adapter — publiczne API, bez logowania."""
from __future__ import annotations

import hashlib
import time

import httpx

from . import Gig

_BASE = "https://remoteok.com/api"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


def fetch(cfg: dict) -> list[Gig]:
    tags = cfg.get("tags", ["python", "data"])
    max_jobs = cfg.get("max_jobs", 50)
    gigs: list[Gig] = []
    seen: set[str] = set()

    for tag in tags:
        try:
            time.sleep(1)  # rate-limit — RemoteOK prosi o 1s między requestami
            r = httpx.get(f"{_BASE}?tag={tag}", headers=_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[remoteok] błąd dla tag={tag}: {e}")
            continue

        for job in data:
            if not isinstance(job, dict) or not job.get("id"):
                continue
            job_id = str(job["id"])
            if job_id in seen:
                continue
            seen.add(job_id)

            budget = _extract_budget(job)
            gigs.append(Gig(
                id=f"rok_{job_id}",
                title=job.get("position", ""),
                url=job.get("url", f"https://remoteok.com/l/{job_id}"),
                description=_clean(job.get("description", "")),
                budget=budget,
                source="RemoteOK",
                posted_at=job.get("date", ""),
                tags=job.get("tags", []),
            ))

        if len(gigs) >= max_jobs:
            break

    return gigs[:max_jobs]


def _extract_budget(job: dict) -> str:
    lo = job.get("salary_min") or job.get("salary")
    hi = job.get("salary_max")
    if lo and hi:
        return f"${lo:,}–${hi:,}/yr"
    if lo:
        return f"${lo:,}/yr"
    return "n/a"


def _clean(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:1200]
