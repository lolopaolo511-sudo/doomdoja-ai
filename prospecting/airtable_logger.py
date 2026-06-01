"""
Airtable logger — dry-run (bez PAT) lub live.

DRY-RUN MODE (domyślny):
  Zapisuje do lokalnego pliku JSON zamiast do Airtable.
  Uruchom z AIRTABLE_PAT w .env żeby przełączyć na live.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import httpx

_LOG_FILE = Path(__file__).parent / "airtable_dryrun_log.jsonl"


def _dry_run_log(record: dict) -> str:
    entry = {"ts": datetime.now().isoformat(), **record}
    with _LOG_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return f"[DRY-RUN] Zalogowano lokalnie → {_LOG_FILE.name}"


def _live_log(record: dict, pat: str, base_id: str, table: str) -> str:
    url = f"https://api.airtable.com/v0/{base_id}/{table}"
    payload = {"fields": record}
    r = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    rec_id = r.json().get("id", "?")
    return f"[AIRTABLE] Zapisano rekord {rec_id}"


def log_prospect(
    job_id: str,
    job_title: str,
    job_url: str,
    fit: int,
    intent: int,
    proposal_draft: str,
    cfg: dict,
) -> str:
    record = {
        "Job ID": job_id,
        "Title": job_title,
        "URL": job_url,
        "Fit Score": fit,
        "Intent Score": intent,
        "Total Score": fit + intent,
        "Proposal Draft": proposal_draft[:500],
        "Status": "Draft",
        "Created": datetime.now().isoformat(),
    }

    pat = os.getenv("AIRTABLE_PAT", "")
    base_id = os.getenv("AIRTABLE_BASE_ID", cfg.get("airtable", {}).get("base_id", ""))
    table = cfg.get("airtable", {}).get("table_name", "Prospects")
    dry_run = cfg.get("airtable", {}).get("dry_run", True)

    if dry_run or not pat:
        return _dry_run_log(record)
    try:
        return _live_log(record, pat, base_id, table)
    except Exception as e:
        return f"[AIRTABLE ERROR] {e} — fallback do dry-run\n" + _dry_run_log(record)
