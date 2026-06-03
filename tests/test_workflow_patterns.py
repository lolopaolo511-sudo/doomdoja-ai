"""
Testy wzorców workflow — unit testy bez LLM (mockowany).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.primitives import AgentResult


def _make_result(output: str, agent_id: str = "test", error: str | None = None,
                 tokens: int = 100, backend: str = "local") -> AgentResult:
    return AgentResult(
        output=output, agent_id=agent_id, goal="test goal",
        model="deepseek-coder-v2:16b", backend=backend,
        tokens_used=tokens, elapsed_s=0.5, error=error,
    )


def _mock_agent(goal, context="", **kwargs) -> AgentResult:
    return _make_result(f"MOCK_OUTPUT: {goal[:30]}", agent_id=kwargs.get("agent_id", "mock"))


# ═══════════════════════════════════════════════════════════════════════════════
# classify_and_act
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyAndAct:
    @patch("workflow.patterns.classify_and_act.agent", side_effect=_mock_agent)
    def test_classify_routes_to_category(self, mock_ag):
        from workflow.patterns.classify_and_act import classify_and_act

        calls = []
        def tracking_agent(goal, context="", **kw):
            calls.append({"goal": goal, "kw": kw})
            if kw.get("agent_id") == "classify":
                return _make_result("scraping", agent_id="classify")
            return _make_result(f"Handler result for: {goal[:40]}", agent_id=kw.get("agent_id", "h"))

        with patch("workflow.patterns.classify_and_act.agent", side_effect=tracking_agent):
            result = classify_and_act(
                task="Build a Python web scraper",
                categories={
                    "scraping": {"goal": "Design scraper for: {task}"},
                    "etl":      {"goal": "Design ETL for: {task}"},
                    "default":  {"goal": "Handle: {task}"},
                },
            )

        assert result.category == "scraping"
        assert "Handler result" in result.output

    @patch("workflow.patterns.classify_and_act.agent", side_effect=_mock_agent)
    def test_classify_falls_back_to_default(self, _):
        from workflow.patterns.classify_and_act import classify_and_act

        def unknown_classifier(goal, context="", **kw):
            if kw.get("agent_id") == "classify":
                return _make_result("unknown_xyz", agent_id="classify")
            return _make_result("Default handler ran", agent_id=kw.get("agent_id", "h"))

        with patch("workflow.patterns.classify_and_act.agent", side_effect=unknown_classifier):
            result = classify_and_act(
                task="Random task",
                categories={
                    "scraping": {"goal": "Scrape: {task}"},
                    "default":  {"goal": "Handle: {task}"},
                },
            )

        assert result.category == "default"

    def test_extract_category(self):
        from workflow.patterns.classify_and_act import _extract_category
        assert _extract_category("scraping", ["scraping", "etl", "default"]) == "scraping"
        assert _extract_category(" SCRAPING ", ["scraping", "etl", "default"]) == "scraping"
        assert _extract_category("this is scraping", ["scraping", "etl", "default"]) == "scraping"
        assert _extract_category("xyz", ["scraping", "etl", "default"]) == "default"


# ═══════════════════════════════════════════════════════════════════════════════
# fan_out_and_synthesize
# ═══════════════════════════════════════════════════════════════════════════════

class TestFanOutAndSynthesize:
    @patch("workflow.patterns.fan_out_and_synthesize.agent", side_effect=_mock_agent)
    @patch("workflow.patterns.fan_out_and_synthesize.parallel")
    def test_fan_out_calls_parallel(self, mock_parallel, _mock_ag):
        from workflow.patterns.fan_out_and_synthesize import fan_out_and_synthesize

        subtask_results = [_make_result(f"result {i}", agent_id=f"fanout-{i}") for i in range(3)]
        mock_parallel.return_value = subtask_results

        result = fan_out_and_synthesize(
            subtasks=[{"goal": f"task {i}"} for i in range(3)],
            synthesize_goal="Synthesize all",
        )

        mock_parallel.assert_called_once()
        assert result.ok_count == 3
        assert result.failed_count == 0
        assert "MOCK_OUTPUT" in result.synthesis.output

    @patch("workflow.patterns.fan_out_and_synthesize.agent", side_effect=_mock_agent)
    @patch("workflow.patterns.fan_out_and_synthesize.parallel")
    def test_fan_out_report_format(self, mock_parallel, _):
        from workflow.patterns.fan_out_and_synthesize import fan_out_and_synthesize

        mock_parallel.return_value = [_make_result("r1", agent_id="fanout-0")]
        result = fan_out_and_synthesize(subtasks=[{"goal": "task 1"}])
        report = result.report()
        assert "FanOut" in report
        assert "OK" in report


# ═══════════════════════════════════════════════════════════════════════════════
# adversarial_verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdversarialVerification:
    def test_parse_pass_verdict(self):
        from workflow.patterns.adversarial_verification import _parse_verifier_output, Verdict
        result = _make_result('{"verdict": "PASS", "score": 8, "reasons": []}')
        adv = _parse_verifier_output(result, pass_threshold=5)
        assert adv.verdict == Verdict.PASS
        assert adv.score == 8
        assert not adv.parse_error

    def test_parse_fail_verdict(self):
        from workflow.patterns.adversarial_verification import _parse_verifier_output, Verdict
        result = _make_result('{"verdict": "FAIL", "score": 2, "reasons": ["expired", "wrong domain"]}')
        adv = _parse_verifier_output(result, pass_threshold=5)
        assert adv.verdict == Verdict.FAIL
        assert adv.score == 2
        assert "expired" in adv.reasons

    def test_parse_high_score_overrides_pass_threshold(self):
        from workflow.patterns.adversarial_verification import _parse_verifier_output, Verdict
        result = _make_result('{"verdict": "PASS", "score": 3, "reasons": []}')
        adv = _parse_verifier_output(result, pass_threshold=5)
        # score < threshold → FAIL nawet jeśli verdict=PASS
        assert adv.verdict == Verdict.FAIL

    def test_parse_error_fallback(self):
        from workflow.patterns.adversarial_verification import _parse_verifier_output, Verdict
        result = _make_result("not json at all")
        adv = _parse_verifier_output(result, pass_threshold=5)
        assert adv.parse_error is True
        assert adv.verdict in (Verdict.PASS, Verdict.FAIL, Verdict.UNCERTAIN)

    def test_parse_markdown_wrapped_json(self):
        from workflow.patterns.adversarial_verification import _parse_verifier_output, Verdict
        result = _make_result('```json\n{"verdict": "PASS", "score": 7, "reasons": []}\n```')
        adv = _parse_verifier_output(result, pass_threshold=5)
        assert adv.verdict == Verdict.PASS

    @patch("workflow.patterns.adversarial_verification.agent")
    def test_full_call_with_mock(self, mock_ag):
        from workflow.patterns.adversarial_verification import adversarial_verification, Verdict
        mock_ag.return_value = _make_result('{"verdict": "PASS", "score": 8, "reasons": ["good match"]}')
        result = adversarial_verification(
            content="Python scraping project $50/h remote",
            rubric="Pass if: scraping, remote, >$35/h",
        )
        assert result.verdict == Verdict.PASS
        assert result.score == 8
        mock_ag.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# generate_and_filter
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateAndFilter:
    def test_parse_numbered_list(self):
        from workflow.patterns.generate_and_filter import _parse_numbered_list
        text = "1. First item\n2. Second item\n3. Third item"
        result = _parse_numbered_list(text)
        assert result == ["First item", "Second item", "Third item"]

    def test_dedup_removes_similar(self):
        from workflow.patterns.generate_and_filter import _dedup
        options = ["Python scraper", "Python scraper tool", "ETL pipeline", "Python scraper service"]
        result = _dedup(options, threshold=0.7)
        assert len(result) < len(options)
        assert "ETL pipeline" in result

    def test_dedup_keeps_unique(self):
        from workflow.patterns.generate_and_filter import _dedup
        options = ["Python scraper", "Go microservice", "Node.js API"]
        result = _dedup(options)
        assert len(result) == 3

    @patch("workflow.patterns.generate_and_filter.agent")
    def test_full_generate_and_filter(self, mock_ag):
        from workflow.patterns.generate_and_filter import generate_and_filter
        gen_output = "1. Python Expert\n2. Scraper Dev\n3. ETL Builder\n4. Automation Guru\n5. Data Wizard"
        filter_output = '{"kept": [{"index": 1, "text": "Python Expert", "score": 9}, {"index": 2, "text": "Scraper Dev", "score": 8}]}'

        call_count = [0]
        def fake_agent(goal, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_result(gen_output, agent_id="generator")
            return _make_result(filter_output, agent_id="filter")

        mock_ag.side_effect = fake_agent
        result = generate_and_filter(
            prompt="Freelancer titles",
            rubric="Keep Python/scraping specialists",
            n=5, top_k=2,
        )
        assert len(result.kept) == 2
        assert result.kept[0]["score"] == 9
        assert not result.parse_error


# ═══════════════════════════════════════════════════════════════════════════════
# tournament
# ═══════════════════════════════════════════════════════════════════════════════

class TestTournament:
    def test_parse_match_winner_a(self):
        from workflow.patterns.tournament import _parse_match
        assert _parse_match('{"winner": "A", "reason": "better"}') == "A"

    def test_parse_match_winner_b(self):
        from workflow.patterns.tournament import _parse_match
        assert _parse_match('{"winner": "B", "reason": "clearer"}') == "B"

    def test_parse_match_tie(self):
        from workflow.patterns.tournament import _parse_match
        assert _parse_match('{"winner": "TIE", "reason": "equal"}') == "TIE"

    def test_parse_match_fallback(self):
        from workflow.patterns.tournament import _parse_match
        result = _parse_match("Option A is clearly better here")
        assert result in ("A", "B", "TIE")

    @patch("workflow.patterns.tournament.parallel")
    def test_tournament_ranking(self, mock_parallel):
        from workflow.patterns.tournament import tournament
        candidates = ["Option A", "Option B", "Option C"]
        # A vs B → A, A vs C → A, B vs C → B
        mock_parallel.return_value = [
            _make_result('{"winner": "A", "reason": "better"}', agent_id="match-0v1"),
            _make_result('{"winner": "A", "reason": "better"}', agent_id="match-0v2"),
            _make_result('{"winner": "B", "reason": "better"}', agent_id="match-1v2"),
        ]
        result = tournament(candidates, criterion="Which is best?")
        assert result.winner == "Option A"
        assert result.ranking[0][1] == 2   # A: 2 zwycięstwa
        # "B" w meczu B vs C oznacza drugiego uczestnika pary (Option C) → C dostaje punkt
        assert result.ranking[1][0] == "Option C"

    def test_tournament_requires_two_candidates(self):
        from workflow.patterns.tournament import tournament
        with pytest.raises(ValueError):
            tournament(["Solo"], criterion="Best?")


# ═══════════════════════════════════════════════════════════════════════════════
# loop_until_done
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoopUntilDone:
    @patch("workflow.patterns.loop_until_done.agent")
    def test_loop_exits_on_condition_met(self, mock_ag):
        from workflow.patterns.loop_until_done import loop_until_done
        mock_ag.return_value = _make_result("def sort_list(): return sorted(lst)")

        result = loop_until_done(
            task="Write sort function",
            done_condition=lambda out: "def " in out,
            max_iterations=5,
        )
        assert result.completed is True
        assert result.iterations == 1

    @patch("workflow.patterns.loop_until_done.agent")
    def test_loop_hits_max_iterations(self, mock_ag):
        from workflow.patterns.loop_until_done import loop_until_done
        mock_ag.return_value = _make_result("incomplete output without the keyword")

        result = loop_until_done(
            task="Write something with magic word",
            done_condition=lambda out: "MAGIC" in out,
            max_iterations=3,
        )
        assert result.completed is False
        assert result.iterations == 3
        assert result.hit_limit is True

    @patch("workflow.patterns.loop_until_done.agent")
    def test_loop_report_format(self, mock_ag):
        from workflow.patterns.loop_until_done import loop_until_done
        mock_ag.return_value = _make_result("done content DONE")

        result = loop_until_done(
            task="Do something",
            done_condition=lambda out: "DONE" in out,
            max_iterations=2,
        )
        report = result.report()
        assert "UKOŃCZONE" in report
        assert "Iter 1" in report
