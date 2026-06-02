#!/usr/bin/env python3
"""
Gig Finder — automatyczny skaner ogłoszeń freelancingowych.

Użycie:
  python run_gig_finder.py                     # pełne uruchomienie z LLM
  python run_gig_finder.py --no-llm            # heurystyka, szybko
  python run_gig_finder.py --top 10            # TOP 10 zamiast 15
  python run_gig_finder.py --threshold 7       # wyższy próg fit
  python run_gig_finder.py --no-webhook        # pomiń webhook
  python run_gig_finder.py --source remoteok   # tylko jedno źródło
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

_DIR = Path(__file__).parent
sys.path.insert(0, str(_DIR))

from sources import Gig
from sources import remoteok, weworkremotely, hn_hiring, upwork_rss, searxng
from sources import reddit_forhire, remotive, freelancer
from scorer import score, GigScore
from reporter import RankedGig, generate
from webhook import deliver


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or (_DIR / "config.yaml")
    return yaml.safe_load(cfg_path.read_text())


def load_env() -> None:
    env_candidates = [
        _DIR / ".env",
        _DIR.parent / ".env",
        Path.home() / "qwen-agent" / ".env",
    ]
    for p in env_candidates:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()
            break


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def filter_gigs(gigs: list[Gig], cfg: dict) -> list[Gig]:
    """Filtruj zablokowane domeny i stare ogłoszenia."""
    filters_cfg = cfg.get("filters", {})
    blocked = [d.lower() for d in filters_cfg.get("blocked_domains", [])]
    max_age = filters_cfg.get("max_age_days")

    result, blocked_count, stale_count = [], 0, 0

    for gig in gigs:
        dom = _domain(gig.url)
        if any(b in dom for b in blocked):
            blocked_count += 1
            continue

        if max_age is not None and gig.posted_dt is not None:
            age = gig.age_days()
            if age is not None and age > max_age:
                stale_count += 1
                continue

        result.append(gig)

    if blocked_count:
        print(f"→ Odfiltrowano (zablokowane domeny): {blocked_count}")
    if stale_count:
        print(f"→ Odfiltrowano (zbyt stare, >{max_age}d): {stale_count}")

    return result


def fetch_all(cfg: dict, only_source: str | None = None) -> tuple[list[Gig], list[str]]:
    all_gigs: list[Gig] = []
    sources_used: list[str] = []
    sources_cfg = cfg.get("sources", {})

    def run(name: str, adapter, src_cfg: dict):
        nonlocal all_gigs, sources_used
        if only_source and name != only_source:
            return
        if not src_cfg.get("enabled", False):
            print(f"[{name}] pominięty (enabled: false)")
            return
        print(f"[{name}] pobieranie...", end=" ", flush=True)
        try:
            gigs = adapter.fetch(src_cfg)
            print(f"{len(gigs)} ogłoszeń")
            all_gigs.extend(gigs)
            if gigs:
                sources_used.append(name)
        except Exception as e:
            print(f"BŁĄD: {e}")

    run("remoteok",      remoteok,       sources_cfg.get("remoteok", {}))
    run("weworkremotely",weworkremotely, sources_cfg.get("weworkremotely", {}))
    run("hn_hiring",     hn_hiring,      sources_cfg.get("hn_hiring", {}))
    run("upwork_rss",    upwork_rss,     sources_cfg.get("upwork_rss", {}))
    run("searxng",       searxng,        sources_cfg.get("searxng", {}))
    run("reddit_forhire",reddit_forhire, sources_cfg.get("reddit_forhire", {}))
    run("remotive",      remotive,       sources_cfg.get("remotive", {}))
    run("freelancer",    freelancer,     sources_cfg.get("freelancer", {}))

    return all_gigs, sources_used


def _sort_key(item: RankedGig):
    """Sortuj: najnowsze pierwsze, fit jako tiebreaker."""
    dt = item.gig.posted_dt
    if dt is None:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    else:
        epoch = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return (epoch, item.fit)


def run(
    use_llm: bool = True,
    top_n: int | None = None,
    threshold: int | None = None,
    no_webhook: bool = False,
    only_source: str | None = None,
) -> None:
    load_env()
    cfg = load_config()
    scoring_cfg = cfg.get("scoring", {})
    report_cfg = cfg.get("report", {})

    if top_n is not None:
        report_cfg["top_n"] = top_n
    if threshold is not None:
        scoring_cfg["fit_threshold"] = threshold
    if not use_llm:
        scoring_cfg["use_llm"] = False

    fit_threshold = scoring_cfg.get("fit_threshold", 6)
    top_n = report_cfg.get("top_n", 15)

    print("=" * 65)
    print("GIG FINDER — START  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 65)

    # 1. Pobieranie
    print("\n── POBIERANIE OGŁOSZEŃ ──────────────────────────────────────")
    all_gigs, sources_used = fetch_all(cfg, only_source)
    print(f"\n→ Łącznie pobrano: {len(all_gigs)} ogłoszeń z {len(sources_used)} źródeł")

    if not all_gigs:
        print("Brak ogłoszeń do oceny. Sprawdź połączenie z sieciami.")
        return

    # 2. Deduplicacja po URL
    seen_urls: set[str] = set()
    unique_gigs: list[Gig] = []
    for g in all_gigs:
        if g.url not in seen_urls:
            seen_urls.add(g.url)
            unique_gigs.append(g)
    print(f"→ Po deduplicacji: {len(unique_gigs)} unikalnych ogłoszeń")

    # 3. Filtr domen i świeżości
    print("\n── FILTROWANIE ───────────────────────────────────────────────")
    filtered = filter_gigs(unique_gigs, cfg)
    print(f"→ Po filtrowaniu: {len(filtered)} ogłoszeń")

    if not filtered:
        print("Brak ogłoszeń po filtrowaniu.")
        return

    # 4. Scoring
    llm_mode = scoring_cfg.get("use_llm", True) and use_llm
    print(f"\n── SCORING (mode: {'LLM' if llm_mode else 'heurystyka'}) ────────────────────────")

    ranked: list[RankedGig] = []
    for i, gig in enumerate(filtered, 1):
        print(f"  [{i:3}/{len(filtered)}] {gig.title[:55]:<55} ", end="", flush=True)
        s = score(gig, scoring_cfg)
        bar = "█" * s.fit + "░" * (10 - s.fit)
        print(f"fit={s.fit}/10 {bar}")
        if s.fit >= fit_threshold:
            ranked.append(RankedGig(gig=gig, score=s))

    # Sortuj: najnowsze pierwsze, fit jako tiebreaker
    ranked.sort(key=_sort_key, reverse=True)
    print(f"\n→ Zakwalifikowano: {len(ranked)} ogłoszeń (fit ≥ {fit_threshold}), najnowsze pierwsze")

    # 5. Raport
    print("\n── GENEROWANIE RAPORTU ──────────────────────────────────────")
    output_dir = _DIR / report_cfg.get("output_dir", "reports")
    paths = generate(
        ranked=ranked,
        total_scanned=len(unique_gigs),
        sources_used=sources_used,
        cfg={**report_cfg, "fit_threshold": fit_threshold},
        output_dir=output_dir,
    )
    for fmt, path in paths.items():
        print(f"  [{fmt.upper()}] → {path}")

    # 6. Webhook
    if not no_webhook:
        print("\n── DOSTARCZENIE (webhook) ───────────────────────────────────")
        date_str = datetime.now().strftime("%Y-%m-%d")
        deliver(ranked, paths, date_str)

    # 7. Podsumowanie TOP 10
    print("\n" + "=" * 65)
    print(f"TOP {min(10, len(ranked))} NAJNOWSZYCH ogłoszeń (fit ≥ {fit_threshold})")
    print("=" * 65)
    for i, item in enumerate(ranked[:10], 1):
        fit_bar = "█" * item.fit + "░" * (10 - item.fit)
        age = item.gig.age_str()
        date_label = f"{item.gig.posted_at}  ({age})" if item.gig.posted_at else f"({age})"
        print(f"\n#{i}  fit={item.fit}/10 {fit_bar}")
        print(f"    TYTUŁ:  {item.gig.title}")
        print(f"    LINK:   {item.gig.url}")
        print(f"    DATA:   {date_label}")
        print(f"    BUDŻET: {item.gig.budget}  |  ŹRÓDŁO: {item.gig.source}")
        print(f"    DLACZEGO: {item.score.why_fits}")
        print(f"    KĄT OFERTY: {item.score.offer_angle}")

    print("\n" + "=" * 65)
    print(f"Raport: {paths.get('html', paths.get('markdown', '—'))}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gig Finder — automatyczny skaner zleceń")
    parser.add_argument("--no-llm", action="store_true", help="Heurystyka zamiast LLM")
    parser.add_argument("--top", type=int, default=None, help="Liczba pozycji w raporcie (default: 15)")
    parser.add_argument("--threshold", type=int, default=None, help="Min fit score (default: 6)")
    parser.add_argument("--no-webhook", action="store_true", help="Pomiń webhook")
    parser.add_argument("--source", type=str, default=None,
                        help="Tylko jedno źródło: remoteok|weworkremotely|hn_hiring|searxng|reddit_forhire|remotive|freelancer")
    args = parser.parse_args()

    run(
        use_llm=not args.no_llm,
        top_n=args.top,
        threshold=args.threshold,
        no_webhook=args.no_webhook,
        only_source=args.source,
    )
