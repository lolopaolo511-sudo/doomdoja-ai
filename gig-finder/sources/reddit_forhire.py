"""Reddit r/forhire adapter — Atom RSS feed (bez logowania).

Pobiera posty [Hiring] z r/forhire/new — to są zleceniodawcy szukający freelancerów.
JSON API wymaga OAuth; RSS jest publiczne.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import feedparser

from . import Gig

_RSS_URL = "https://www.reddit.com/r/forhire/new/.rss"
_HEADERS = {"User-Agent": "feedparser/6.0 (gig-finder)"}


def fetch(cfg: dict) -> list[Gig]:
    max_posts = cfg.get("max_posts", 50)
    gigs: list[Gig] = []

    try:
        feed = feedparser.parse(_RSS_URL, request_headers=_HEADERS)
        entries = feed.entries
    except Exception as e:
        print(f"[reddit_forhire] błąd: {e}")
        return []

    for entry in entries:
        title = entry.get("title", "")

        # Tylko [Hiring] — pomijamy [For Hire]
        if not re.match(r"\[(Hiring|HIRING|hiring)\]", title):
            continue

        link = entry.get("link", "")
        if not link:
            continue

        # Parsuj datę — feedparser daje published_parsed jako time.struct_time
        parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        posted_dt = _from_struct(parsed_struct)
        posted_at = posted_dt.strftime("%Y-%m-%d") if posted_dt else ""

        # Treść ogłoszenia z HTML
        content_html = ""
        if entry.get("content"):
            content_html = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            content_html = entry["summary"]
        description = _clean_html(content_html)[:1200]

        entry_id = hashlib.md5(link.encode()).hexdigest()[:12]

        gigs.append(Gig(
            id=f"rdt_{entry_id}",
            title=title[:120],
            url=link,
            description=description,
            budget=_extract_budget(description + " " + title),
            source="Reddit r/forhire",
            posted_at=posted_at,
            posted_dt=posted_dt,
            tags=_extract_tags(description + " " + title),
        ))

        if len(gigs) >= max_posts:
            break

    return gigs


def _from_struct(ts) -> datetime | None:
    if ts is None:
        return None
    import calendar
    try:
        return datetime.fromtimestamp(calendar.timegm(ts), tz=timezone.utc)
    except Exception:
        return None


def _clean_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_budget(text: str) -> str:
    m = re.search(r"\$[\d,]+(?:\s*[-–/]\s*\$?[\d,]+)?(?:/\w+)?", text)
    return m.group(0) if m else "n/a"


def _extract_tags(text: str) -> list[str]:
    tech = [
        "python", "javascript", "typescript", "go", "rust",
        "scraping", "automation", "data", "playwright", "selenium",
        "airtable", "zapier", "n8n", "make.com", "AI", "LLM",
    ]
    low = text.lower()
    return [t for t in tech if t.lower() in low]
