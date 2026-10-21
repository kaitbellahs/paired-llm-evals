"""Simulated candidates, so the pipeline has something to grade offline.

The numbers this produces say nothing about any real model. Each fake model
has a skill level; on each task it either returns the reference solution,
one of the task's plausible-but-wrong mutants, or an obviously unfinished
answer. Swap the output for real completions in the same JSONL format.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .tasks import Task


@dataclass(frozen=True)
class FakeModel:
    name: str
    skill: float
    plausible_when_wrong: float  # share of wrong answers that look right


MODELS = (
    FakeModel("model-a", skill=3.0, plausible_when_wrong=0.5),
    FakeModel("model-b", skill=1.8, plausible_when_wrong=0.6),
    FakeModel("model-c", skill=1.6, plausible_when_wrong=0.3),
    FakeModel("model-d", skill=0.6, plausible_when_wrong=0.9),
)


def unfinished(task: Task, rng: random.Random) -> str:
    args = task.reference.split(f"def {task.entry}(", 1)[1].split(")", 1)[0]
    if rng.random() < 0.5:
        return f"def {task.entry}({args}):\n    # TODO: handle edge cases\n    raise NotImplementedError\n"
    body = task.reference.strip().splitlines()
    return "\n".join(body[: max(2, len(body) // 2)]) + "\n    return (\n"


def simulate(tasks: list[Task], seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for model in MODELS:
        for task in tasks:
            p_correct = 1 / (1 + math.exp(-(model.skill - (task.difficulty - 1))))
            if rng.random() < p_correct:
                code = task.reference
            elif task.mutants and rng.random() < model.plausible_when_wrong:
                code = rng.choice(task.mutants)
            else:
                code = unfinished(task, rng)
            rows.append({"task_id": task.id, "model": model.name, "completion": code.strip() + "\n"})
    return rows


def write_jsonl(rows: list[dict], path: str | Path) -> None:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
