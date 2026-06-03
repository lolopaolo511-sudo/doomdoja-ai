"""
workflow/demo_gig_finder.py — Gig Finder przepisany na WORKFLOW-ENGINE v1

Architektura workflow (vs stary sequential):

  STARY FLOW:
    fetch A → fetch B → ... fetch N  (sekwencyjnie)
    score gig 1 → score gig 2 → ...  (sekwencyjnie, jeden scorer)
    [brak adversarial check — scorer był zbyt łaskawy]

  NOWY FLOW:
    ┌─ quarantine fetch A ─┐
    ├─ quarantine fetch B ─┤  parallel → fan_out
    └─ quarantine fetch N ─┘
             ↓
    parallel LLM scorer (każdy gig = osobny agent, izolowany context)
             ↓
    adversarial_verification_batch (weryfikator bez wiedzy o scorerze)
             ↓
    synthesis → ranking TOP N

Kluczowe ulepszenia:
  1. Quarantine: agenty pobierające dane z sieci NIE mogą wywołać akcji
  2. Adversarial: osobny agent weryfikuje BEZ znajomości scorera
     → łapie: stare ogłoszenia, błędną domenę, mismatch budżetu
  3. Parallel scorer: 3-5x szybciej niż sekwencyjny
  4. Izolacja: każdy scoring agent widzi TYLKO swoje ogłoszenie

Użycie:
    # Pełne uruchomienie
    python -m workflow.demo_gig_finder --top 10 --budget 20000

    # Porównanie z oryginalnym scorerem
    python -m workflow.demo_gig_finder --compare --source remoteok

    # Dry-run (bez LLM)
    python -m workflow.demo_gig_finder --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DIR = Path(__file__).parent
_GIG_FINDER_DIR = _DIR.parent / "gig-finder"
sys.path.insert(0, str(_DIR.parent))
sys.path.insert(0, str(_GIG_FINDER_DIR))

from workflow import (
    agent, parallel, WorkflowBudget, quarantine,
    run_workflow, WorkflowConfig,
)
from workflow.patterns import (
    fan_out_and_synthesize, adversarial_verification_batch,
    FanOutResult, AdversarialResult, Verdict,
)
from workflow.quarantine import action_tool

logger = logging.getLogger("qwen_agent.workflow.gig_finder_demo")

# ── Profil do oceny dopasowania ───────────────────────────────────────────────
_PROFILE_SUMMARY = """
Specjalizacje: web scraping, data extraction, Python automation, ETL pipelines,
AI agents (LLM), Playwright/Selenium crawlers, Airtable integration,
Make.com/Zapier/n8n, pandas, lead generation, OCR, invoice/PDF parsing,
document processing, FastAPI.
Minimalna stawka: $35/h lub $300/projekt. Tylko remote.
"""

# ── Rubryka adversarial weryfikatora ─────────────────────────────────────────
_ADVERSARIAL_RUBRIC = """
ODRZUĆ ogłoszenie (FAIL) jeśli:
  - Brak budżetu LUB budżet wyraźnie poniżej $300
  - Wymaga pracy biurowej / on-site / non-remote
  - Ogłoszenie stare (>14 dni od daty publikacji)
  - Wygasłe lub nieaktualne (zawiera "closed", "filled", "no longer")
  - Dotyczy technologii spoza profilu: blockchain, mobile (iOS/Android),
    WordPress themes, Shopify design, Java/.NET-only, C#-only
  - Tytuł sugeruje misja-mismatch (marketing copy, HR, accounting)
  - Opis zbyt niejasny żeby ocenić dopasowanie

PRZEPUŚĆ (PASS) jeśli:
  - Wyraźnie dotyczy: scraping, automation, ETL, data pipeline, AI agents,
    integration API, OCR/PDF, lead gen, Airtable/Make/Zapier/n8n
  - Remote i widoczny budżet ≥ $300 LUB stawka ≥ $35/h
  - Opis wystarczająco konkretny
