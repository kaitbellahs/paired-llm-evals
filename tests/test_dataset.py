"""The benchmark is code too, so it gets executed like everything else.

A test suite that a wrong answer can pass is a benchmark that reports false
greens. Every mutant must be killed and must still look right to a reader.
"""

from pathlib import Path

import pytest

from paired_evals.grading import executed_grade, static_grade
from paired_evals.tasks import load_tasks

TASKS = load_tasks(Path(__file__).parent.parent / "data" / "tasks.toml")


def test_dataset_shape():
    assert len(TASKS) >= 20
    assert all(t.tests and t.mutants for t in TASKS)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_passes(task):
    assert executed_grade(task.reference, task).status == "pass"


@pytest.mark.parametrize(
    "task,mutant",
    [(t, m) for t in TASKS for m in t.mutants],
    ids=lambda x: x.id if hasattr(x, "id") else "",
)
def test_every_mutant_is_killed_but_looks_right(task, mutant):
    assert static_grade(mutant, task.entry), "mutant should pass the static grader"
    assert executed_grade(mutant, task).passed is False, "tests did not catch this mutant"
