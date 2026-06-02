"""Upwork RSS adapter.

OGRANICZENIE: Upwork nie udostępnia ogłoszeń publicznie bez logowania.
Ten adapter wymaga UPWORK_RSS_URL w .env — adresu RSS z zalogowanej sesji.

JAK PODPIĄĆ UPWORK RSS:
═══════════════════════
1. Zaloguj się na Upwork w przeglądarce Chrome/Firefox.

2. Przejdź do wyszukiwania ogłoszeń, np.:
   https://www.upwork.com/nx/find-work/best-matches

3. Ustaw filtry: Category, Skills, Budget (np. >$500)

4. Otwórz DevTools (F12) → Network → wyczyść logi → odśwież stronę.

5. Wyszukaj request do URL zawierającego "/ab/feed/jobs/rss" lub "/api/feeds/v1".
   Skopiuj pełny URL razem z parametrami i cookies.

   Alternatywnie: Saved Search RSS
   - Zapisz wyszukanie jako "Saved Search" na Upwork
   - URL RSS będzie w formacie:
     https://www.upwork.com/ab/feed/jobs/rss?q=...&sort=recency&paging=...
   - Kopiując URL bezpośrednio po zalogowaniu masz session cookie w przeglądarce.
   - Ustaw UPWORK_RSS_URL=<ten URL> w .env

6. UPWORK_COOKIE (opcjonalne, dla lepszej autoryzacji):
   DevTools → Application → Cookies → www.upwork.com
   Skopiuj cookies: "OAuth2AccessToken", "user_uid", "visitor_id"
   Złącz je jako: "OAuth2AccessToken=xxx; user_uid=yyy"
   Wpisz do .env: UPWORK_COOKIE=<wartość>

7. W config.yaml ustaw: upwork_rss.enabled: true

UWAGA: Session cookies wygasają (zwykle po 30 dniach).
       Trzeba je odnowić po wygaśnięciu.
"""
from __future__ import annotations

import hashlib
import os
import re

import feedparser

from . import Gig


def fetch(cfg: dict) -> list[Gig]:
    rss_url = os.getenv("UPWORK_RSS_URL", "")
    cookie = os.getenv("UPWORK_COOKIE", "")

    if not rss_url:
        print("[upwork_rss] BRAK UPWORK_RSS_URL w .env — adapter pominięty")
        print("[upwork_rss] Przeczytaj docstring w sources/upwork_rss.py jak podpiąć RSS")
        return []

    max_jobs = cfg.get("max_jobs", 30)
    headers: dict = {}
    if cookie:
        headers["Cookie"] = cookie

    try:
        feed = feedparser.parse(rss_url, request_headers=headers)
    except Exception as e:
        print(f"[upwork_rss] błąd parsowania RSS: {e}")
        return []

    if not feed.entries:
        print("[upwork_rss] Pusty feed — sprawdź czy RSS URL jest aktualny i czy session cookie nie wygasło")
        return []

    gigs = []
    for entry in feed.entries[:max_jobs]:
        link = entry.get("link", "")
        uid = hashlib.md5(link.encode()).hexdigest()[:12]

        gigs.append(Gig(
            id=f"upw_{uid}",
            title=entry.get("title", ""),
            url=link,
            description=_clean(entry.get("summary", ""))[:1200],
            budget=_extract_budget(entry),
            source="Upwork",
            posted_at=entry.get("published", ""),
            tags=_extract_tags(entry),
        ))

    print(f"[upwork_rss] Pobrano {len(gigs)} ogłoszeń z Upwork RSS")
    return gigs


def _extract_budget(entry: dict) -> str:
    summary = entry.get("summary", "")
    patterns = [
        r"Budget:\s*\$?([\d,]+)",
        r"Hourly Rate:\s*\$?([\d.]+)\s*[-–]\s*\$?([\d.]+)",
        r"\$(\d[\d,]+)",
    ]
    for pat in patterns:
        m = re.search(pat, summary, re.IGNORECASE)
        if m:
            return m.group(0)
    return "n/a"


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_tags(entry: dict) -> list[str]:
    tags = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "")
        if term:
            tags.append(term)
    return tags
