"""SearxNG adapter — lokalny serwis :8888, bez zewnętrznych zależności."""
from __future__ import annotations

import hashlib
import re
import time

import httpx

from . import Gig


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
                params={"q": query, "format": "json", "engines": "google,bing,duckduckgo"},
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
            # Filtruj wyniki które wyglądają jak ogłoszenia
            title = res.get("title", "")
            content = res.get("content", "")
            if not _looks_like_job(title, content):
                continue
            seen_urls.add(url)

            uid = hashlib.md5(url.encode()).hexdigest()[:12]
            gigs.append(Gig(
                id=f"sx_{uid}",
                title=title[:120],
                url=url,
                description=(content or "")[:800],
                budget=_extract_budget(content),
                source=f"SearxNG ({res.get('engine','?')})",
                posted_at="",
                tags=[],
            ))
            count += 1

    return gigs


def _looks_like_job(title: str, content: str) -> bool:
    """Filtr: czy wynik wygląda jak ogłoszenie o pracę / zlecenie."""
    job_signals = [
        "freelance", "job", "hiring", "developer", "remote", "contract",
        "upwork", "toptal", "fiverr", "we're looking", "we are looking",
        "position", "opportunity", "role",
    ]
    text = (title + " " + content).lower()
    return any(s in text for s in job_signals)


def _extract_budget(text: str) -> str:
    if not text:
        return "n/a"
    m = re.search(r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:/\w+)?", text)
    return m.group(0) if m else "n/a"
