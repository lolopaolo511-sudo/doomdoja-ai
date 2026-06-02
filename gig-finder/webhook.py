"""Dostarczenie raportu przez Make.com webhook.

Jeśli MAKE_WEBHOOK_URL jest ustawiony w .env → wysyła POST z danymi TOP N gigs.
Jeśli nie ma URL → dry-run: wyświetla payload który byłby wysłany.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from reporter import RankedGig


def deliver(ranked: list[RankedGig], report_paths: dict[str, Path], date_str: str) -> str:
    url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    dry_run = not url

    payload = _build_payload(ranked, report_paths, date_str)

    if dry_run:
        print("\n[webhook] DRY-RUN — MAKE_WEBHOOK_URL nie ustawiony w .env")
        print("[webhook] Payload który byłby wysłany:")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
        print("[webhook] Aby podpiąć Make.com:")
        print("  1. Utwórz scenariusz w Make.com z triggerem 'Custom Webhook'")
        print("  2. Skopiuj URL webhooka do .env: MAKE_WEBHOOK_URL=https://hook.eu1.make.com/...")
        print("  3. Uruchom ponownie — dane zostaną wysłane automatycznie")
        return "dry-run"

    try:
        r = httpx.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[webhook] Wysłano do Make.com → {r.status_code}")
        return f"sent:{r.status_code}"
    except Exception as e:
        print(f"[webhook] Błąd wysyłania: {e}")
        return f"error:{e}"


def _build_payload(ranked: list[RankedGig], report_paths: dict[str, Path], date_str: str) -> dict:
    top_gigs = []
    for i, item in enumerate(ranked[:15], 1):
        top_gigs.append({
            "rank": i,
            "title": item.gig.title,
            "url": item.gig.url,
            "source": item.gig.source,
            "budget": item.gig.budget,
            "fit": item.score.fit,
            "why_fits": item.score.why_fits,
            "offer_angle": item.score.offer_angle,
            "posted_at": item.gig.posted_at,
        })

    report_paths_str = {k: str(v) for k, v in report_paths.items()}

    return {
        "report_date": date_str,
        "top_gigs": top_gigs,
        "total_ranked": len(ranked),
        "report_files": report_paths_str,
        "source": "doomdoja-gig-finder",
    }
