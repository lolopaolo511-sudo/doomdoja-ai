"""
Testy runnera workflow (CLI, budżety, loop, goal) — bez LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.runner import WorkflowConfig, RunResult, run_workflow, config_from_args
from workflow.budget import TokenBudgetExceeded


def _simple_wf(budget=None, session_id="") -> str:
    return "workflow output"


def _counting_wf(counter=None, budget=None, session_id="") -> str:
    if counter is not None:
        counter.append(1)
    return "done"


class TestWorkflowConfig:
    def test_default_config(self):
        cfg = WorkflowConfig()
        assert cfg.loop == 1
        assert cfg.budget_tokens is None
        assert cfg.goal_condition is None
        assert cfg.quarantine_all is False

    def test_config_from_args_defaults(self):
        cfg = config_from_args([])
        assert cfg.loop == 1
        assert cfg.budget_tokens is None

    def test_config_from_args_full(self):
        cfg = config_from_args([
            "--goal", "zawiera JSON",
            "--loop", "3",
            "--budget", "5000",
            "--quarantine",
            "--session", "test-123",
        ])
        assert cfg.goal_condition == "zawiera JSON"
        assert cfg.loop == 3
        assert cfg.budget_tokens == 5000
        assert cfg.quarantine_all is True
        assert cfg.session_id == "test-123"


class TestRunWorkflow:
    def test_single_run(self):
        result = run_workflow(_simple_wf)
        assert result.iterations == 1
        assert result.final_output() == "workflow output"
        assert not result.budget_exceeded
        assert not result.errors

    def test_loop_n_times(self):
        counter = []
        cfg = WorkflowConfig(loop=3)
        result = run_workflow(_counting_wf, cfg=cfg, counter=counter)
        assert result.iterations == 3
        assert len(counter) == 3

    def test_dry_run(self):
        cfg = WorkflowConfig(dry_run=True)
        result = run_workflow(_simple_wf, cfg=cfg)
        assert result.iterations == 0
        assert "[DRY-RUN]" in result.final_output()

    def test_budget_enforced(self):
        def expensive_wf(budget=None, session_id=""):
            if budget:
                budget.charge(budget.total + 1)  # przekrocz
            return "output"

        cfg = WorkflowConfig(budget_tokens=100)
        result = run_workflow(expensive_wf, cfg=cfg)
        assert result.budget_exceeded is True

    def test_error_captured(self):
        def failing_wf(budget=None, session_id=""):
            raise RuntimeError("coś poszło nie tak")

        cfg = WorkflowConfig(loop=2)
        result = run_workflow(failing_wf, cfg=cfg)
        assert len(result.errors) > 0
        assert "coś poszło nie tak" in result.errors[0]

    def test_run_result_report_format(self):
        result = RunResult(
            outputs=["output1"], iterations=2, total_tokens=500,
            elapsed_s=1.5, completed_goal=True, budget_exceeded=False, errors=[],
        )
        report = result.report()
        assert "WorkflowRunner" in report
        assert "SPEŁNIONY" in report
        assert "2" in report

    def test_quarantine_propagated(self):
        from workflow.quarantine import is_quarantined

        captured = []

        def check_quarantine_wf(budget=None, session_id=""):
            captured.append(is_quarantined())
            return "checked"

        cfg = WorkflowConfig(quarantine_all=True)
        run_workflow(check_quarantine_wf, cfg=cfg)
        assert captured == [True]

    def test_quarantine_off_by_default(self):
        from workflow.quarantine import is_quarantined

        captured = []

        def check_quarantine_wf(budget=None, session_id=""):
            captured.append(is_quarantined())
            return "checked"

        run_workflow(check_quarantine_wf)
        assert captured == [False]

    def test_goal_condition_stops_loop(self):
        """Cel osiągnięty w 2. iteracji — pętla zatrzymuje się."""
        call_count = [0]

        def incremental_wf(budget=None, session_id=""):
            call_count[0] += 1
            return "step" * call_count[0]

        with patch("workflow.runner._check_goal", side_effect=lambda out, cond: "stepstep" in out):
            cfg = WorkflowConfig(loop=5, goal_condition="zawiera dwa kroki")
            result = run_workflow(incremental_wf, cfg=cfg)

        assert result.completed_goal is True
        assert result.iterations == 2  # zatrzymano po 2. iteracji
