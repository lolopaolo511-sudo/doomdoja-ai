"""
Testy demo gig-finder workflow — bez LLM i bez sieci.
Weryfikuje logikę rankingu, parsowania i integracji quarantine.
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "gig-finder"))


# ── Mockowe Gig obiekty (bez importu rzeczywistego modułu sources) ────────────

@dataclass
class MockGig:
    id: str
    title: str
    url: str
    description: str
    budget: str
    source: str
    posted_at: str = ""
    tags: list = field(default_factory=list)

    def text_blob(self):
        return f"{self.title}\n{self.description}\n{' '.join(self.tags)}"

    def age_days(self):
        return None


def _make_gig(n: int, source: str = "remoteok", budget: str = "$50/h") -> MockGig:
    return MockGig(
        id=f"gig-{n}",
        title=f"Python Scraping Dev #{n}",
        url=f"https://example.com/job/{n}",
        description=f"We need a Python scraper #{n}. Remote. Automation/ETL.",
        budget=budget,
        source=source,
        posted_at="2026-06-01",
        tags=["python", "scraping", "remote"],
    )


class TestGigFinderWorkflowLogic:
    def test_gig_to_text_format(self):
        from workflow.demo_gig_finder import _gig_to_text
        gig = _make_gig(1)
        text = _gig_to_text(gig)
        assert "TITLE:" in text
        assert "Python Scraping Dev #1" in text
        assert "SOURCE:" in text
        assert "BUDGET:" in text
        assert "DESCRIPTION:" in text

    def test_gig_for_adversarial_no_scorer_info(self):
        from workflow.demo_gig_finder import _gig_for_adversarial
        gig = _make_gig(1)
        score_data = {"fit": 9, "why_fits": "perfect match", "offer_angle": "lead with portfolio"}
        text = _gig_for_adversarial(gig, score_data)
        # Adversarial nie powinien widzieć why_fits ani offer_angle ze scorera
        assert "perfect match" not in text
        assert "lead with portfolio" not in text
        assert "Python Scraping Dev" in text

    def test_parse_score_valid_json(self):
        from workflow.demo_gig_finder import _parse_score
        raw = '{"fit": 8, "why_fits": "Strong match", "offer_angle": "Show portfolio"}'
        result = _parse_score(raw)
        assert result["fit"] == 8
        assert "Strong match" in result["why_fits"]

    def test_parse_score_markdown_wrapped(self):
        from workflow.demo_gig_finder import _parse_score
        raw = '```json\n{"fit": 7, "why_fits": "Good", "offer_angle": "N/A"}\n```'
        result = _parse_score(raw)
        assert result["fit"] == 7

    def test_parse_score_invalid_fallback(self):
        from workflow.demo_gig_finder import _parse_score
        result = _parse_score("not json")
        assert result["fit"] == 0

    @patch("workflow.demo_gig_finder.parallel")
    def test_score_gigs_parallel_structure(self, mock_parallel):
        from workflow.demo_gig_finder import score_gigs_parallel
        from workflow.primitives import AgentResult

        gigs = [_make_gig(i) for i in range(3)]
        mock_parallel.return_value = [
            AgentResult(
                output=f'{{"fit": {5+i}, "why_fits": "match", "offer_angle": "ok"}}',
                agent_id=f"scorer-{i}", goal="score",
                model="deepseek", backend="local",
                tokens_used=100, elapsed_s=0.5
            )
            for i in range(3)
        ]

        results = score_gigs_parallel(gigs)
        assert len(results) == 3
        assert results[0]["fit"] == 5
        assert results[1]["fit"] == 6
        assert results[2]["fit"] == 7

    def test_workflow_ranked_gig_sorting(self):
        """PASS adversarial powinny być wyżej niż FAIL przy tym samym fit_score."""
        from workflow.demo_gig_finder import WorkflowScoredGig

        gigs = [
            WorkflowScoredGig(
                title="A", url="http://a", source="remoteok", budget="$50",
                posted_at="2026-06-01", fit_score=8, why_fits="good", offer_angle="ok",
                scorer_backend="local", adv_verdict="FAIL", adv_score=3, adv_reasons=["stale"],
            ),
            WorkflowScoredGig(
                title="B", url="http://b", source="hn_hiring", budget="$60",
                posted_at="2026-06-01", fit_score=8, why_fits="great", offer_angle="ok",
                scorer_backend="local", adv_verdict="PASS", adv_score=8, adv_reasons=[],
            ),
            WorkflowScoredGig(
                title="C", url="http://c", source="wwr", budget="$40",
                posted_at="2026-06-01", fit_score=7, why_fits="ok", offer_angle="ok",
                scorer_backend="local", adv_verdict="PASS", adv_score=7, adv_reasons=[],
            ),
        ]

        def _rank_key(g):
            adv_bonus = 2 if g.adv_verdict == "PASS" else (1 if g.adv_verdict == "UNCERTAIN" else 0)
            return (adv_bonus, g.fit_score)

        sorted_gigs = sorted(gigs, key=_rank_key, reverse=True)
        assert sorted_gigs[0].title == "B"  # PASS + fit=8
        assert sorted_gigs[1].title == "C"  # PASS + fit=7
        assert sorted_gigs[2].title == "A"  # FAIL mimo fit=8

    @patch("workflow.demo_gig_finder.adversarial_verification_batch")
    @patch("workflow.demo_gig_finder.score_gigs_parallel")
    @patch("workflow.demo_gig_finder.fetch_all_parallel")
    def test_workflow_pipeline_integration(self, mock_fetch, mock_score, mock_adv):
        from workflow.demo_gig_finder import gig_finder_workflow
        from workflow.patterns.adversarial_verification import AdversarialResult, Verdict

        mock_fetch.return_value = [_make_gig(i) for i in range(5)]
        mock_score.return_value = [
            {"gig": _make_gig(i), "fit": 7+i%3, "why_fits": "good",
             "offer_angle": "ok", "scorer_backend": "local", "scorer_tokens": 100}
            for i in range(5)
        ]
        mock_adv.return_value = [
            AdversarialResult(
                verdict=Verdict.PASS if i % 2 == 0 else Verdict.FAIL,
                score=8 if i % 2 == 0 else 2,
                reasons=[] if i % 2 == 0 else ["too old"],
                raw_output="", verifier_model="local", verifier_backend="local",
                tokens_used=50,
            )
            for i in range(5)
        ]

        results = gig_finder_workflow(cfg={}, top_n=10, verbose=False)
        assert len(results) > 0
        # PASS wyniki powinny być na górze rankingu
        pass_results = [r for r in results if r.adv_verdict == "PASS"]
        fail_results = [r for r in results if r.adv_verdict == "FAIL"]
        if pass_results and fail_results:
            assert pass_results[0].final_rank < fail_results[0].final_rank

    def test_quarantine_in_fetch(self):
        """Fetch działa w quarantine — @action_tool powinien być zablokowany."""
        from workflow.quarantine import quarantine, is_quarantined
        from workflow.demo_gig_finder import _save_report

        captured = []

        def mock_fetch_impl():
            captured.append(is_quarantined())

        with quarantine():
            mock_fetch_impl()
            # Próba zapisu raportu w quarantine powinna rzucić QuarantineViolation
            from workflow.quarantine import QuarantineViolation
            with pytest.raises(QuarantineViolation):
                _save_report(Path("/tmp/test_report.md"), "content")

        assert captured == [True]
