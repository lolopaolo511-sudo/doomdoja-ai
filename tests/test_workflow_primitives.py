"""
Testy prymitywów workflow — unit testy bez LLM (mockowany).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.budget import WorkflowBudget, TokenBudgetExceeded, estimate_tokens
from workflow.quarantine import (
    quarantine, is_quarantined, action_tool, QuarantineViolation, assert_clean,
)


# ═══════════════════════════════════════════════════════════════════════════════
# BUDGET
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkflowBudget:
    def test_initial_state(self):
        b = WorkflowBudget(total=1000)
        assert b.used == 0
        assert b.remaining == 1000

    def test_charge_within_budget(self):
        b = WorkflowBudget(total=1000)
        b.charge(400)
        assert b.used == 400
        assert b.remaining == 600

    def test_charge_exceeds_budget(self):
        b = WorkflowBudget(total=500)
        with pytest.raises(TokenBudgetExceeded) as exc_info:
            b.charge(600)
        assert exc_info.value.limit == 500

    def test_check_before_call(self):
        b = WorkflowBudget(total=100)
        with pytest.raises(TokenBudgetExceeded):
            b.check(200)

    def test_check_ok(self):
        b = WorkflowBudget(total=1000)
        b.check(500)  # nie rzuca

    def test_child_budget(self):
        parent = WorkflowBudget(total=5000)
        child = parent.child(1000, label="agent-1")
        assert child.total == 1000
        child.charge(400)
        assert child.used == 400
        assert parent.used == 0  # child niezależny od parent pod względem śledzenia

    def test_report_format(self):
        b = WorkflowBudget(total=1000, label="test-wf")
        b.charge(200)
        report = b.report()
        assert "test-wf" in report
        assert "200/1000" in report

    def test_estimate_tokens(self):
        assert estimate_tokens("") == 1
        assert estimate_tokens("aaaa") == 1
        assert estimate_tokens("a" * 400) == 100


# ═══════════════════════════════════════════════════════════════════════════════
# QUARANTINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuarantine:
    def test_not_quarantined_by_default(self):
        assert is_quarantined() is False

    def test_quarantine_context_sets_flag(self):
        with quarantine():
            assert is_quarantined() is True
        assert is_quarantined() is False

    def test_quarantine_nested(self):
        with quarantine():
            with quarantine():
                assert is_quarantined() is True
            assert is_quarantined() is True
        assert is_quarantined() is False

    def test_action_tool_blocked_in_quarantine(self):
        @action_tool
        def do_something():
            return "done"

        with quarantine():
            with pytest.raises(QuarantineViolation):
                do_something()

    def test_action_tool_allowed_outside_quarantine(self):
        @action_tool
        def do_something():
            return "done"

        result = do_something()
        assert result == "done"

    def test_assert_clean_passes_for_unquarantined(self):
        r = MagicMock()
        r.quarantined = False
        assert_clean(r, allow_text_passthrough=False)  # nie rzuca

    def test_assert_clean_raises_for_quarantined_strict(self):
        r = MagicMock()
        r.quarantined = True
        with pytest.raises(QuarantineViolation):
            assert_clean(r, allow_text_passthrough=False)

    def test_assert_clean_allows_quarantined_text_passthrough(self):
        r = MagicMock()
        r.quarantined = True
        assert_clean(r, allow_text_passthrough=True)  # nie rzuca


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT — mock LLM
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_call_llm(prompt, decision, system="", temperature=0.2, max_tokens=4096):
    return f"MOCK: {prompt[:40]}"


class TestAgentPrimitive:
    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_basic_agent_call(self, _mock):
        from workflow.primitives import agent
        r = agent("Zrób coś prostego", context="dane: A=1")
        assert r.ok
        assert "MOCK:" in r.output
        assert r.tokens_used > 0

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_agent_respects_token_budget(self, _mock):
        from workflow.primitives import agent
        from workflow.budget import TokenBudgetExceeded
        # 1 token budget — zawsze za mały
        with pytest.raises(TokenBudgetExceeded):
            agent("Zadanie z bardzo małym budżetem " * 20, token_budget=1)

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_agent_quarantine_propagation(self, _mock):
        from workflow.primitives import agent
        with quarantine():
            r = agent("Podsumuj ogłoszenia", context="raw html")
        assert r.quarantined is True

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_agent_error_captured(self, _mock):
        def bad_llm(*a, **kw):
            raise RuntimeError("LLM niedostępny")
        with patch("workflow.primitives._call_llm", side_effect=bad_llm):
            from workflow.primitives import agent
            r = agent("test")
        assert r.error is not None
        assert r.output == ""

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_parallel_all_results(self, _mock):
        from workflow.primitives import parallel
        tasks = [
            {"goal": f"Zadanie {i}", "context": f"dane {i}"}
            for i in range(4)
        ]
        results = parallel(tasks, max_workers=4)
        assert len(results) == 4
        assert all(r.ok for r in results)

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_pipeline_stages_string(self, _mock):
        from workflow.primitives import pipeline
        stages = ["Wyodrębnij fakty", "Oceń jakość", "Sformatuj wynik"]
        results = pipeline(stages, initial_input="Wejście testowe")
        assert len(results) == 3
        # Każdy etap dostaje output poprzedniego jako context
        assert all(r.ok for r in results)

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_pipeline_callable_stage(self, _mock):
        from workflow.primitives import pipeline
        transform = lambda x: x.upper()
        stages = [transform, "Opisz to"]
        results = pipeline(stages, initial_input="hello world")
        assert results[0].output == "HELLO WORLD"
        assert results[0].backend == "local"
        assert results[0].tokens_used == 0

    @patch("workflow.primitives._call_llm", side_effect=_mock_call_llm)
    def test_parallel_shared_budget(self, _mock):
        from workflow.primitives import parallel, WorkflowBudget
        budget = WorkflowBudget(total=50000)
        tasks = [{"goal": f"Krótkie zadanie {i}"} for i in range(3)]
        results = parallel(tasks, budget=budget)
        assert len(results) == 3
        # Budget powinien być częściowo zużyty
        assert budget.used > 0
