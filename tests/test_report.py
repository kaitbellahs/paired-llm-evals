"""The committed report must be what the committed code produces."""

from pathlib import Path

from paired_evals.run import grade_all, load_completions, render_report
from paired_evals.simulate import simulate
from paired_evals.tasks import load_tasks

ROOT = Path(__file__).parent.parent


def test_committed_completions_match_the_simulator():
    tasks = load_tasks(ROOT / "data" / "tasks.toml")
    assert simulate(tasks, seed=7) == load_completions(ROOT / "data" / "completions.jsonl")


def test_committed_report_is_reproducible():
    tasks = load_tasks(ROOT / "data" / "tasks.toml")
    grades = grade_all(tasks, load_completions(ROOT / "data" / "completions.jsonl"))
    assert render_report(grades) == (ROOT / "results" / "report.md").read_text()


def test_incomplete_pairs_are_refused():
    tasks = load_tasks(ROOT / "data" / "tasks.toml")
    rows = [r for r in load_completions(ROOT / "data" / "completions.jsonl") if not (r["model"] == "model-a" and r["task_id"] == "clamp")]
    try:
        grade_all(tasks, rows)
    except ValueError as e:
        assert "paired tests need every task" in str(e)
    else:
        raise AssertionError("expected ValueError")
