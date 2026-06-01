"""Unit testy eval_lite.py — testują scoring logic bez Ollamy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from eval_lite import compute_pass_rate, run_lite, score_task


# ── score_task ────────────────────────────────────────────────────────────────

def test_score_substring_pass():
    task = {"id": "t1", "expected_substring": "def fizzbuzz"}
    res = score_task(task, "def fizzbuzz(n): pass")
    assert res["status"] == "pass"
    assert res["fail_reasons"] == []


def test_score_substring_fail():
    task = {"id": "t1", "expected_substring": "def fizzbuzz"}
    res = score_task(task, "totally unrelated response")
    assert res["status"] == "fail"
    assert len(res["fail_reasons"]) == 1


def test_score_regex_pass():
    task = {"id": "t1", "expected_regex": r"O\(1\)"}
    res = score_task(task, "złożoność to O(1)")
    assert res["status"] == "pass"


def test_score_regex_fail():
    task = {"id": "t1", "expected_regex": r"O\(1\)"}
    res = score_task(task, "złożoność to O(n)")
    assert res["status"] == "fail"


def test_score_both_criteria():
    task = {
        "id": "t1",
        "expected_substring": "def fizzbuzz",
        "expected_regex": r"(?:Fizz|fizz).*(?:Buzz|buzz)",
    }
    res = score_task(task, "def fizzbuzz(n): # FizzBuzz")
    assert res["status"] == "pass"


def test_score_case_insensitive():
    task = {"id": "t1", "expected_substring": "too many requests"}
    res = score_task(task, "HTTP 429: Too Many Requests")
    assert res["status"] == "pass"


# ── compute_pass_rate ─────────────────────────────────────────────────────────

def test_pass_rate_all_pass():
    results = [{"status": "pass"}, {"status": "pass"}, {"status": "pass"}]
    assert compute_pass_rate(results) == 100.0


def test_pass_rate_half():
    results = [{"status": "pass"}, {"status": "fail"}]
    assert compute_pass_rate(results) == 50.0


def test_pass_rate_skipped_excluded():
    # skipped nie wchodzi do mianownika
    results = [{"status": "pass"}, {"status": "skipped"}, {"status": "fail"}]
    assert compute_pass_rate(results) == 50.0


def test_pass_rate_empty():
    assert compute_pass_rate([]) == 100.0


# ── run_lite integration ──────────────────────────────────────────────────────

def test_run_lite_known_tasks_pass():
    tasks = [
        {"id": "code_fizzbuzz", "category": "coding",
         "expected_substring": "def fizzbuzz",
         "expected_regex": r"(?:Fizz|fizz).*(?:Buzz|buzz)"},
        {"id": "rag_python_dict", "category": "knowledge",
         "expected_substring": "O(1)"},
    ]
    results = run_lite(tasks)
    assert all(r["status"] == "pass" for r in results)


def test_run_lite_fail_some_simulates_failures():
    tasks = [
        {"id": "reason_math",  "category": "reasoning", "expected_substring": "80"},
        {"id": "reason_word",  "category": "reasoning", "expected_substring": "enihcam"},
        {"id": "rag_python_dict", "category": "knowledge", "expected_substring": "O(1)"},
    ]
    results = run_lite(tasks, fail_some=True)
    statuses = {r["id"]: r["status"] for r in results}
    assert statuses["reason_math"] == "fail"
    assert statuses["reason_word"] == "fail"
    assert statuses["rag_python_dict"] == "pass"


def test_run_lite_vision_skipped_when_no_image(tmp_path):
    tasks = [
        {"id": "vision_describe", "category": "vision",
         "image_path": str(tmp_path / "nonexistent.png"),
         "expected_substring": "."},
    ]
    results = run_lite(tasks)
    assert results[0]["status"] == "skipped"
