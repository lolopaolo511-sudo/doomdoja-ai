#!/usr/bin/env python3
"""
Demo end-to-end: pobierz ogłoszenia → score → proposal → log do Airtable.

Uruchomienie:
  cd ~/qwen-agent/prospecting && python run_prospecting.py
  python run_prospecting.py --no-llm          # szybki tryb: heurystyka zamiast LLM
  python run_prospecting.py --min-fit 7       # tylko ogłoszenia z fit >= 7
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

# allow sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from job_source import get_jobs
from scorer import score_job
from proposer import generate_proposal
from airtable_logger import log_prospect


def load_config() -> dict:
    cfg_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text())


def run(min_fit: int = 6, use_llm: bool = True) -> None:
    cfg = load_config()
    profile = cfg["profile"]

    print("=" * 60)
    print("PROSPECTING AGENT — START")
    print("=" * 60)

    jobs, source = get_jobs(cfg)
    print(f"\n[źródło] {source} — {len(jobs)} ogłoszeń\n")

    results = []
    for job in jobs:
        score = score_job(job, profile, use_llm=use_llm)
        apply = score.fit >= min_fit and score.should_apply

        print(f"{'✓' if apply else '✗'} [{score.fit}/10 fit | {score.intent}/10 intent] {job.title}")
        print(f"   Budget: {job.budget}")
        print(f"   Reasoning: {score.reasoning}")

        if apply:
            print("   → Generuję proposal...")
            proposal = generate_proposal(job, score, profile)
            print(f"   PROPOSAL:\n{'-'*40}")
            for line in proposal.split("\n"):
                print(f"   {line}")
            print("-" * 40)

            log_result = log_prospect(
                job_id=job.id,
                job_title=job.title,
                job_url=job.url,
                fit=score.fit,
                intent=score.intent,
                proposal_draft=proposal,
                cfg=cfg,
            )
            print(f"   {log_result}")
        else:
            proposal = ""

        results.append({
            "id": job.id,
            "title": job.title,
            "budget": job.budget,
            "fit": score.fit,
            "intent": score.intent,
            "should_apply": apply,
            "proposal_snippet": proposal[:200] if proposal else "",
        })
        print()

    # summary
    applied = [r for r in results if r["should_apply"]]
    print("=" * 60)
    print(f"PODSUMOWANIE: {len(applied)}/{len(results)} ogłoszeń kwalifikuje się")
    print("=" * 60)

    out_path = Path(__file__).parent / "results_latest.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Wyniki zapisane → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-fit", type=int, default=6)
    parser.add_argument("--no-llm", action="store_true", help="Użyj heurystyki zamiast LLM")
    args = parser.parse_args()
    run(min_fit=args.min_fit, use_llm=not args.no_llm)
