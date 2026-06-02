"""SearxNG adapter — lokalny serwis :8888, time_range=week, bez zewnętrznych zależności."""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone

import httpx

from . import Gig

_EXCLUDE_DOMAINS = [
    "linkedin.com", "cataloxy.pl", "pracuj.pl", "rocketjobs.pl",
    "goldenline.pl", "nofluffjobs.com", "justjoin.it", "indeed.com",
    "glassdoor.com", "monster.com",
]


def fetch(cfg: dict) -> list[Gig]:
    base_url = cfg.get("url", "http://localhost:8888")
    queries = cfg.get("queries", ["python scraping freelance"])
    max_per_query = cfg.get("max_per_query", 5)

    gigs: list[Gig] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            time.sleep(0.5)
            r = httpx.get(
                f"{base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "engines": "google,bing,duckduckgo",
                    "time_range": "week",
                },
                timeout=12,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as e:
            print(f"[searxng] błąd dla query='{query}': {e}")
            continue

        count = 0
        for res in results:
            if count >= max_per_query:
                break
            url = res.get("url", "")
            if not url or url in seen_urls:
                continue
            if _is_blocked(url):
                continue
            title = res.get("title", "")
            content = res.get("content", "")
            if not _looks_like_job(title, content):
                continue
            seen_urls.add(url)

            pub_date = res.get("publishedDate") or res.get("published_date") or ""
            posted_dt = _parse_date(pub_date)

            uid = hashlib.md5(url.encode()).hexdigest()[:12]
            gigs.append(Gig(
                id=f"sx_{uid}",
                title=title[:120],
                url=url,
                description=(content or "")[:800],
                budget=_extract_budget(content),
                source=f"SearxNG ({res.get('engine','?')})",
                posted_at=pub_date[:10] if pub_date else "",
                posted_dt=posted_dt,
                tags=[],
            ))
            count += 1

    return gigs


def _is_blocked(url: str) -> bool:
    low = url.lower()
    return any(d in low for d in _EXCLUDE_DOMAINS)


def _looks_like_job(title: str, content: str) -> bool:
    job_signals = [
        "freelance", "job", "hiring", "developer", "remote", "contract",
        "upwork", "toptal", "fiverr", "we're looking", "we are looking",
        "position", "opportunity", "role", "project", "need a",
    ]
    text = (title + " " + content).lower()
    return any(s in text for s in job_signals)


def _is_aggregator(url: str) -> bool:
    aggregator_domains = [
        "linkedin.com", "cataloxy.pl", "pracuj.pl", "rocketjobs.pl",
        "goldenline.pl", "nofluffjobs.com", "justjoin.it",
    ]
    return any(d in url.lower() for d in aggregator_domains)


def _extract_budget(text: str) -> str:
    if not text:
        return "n/a"
    m = re.search(r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:/\w+)?", text)
    return m.group(0) if m else "n/a"


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d",
                "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
