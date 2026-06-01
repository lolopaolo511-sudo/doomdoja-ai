"""Unit testy runner.summarize() — czysta funkcja, zero zależności sieciowych."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from runner import summarize


def _make_results(model: str, statuses: list[str]) -> list[dict]:
    return [
        {"model": model, "status": s, "latency_s": 1.0, "tokens": 50}
        for s in statuses
    ]


def test_summarize_all_pass():
    results = _make_results("model-a", ["pass", "pass", "pass"])
    s = summarize(results)
    assert s["model-a"]["pass_rate"] == 100.0
    assert s["model-a"]["pass"] == 3
    assert s["model-a"]["fail"] == 0


def test_summarize_mixed():
    results = _make_results("model-a", ["pass", "pass", "fail", "fail"])
    s = summarize(results)
    assert s["model-a"]["pass_rate"] == 50.0


def test_summarize_multiple_models():
    results = (
        _make_results("model-a", ["pass", "fail"])
        + _make_results("model-b", ["pass", "pass", "pass"])
    )
    s = summarize(results)
    assert "model-a" in s and "model-b" in s
    assert s["model-b"]["pass_rate"] == 100.0
    assert s["model-a"]["pass_rate"] == 50.0


def test_summarize_error_excluded_from_pass_rate():
    results = _make_results("model-a", ["pass", "pass", "error"])
    s = summarize(results)
    # error nie wchodzi do pass_rate (tylko pass+fail)
    assert s["model-a"]["pass_rate"] == 100.0
    assert s["model-a"]["error"] == 1