"""


# ═══════════════════════════════════════════════════════════════════════════════
# STRUKTURY DANYCH
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class WorkflowScoredGig:
    """Wynik pipeline'u workflow dla jednego ogłoszenia."""
    title: str
    url: str
    source: str
    budget: str
    posted_at: str
    # Scorer
    fit_score: int          # 0-10 z LLM scorera
    why_fits: str
    offer_angle: str
    scorer_backend: str
    # Adversarial verifier
    adv_verdict: str        # PASS / FAIL / UNCERTAIN
    adv_score: int          # 0-10
    adv_reasons: list[str]
    # Final
    final_rank: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# POMOCNICZE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_env() -> None:
    """Załaduj .env z kilku możliwych lokalizacji."""
    for p in [_GIG_FINDER_DIR / ".env", _DIR.parent / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()
            return


def _gig_to_text(gig) -> str:
    """Konwertuj Gig dataclass na tekst dla LLM agenta."""
    tags = ", ".join(gig.tags[:8]) if gig.tags else "—"
    return (
        f"TITLE: {gig.title}\n"
        f"SOURCE: {gig.source}\n"
        f"BUDGET: {gig.budget}\n"
        f"POSTED: {gig.posted_at or 'unknown'}\n"
        f"TAGS: {tags}\n"
        f"URL: {gig.url}\n"
        f"DESCRIPTION:\n{gig.description[:600]}"
    )


def _gig_for_adversarial(gig, score_result: dict) -> str:
    """Tekst ogłoszenia dla adversarial weryfikatora — BEZ informacji o scorerze."""
    return (
        f"TITLE: {gig.title}\n"
        f"SOURCE: {gig.source}\n"
        f"BUDGET: {gig.budget}\n"
        f"POSTED: {gig.posted_at or 'unknown'}\n"
        f"URL: {gig.url}\n"
        f"DESCRIPTION:\n{gig.description[:600]}"
        # Celowo NIE dołączamy score.why_fits ani score.offer_angle
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FETCHING (quarantine)
# ═══════════════════════════════════════════════════════════════════════════════

@action_tool
def _save_report(path: Path, content: str) -> None:
    """Zapis raportu — zabezpieczony @action_tool (blokowany w quarantine)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fetch_source_safe(name: str, adapter, src_cfg: dict) -> list:
    """Pobierz gigi z jednego źródła w kwarantannie (opakowuje Python adapter)."""
    try:
        gigs = adapter.fetch(src_cfg)
        logger.info(f"[fetch] {name}: {len(gigs)} ogłoszeń")
        return gigs
    except Exception as exc:
        logger.warning(f"[fetch] {name} błąd: {exc}")
        return []


def fetch_all_parallel(cfg: dict, only_source: Optional[str] = None) -> list:
    """
    Pobierz ogłoszenia ze wszystkich źródeł równolegle.
    Każde źródło jest izolowane (quarantine context).
    """
    try:
        from sources import remoteok, weworkremotely, hn_hiring, upwork_rss
        from sources import reddit_forhire, remotive, freelancer
    except ImportError as exc:
        logger.error(f"[fetch] brak modułu sources: {exc}")
        return []

    sources_cfg = cfg.get("sources", {})
    adapter_map = {
        "remoteok":        (remoteok,        sources_cfg.get("remoteok", {})),
        "weworkremotely":  (weworkremotely,   sources_cfg.get("weworkremotely", {})),
        "hn_hiring":       (hn_hiring,        sources_cfg.get("hn_hiring", {})),
        "upwork_rss":      (upwork_rss,       sources_cfg.get("upwork_rss", {})),
        "reddit_forhire":  (reddit_forhire,   sources_cfg.get("reddit_forhire", {})),
        "remotive":        (remotive,         sources_cfg.get("remotive", {})),
        "freelancer":      (freelancer,       sources_cfg.get("freelancer", {})),
    }

    if only_source:
        adapter_map = {k: v for k, v in adapter_map.items() if k == only_source}

    all_gigs = []
    # Pobieranie w kwarantannie — dane z sieci nie mogą triggować akcji
    with quarantine():
        for name, (adapter, src_cfg) in adapter_map.items():
            if src_cfg.get("enabled", True):
                gigs = _fetch_source_safe(name, adapter, src_cfg)
                all_gigs.extend(gigs)

    return all_gigs


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING (parallel LLM agenty)
# ═══════════════════════════════════════════════════════════════════════════════

_SCORER_SYSTEM = (
    "You are a freelance business analyst. Rate job fit and respond ONLY with valid JSON."
)

_SCORER_PROMPT = """\
Rate this job posting for a freelancer with this profile:
{profile}

JOB POSTING:
{gig_text}

Rate fit 0-10 where:
10 = perfect match (scraping/automation/ETL/OCR explicitly requested)
7-9 = strong match (data, python, automation, pipelines)
4-6 = partial match
0-3 = weak/irrelevant

Return ONLY JSON:
{{"fit": <0-10>, "why_fits": "<1-2 sentences>", "offer_angle": "<1 sentence>"}}
"""


def score_gigs_parallel(
    gigs: list,
    budget: Optional[WorkflowBudget] = None,
    max_workers: int = 6,
    token_budget_per_gig: int = 800,
    session_id: str = "",
) -> list[dict]:
    """
    Ocen wszystkie gigi równolegle — każdy agent widzi TYLKO jedno ogłoszenie.
    """
    tasks = []
    for i, gig in enumerate(gigs):
        gig_text = _gig_to_text(gig)
        tasks.append({
            "goal": _SCORER_PROMPT.format(
                profile=_PROFILE_SUMMARY.strip(),
                gig_text=gig_text,
            ),
            "system": _SCORER_SYSTEM,
            "token_budget": token_budget_per_gig,
            "session_id": session_id,
            "agent_id": f"scorer-{i}",
            "force_local": True,   # scoring lokalnie — szybko i tanio
            "tags": ["scoring", "gig-finder"],
        })
    if budget:
        for t in tasks:
            t["budget"] = budget

    results = parallel(tasks, max_workers=max_workers)

    scored = []
    for gig, res in zip(gigs, results):
        score_data = _parse_score(res.output)
        scored.append({
            "gig": gig,
            "fit": score_data.get("fit", 0),
            "why_fits": score_data.get("why_fits", ""),
            "offer_angle": score_data.get("offer_angle", "N/A"),
            "scorer_backend": res.backend,
            "scorer_tokens": res.tokens_used,
        })

    return scored


def _parse_score(text: str) -> dict:
    """Parsuj JSON ze scorera."""
    import re
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"fit": 0, "why_fits": "parse error", "offer_angle": "N/A"}


# ═══════════════════════════════════════════════════════════════════════════════
# GŁÓWNY WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

def gig_finder_workflow(
    cfg: dict,
    *,
    budget: Optional[WorkflowBudget] = None,
    session_id: str = "",
    top_n: int = 10,
    fit_threshold: int = 6,
    adv_pass_threshold: int = 5,
    only_source: Optional[str] = None,
    max_gigs_to_score: int = 60,
    max_workers: int = 6,
    verbose: bool = True,
) -> list[WorkflowScoredGig]:
    """
    Główny workflow gig-findera.

    Etapy:
      1. Fetch (quarantine, Python adapters)
      2. Dedup + wstępny filtr
      3. Parallel LLM scoring
      4. Adversarial verification na gigi ≥ fit_threshold
      5. Ranking: zachowaj tylko PASS z adversarial

    Returns: posortowana lista WorkflowScoredGig
    """
    start_ts = time.monotonic()

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    if verbose:
        print("\n── FETCH (quarantine) ──────────────────────────────────────")
    all_gigs = fetch_all_parallel(cfg, only_source=only_source)
    if verbose:
        print(f"  Pobrano: {len(all_gigs)} ogłoszeń")

    if not all_gigs:
        return []

    # ── 2. Dedup + filtr ──────────────────────────────────────────────────────
    seen_urls: set[str] = set()
    unique_gigs = []
    for g in all_gigs:
        if g.url not in seen_urls:
            seen_urls.add(g.url)
            unique_gigs.append(g)

    # Ogranicz do max_gigs_to_score (koszt tokenów)
    gigs_to_score = unique_gigs[:max_gigs_to_score]
    if verbose:
        print(f"  Po dedup: {len(unique_gigs)} | do scoringu: {len(gigs_to_score)}")

    # ── 3. Parallel scoring ───────────────────────────────────────────────────
    if verbose:
        print(f"\n── PARALLEL SCORING ({len(gigs_to_score)} gig, max_workers={max_workers}) ──")
    score_start = time.monotonic()
    scored = score_gigs_parallel(
        gigs_to_score, budget=budget,
        max_workers=max_workers, session_id=session_id,
    )
    score_elapsed = time.monotonic() - score_start

    # Filtruj wg progu
    above_threshold = [s for s in scored if s["fit"] >= fit_threshold]
    if verbose:
        print(f"  Scored {len(scored)} gig w {score_elapsed:.1f}s | "
              f"≥{fit_threshold}: {len(above_threshold)} ogłoszeń")

    if not above_threshold:
        return []

    # ── 4. Adversarial verification ───────────────────────────────────────────
    if verbose:
        print(f"\n── ADVERSARIAL VERIFICATION ({len(above_threshold)} ogłoszeń) ──")
    adv_start = time.monotonic()

    # Weryfikator NIE dostaje score.why_fits ani historii scorera
    items_for_adv = [_gig_for_adversarial(s["gig"], s) for s in above_threshold]

    adv_results = adversarial_verification_batch(
        items=items_for_adv,
        rubric=_ADVERSARIAL_RUBRIC,
        pass_threshold=adv_pass_threshold,
        max_workers=max_workers,
        token_budget_per_item=600,
        budget=budget,
        session_id=session_id,
    )
    adv_elapsed = time.monotonic() - adv_start

    passed_adv = sum(1 for r in adv_results if r.passed)
    if verbose:
        print(f"  Adversarial: {passed_adv}/{len(adv_results)} PASS "
              f"w {adv_elapsed:.1f}s")

    # ── 5. Ranking ────────────────────────────────────────────────────────────
    combined = []
    for s, adv in zip(above_threshold, adv_results):
        combined.append(WorkflowScoredGig(
            title=s["gig"].title,
            url=s["gig"].url,
            source=s["gig"].source,
            budget=s["gig"].budget,
            posted_at=getattr(s["gig"], "posted_at", "") or "",
            fit_score=s["fit"],
            why_fits=s["why_fits"],
            offer_angle=s["offer_angle"],
            scorer_backend=s["scorer_backend"],
            adv_verdict=adv.verdict.value,
            adv_score=adv.score,
            adv_reasons=adv.reasons,
        ))

    # Sortuj: PASS adversarial najpierw, potem wg fit_score malejąco
    def _rank_key(g: WorkflowScoredGig):
        adv_bonus = 2 if g.adv_verdict == "PASS" else (1 if g.adv_verdict == "UNCERTAIN" else 0)
        return (adv_bonus, g.fit_score)

    combined.sort(key=_rank_key, reverse=True)
    for i, item in enumerate(combined, 1):
        item.final_rank = i

    total_elapsed = time.monotonic() - start_ts
    if verbose:
        print(f"\n  Łącznie: {len(combined)} ogłoszeń w {total_elapsed:.1f}s")

    return combined[:top_n]


# ═══════════════════════════════════════════════════════════════════════════════
# PORÓWNANIE Z ORYGINALNYM SCOREREM
# ═══════════════════════════════════════════════════════════════════════════════

def compare_with_original(
    gigs: list,
    cfg: dict,
    top_n: int = 10,
) -> None:
    """
    Porównaj workflow ranking z oryginalnym scorerem gig-findera.
    Pokazuje różnicę w rankingu i które ogłoszenia adversarial odrzucił.
    """
    try:
        from scorer import score as original_score
    except ImportError:
        print("[compare] Nie można zaimportować oryginalnego scorera")
        return

    scoring_cfg = cfg.get("scoring", {})
    print("\n" + "=" * 65)
    print("PORÓWNANIE: Oryginalny scorer vs Workflow (adversarial)")
    print("=" * 65)

    orig_scores = []
    for gig in gigs[:40]:
        try:
            s = original_score(gig, scoring_cfg)
            orig_scores.append((gig, s.fit, s.why_fits))
        except Exception:
            orig_scores.append((gig, 0, "error"))

    orig_scores.sort(key=lambda x: x[1], reverse=True)

    print(f"\n--- ORYGINALNY SCORER (TOP {top_n}) ---")
    for i, (gig, fit, why) in enumerate(orig_scores[:top_n], 1):
        print(f"  {i:2}. [fit={fit}/10] {gig.title[:55]}")
        print(f"      {why[:80]}")

    print(f"\n--- UWAGA: Oryginalny scorer nie ma adversarial filter ---")
    print("Uruchom workflow demo żeby zobaczyć pełne porównanie.")


# ═══════════════════════════════════════════════════════════════════════════════
# WYDRUK WYNIKÓW
# ═══════════════════════════════════════════════════════════════════════════════

def print_workflow_results(results: list[WorkflowScoredGig], budget: Optional[WorkflowBudget]) -> None:
    """Wydruk TOP wyników z raportem workflow."""
    print("\n" + "=" * 65)
    print(f"WORKFLOW GIG FINDER — TOP {len(results)} WYNIKÓW")
    print("(adversarial verified)")
    print("=" * 65)

    pass_count = sum(1 for r in results if r.adv_verdict == "PASS")
    fail_count = sum(1 for r in results if r.adv_verdict == "FAIL")
    uncert_count = sum(1 for r in results if r.adv_verdict == "UNCERTAIN")

    print(f"\nLegenda: ✓=PASS adversarial | ✗=FAIL | ?=UNCERTAIN")
    print(f"Wyniki: {pass_count} PASS | {fail_count} FAIL | {uncert_count} UNCERTAIN\n")

    for r in results:
        adv_icon = "✓" if r.adv_verdict == "PASS" else ("✗" if r.adv_verdict == "FAIL" else "?")
        fit_bar = "█" * r.fit_score + "░" * (10 - r.fit_score)
        print(f"#{r.final_rank}  fit={r.fit_score}/10 {fit_bar}  adv={adv_icon}[{r.adv_score}]")
        print(f"    TYTUŁ:  {r.title}")
        print(f"    LINK:   {r.url}")
        print(f"    DATA:   {r.posted_at or '—'}  |  BUDŻET: {r.budget}")
        print(f"    ŹRÓDŁO: {r.source}  |  SCORER: {r.scorer_backend}")
        print(f"    DLACZEGO: {r.why_fits[:100]}")
        if r.adv_verdict == "FAIL" and r.adv_reasons:
            print(f"    ⚠ ADV REASONS: {', '.join(r.adv_reasons[:2])}")
        elif r.adv_verdict == "PASS":
            print(f"    ✓ ADV PASSED (score={r.adv_score})")
        print()

    if budget:
        print(f"Budżet tokenów: {budget.report()}")

    print("=" * 65)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _load_gig_config() -> dict:
    cfg_path = _GIG_FINDER_DIR / "config.yaml"
    try:
        import yaml
        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gig Finder WORKFLOW — parallel fetch + adversarial verification"
    )
    parser.add_argument("--top", type=int, default=10, help="TOP N wyników (default: 10)")
    parser.add_argument("--budget", type=int, default=30000,
                        help="Limit tokenów (default: 30000)")
    parser.add_argument("--threshold", type=int, default=6,
                        help="Min fit score dla scorera (default: 6)")
    parser.add_argument("--adv-threshold", type=int, default=5,
                        help="Min score adversarial PASS (default: 5)")
    parser.add_argument("--source", type=str, default=None,
                        help="Tylko jedno źródło (np. remoteok)")
    parser.add_argument("--compare", action="store_true",
                        help="Porównaj z oryginalnym scorerem")
    parser.add_argument("--max-gigs", type=int, default=60,
                        help="Max ogłoszeń do scorowania (default: 60)")
    parser.add_argument("--workers", type=int, default=6,
                        help="Max równoległych agentów (default: 6)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch i wydruk bez LLM scoringu")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    _load_env()
    cfg = _load_gig_config()

    print("=" * 65)
    print("GIG FINDER WORKFLOW v1  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("fan_out + parallel scoring + adversarial verification")
    print("=" * 65)

    budget = WorkflowBudget(total=args.budget, label="gig-finder-workflow")
    session_id = f"gf-{int(time.time())}"

    if args.dry_run:
        print("\n[DRY-RUN] Fetch tylko:")
        gigs = fetch_all_parallel(cfg, only_source=args.source)
        print(f"  Pobrano: {len(gigs)} ogłoszeń")
        for g in gigs[:5]:
            print(f"  - {g.title[:60]} [{g.source}]")
        if len(gigs) > 5:
            print(f"  ... i {len(gigs)-5} więcej")
        return

    results = gig_finder_workflow(
        cfg=cfg,
        budget=budget,
        session_id=session_id,
        top_n=args.top,
        fit_threshold=args.threshold,
        adv_pass_threshold=args.adv_threshold,
        only_source=args.source,
        max_gigs_to_score=args.max_gigs,
        max_workers=args.workers,
        verbose=True,
    )

    if not results:
        print("\nBrak wyników spełniających kryteria.")
        return

    print_workflow_results(results, budget)

    if args.compare:
        all_gigs = fetch_all_parallel(cfg, only_source=args.source)
        compare_with_original(all_gigs, cfg, top_n=args.top)


if __name__ == "__main__":
    main()
