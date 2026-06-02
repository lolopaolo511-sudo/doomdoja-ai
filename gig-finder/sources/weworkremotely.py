"""WeWorkRemotely RSS adapter — publiczne RSS, bez logowania."""
from __future__ import annotations

import hashlib

import feedparser
import httpx

from . import Gig

_RSS_URLS = {
    "programming": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "data": "https://weworkremotely.com/categories/remote-data-science-jobs.rss",
    "devops": "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
}


def fetch(cfg: dict) -> list[Gig]:
    categories = cfg.get("categories", ["programming"])
    max_jobs = cfg.get("max_jobs", 30)
    gigs: list[Gig] = []
    seen: set[str] = set()

    for cat in categories:
        url = _RSS_URLS.get(cat)
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[wwr] błąd dla category={cat}: {e}")
            continue

        for entry in feed.entries:
            link = entry.get("link", "")
            if link in seen:
                continue
            seen.add(link)

            raw_title = entry.get("title", "")
            # WWR tytuły mają format: "Company: Role - Location"
            title = raw_title.split(": ", 1)[-1].split(" - ")[0].strip() if ": " in raw_title else raw_title
            company = raw_title.split(": ")[0].strip() if ": " in raw_title else ""

            description = _clean(entry.get("summary", ""))
            entry_id = hashlib.md5(link.encode()).hexdigest()[:12]

            gigs.append(Gig(
                id=f"wwr_{entry_id}",
                title=title,
                url=link,
                description=f"{company}\n{description}" if company else description,
                budget="n/a",
                source="WeWorkRemotely",
                posted_at=entry.get("published", ""),
                tags=_extract_tags(entry),
            ))

        if len(gigs) >= max_jobs:
            break

    return gigs[:max_jobs]


def _clean(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:1200]


def _extract_tags(entry: dict) -> list[str]:
    tags = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "")
        if term:
            tags.append(term)
    return tags
