"""HackerNews 'Who is hiring' adapter — Algolia HN API, bez logowania.

Pobiera komentarze z miesięcznego wątku 'Ask HN: Who is hiring?'
i filtruje według słów kluczowych z config.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import httpx

from . import Gig


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

_ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
_HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
_HN_URL = "https://news.ycombinator.com/item?id={}"


def fetch(cfg: dict) -> list[Gig]:
    keywords = cfg.get("keywords", ["scraping", "python", "automation"])
    max_comments = cfg.get("max_comments", 100)

    thread_id = _find_latest_hiring_thread()
    if not thread_id:
        print("[hn_hiring] Nie znaleziono wątku 'Who is hiring'")
        return []

    print(f"[hn_hiring] Wątek: https://news.ycombinator.com/item?id={thread_id}")
    comments = _fetch_filtered_comments(thread_id, keywords, max_comments)

    gigs = []
    for c in comments:
        text = c.get("text", "")
        if not text or len(text) < 50:
            continue

        cid = str(c.get("objectID", c.get("id", "")))
        title = _extract_title(text)
        gig_id = hashlib.md5(cid.encode()).hexdigest()[:12]
        created_at = c.get("created_at", "")

        gigs.append(Gig(
            id=f"hn_{gig_id}",
            title=title,
            url=_HN_URL.format(cid),
            description=_clean_html(text)[:1200],
            budget=_extract_salary(text),
            source="HN: Who Is Hiring",
            posted_at=created_at[:10] if created_at else "",
            posted_dt=_parse_iso(created_at),
            tags=_extract_tech_tags(text),
        ))

    return gigs


def _find_latest_hiring_thread() -> str | None:
    """Znajdź ID najnowszego wątku 'Ask HN: Who is hiring?'."""
    try:
        r = httpx.get(
            _ALGOLIA_SEARCH,
            params={
                "query": "Ask HN: Who is hiring",
                "tags": "ask_hn",
                "hitsPerPage": 10,
            },
            timeout=10,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        # Szukaj wątku z 2025 lub 2026
        for hit in hits:
            title = hit.get("title", "")
            created = hit.get("created_at", "")
            if "who is hiring" in title.lower() and ("2025" in created or "2026" in created):
                return hit.get("objectID")
        # Fallback: najnowszy pasujący
        for hit in hits:
            if "who is hiring" in hit.get("title", "").lower():
                return hit.get("objectID")
    except Exception as e:
        print(f"[hn_hiring] błąd szukania wątku: {e}")
    return None


def _fetch_filtered_comments(thread_id: str, keywords: list[str], max_comments: int) -> list[dict]:
    """Pobierz komentarze z wątku filtrowane po słowach kluczowych."""
    try:
        r = httpx.get(
            _ALGOLIA_SEARCH,
            params={
                "tags": f"comment,story_{thread_id}",
                "hitsPerPage": max_comments,
            },
            timeout=15,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as e:
        print(f"[hn_hiring] błąd pobierania komentarzy: {e}")
        return []

    kw_lower = [k.lower() for k in keywords]
    matched = []
    for hit in hits:
        text = (hit.get("comment_text") or hit.get("text") or "").lower()
        if any(kw in text for kw in kw_lower):
            hit["text"] = hit.get("comment_text") or hit.get("text") or ""
            matched.append(hit)

    return matched


def _extract_title(text: str) -> str:
    clean = _clean_html(text)
    # Pierwsza linia zwykle zawiera nazwę firmy + rolę
    first_line = clean.split("\n")[0].strip()
    if "|" in first_line:
        parts = first_line.split("|")
        return f"{parts[0].strip()} | {parts[1].strip()}"
    return first_line[:120] if first_line else "HN Job Posting"


def _extract_salary(text: str) -> str:
    clean = _clean_html(text)
    patterns = [
        r"\$(\d{2,3}[Kk])\s*[-–]\s*\$?(\d{2,3}[Kk])",
        r"\$(\d{2,3},\d{3})\s*[-–]\s*\$?(\d{2,3},\d{3})",
        r"(\d{2,3}[Kk])\s*[-–]\s*(\d{2,3}[Kk])\s*(?:USD|salary|comp)",
        r"\$(\d{2,3}[Kk])\+",
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            return m.group(0)
    return "n/a"


def _extract_tech_tags(text: str) -> list[str]:
    tech_words = [
        "python", "javascript", "typescript", "go", "rust", "java", "scala",
        "remote", "full-time", "part-time", "contract", "freelance",
        "scraping", "automation", "data", "ML", "AI",
    ]
    clean = _clean_html(text).lower()
    return [t for t in tech_words if t.lower() in clean]


def _clean_html(html: str) -> str:
    text = re.sub(r"<p>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#x27;", "'", text)
    text = re.sub(r"\s{3,}", "\n", text)
    return text.strip()
