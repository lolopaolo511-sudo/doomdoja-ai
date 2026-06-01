"""
Job source adapter — mock lub RSS (Upwork).

OGRANICZENIE: Upwork nie udostępnia ogłoszeń publicznie bez logowania.
Adapter RSS działa TYLKO jeśli w .env ustawiony jest UPWORK_COOKIE
(session cookie z zalogowanej sesji przeglądarki).
Bez niego automatycznie używany jest mock.

Jak podpiąć realne źródło:
  1. Zaloguj się na Upwork w przeglądarce.
  2. Otwórz DevTools → Application → Cookies → www.upwork.com.
  3. Skopiuj wartość cookie 'user_uid' + 'OAuth2AccessToken' (lub cały header)
     do .env jako UPWORK_COOKIE="oauth2v2_xxx...; user_uid=xxx"
  4. Ustaw use_mock: false w config.yaml.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime

import httpx


@dataclass
class Job:
    id: str
    title: str
    description: str
    budget: str
    posted_at: str
    url: str
    skills_mentioned: list[str] = field(default_factory=list)


MOCK_JOBS: list[dict] = [
    {
        "id": "mock-001",
        "title": "Python scraper for e-commerce product data",
        "description": "Need a reliable Python scraper for 50k product pages. "
                       "Must handle JS rendering, pagination, rate limits. "
                       "Data to Airtable. Budget flexible for quality.",
        "budget": "$500-1500",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-001",
    },
    {
        "id": "mock-002",
        "title": "AI automation agent for lead generation",
        "description": "Looking for an AI/LLM agent that can search LinkedIn, "
                       "score leads, and draft personalized outreach. Python, "
                       "n8n or similar. Long term collaboration possible.",
        "budget": "$1000-3000",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-002",
    },
    {
        "id": "mock-003",
        "title": "Invoice OCR and data extraction pipeline",
        "description": "We receive 500+ invoices/month as PDF/images. Need "
                       "automated extraction of fields (vendor, amount, date, "
                       "line items) to Google Sheets or Airtable.",
        "budget": "$800-2000",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-003",
    },
    {
        "id": "mock-004",
        "title": "Shopify product migration + scraping",
        "description": "Migrate 10k products from old website to Shopify. "
                       "Need scraper + data cleaning + import script.",
        "budget": "$300-600",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-004",
    },
    {
        "id": "mock-005",
        "title": "WordPress developer for landing page",
        "description": "Need WordPress only developer to build landing page "
                       "with Elementor. No coding required.",
        "budget": "$100-200",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-005",
    },
    {
        "id": "mock-006",
        "title": "Data pipeline: scrape → clean → report (Python)",
        "description": "Build end-to-end data pipeline: scrape competitor "
                       "pricing daily, clean with pandas, generate Excel "
                       "report + email. FastAPI endpoint for on-demand runs.",
        "budget": "$1500-4000",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-006",
    },
    {
        "id": "mock-007",
        "title": "React Native mobile app for iOS",
        "description": "Build a React Native app for restaurant ordering. "
                       "Firebase backend, Stripe payments.",
        "budget": "$2000-5000",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-007",
    },
    {
        "id": "mock-008",
        "title": "LLM document processor — CV parsing service",
        "description": "Build a FastAPI service that accepts CV uploads "
                       "(PDF/image) and returns structured JSON (name, skills, "
                       "experience). Use any local or cloud LLM. "
                       "Integrate with our ATS via REST.",
        "budget": "$700-2500",
        "posted_at": "2026-06-01",
        "url": "https://www.upwork.com/jobs/mock-008",
    },
]


def fetch_mock(count: int = 8) -> list[Job]:
    return [Job(**{k: v for k, v in j.items()}) for j in MOCK_JOBS[:count]]


def fetch_rss(query: str, max_jobs: int = 20, cookie: str = "") -> list[Job]:
    """Fetch from Upwork RSS. Requires session cookie for most searches."""
    url = "https://www.upwork.com/ab/feed/jobs/rss"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = httpx.get(url, params={"q": query, "sort": "recency"}, headers=headers, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
        jobs = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            desc = item.findtext("description", "") or item.findtext(f"{{{ns['content']}encoded}}", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", datetime.now().isoformat())
            guid = item.findtext("guid", link)
            jobs.append(Job(
                id=guid[-20:] if guid else "rss-" + str(len(jobs)),
                title=title,
                description=desc[:1000],
                budget="N/A (see listing)",
                posted_at=pub,
                url=link,
            ))
            if len(jobs) >= max_jobs:
                break
        return jobs
    except Exception as e:
        print(f"[RSS] Błąd: {e} — fallback do mock")
        return fetch_mock()


def get_jobs(cfg: dict) -> tuple[list[Job], str]:
    """Returns (jobs, source_label)."""
    src = cfg.get("source", {})
    cookie = os.getenv("UPWORK_COOKIE", "")
    if src.get("use_mock", True) or not cookie:
        jobs = fetch_mock(src.get("mock_count", 8))
        label = "MOCK (use_mock=true lub brak UPWORK_COOKIE)"
        if not cookie and not src.get("use_mock", True):
            print("[!] UPWORK_COOKIE nie ustawiony — używam mock. "
                  "Ustaw cookie w .env dla realnych ogłoszeń.")
        return jobs, label
    jobs = fetch_rss(src.get("rss_query", "python automation"), src.get("rss_max_jobs", 20), cookie)
    return jobs, "Upwork RSS"
