from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    id: str
    entry: str
    prompt: str
    tests: tuple[str, ...]
    reference: str
    mutants: tuple[str, ...]
    difficulty: int


def load_tasks(path: str | Path) -> list[Task]:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    tasks = [
        Task(
            id=t["id"],
            entry=t["entry"],
            prompt=t["prompt"],
            tests=tuple(t["tests"]),
            reference=t["reference"],
            mutants=tuple(t.get("mutants", ())),
            difficulty=int(t.get("difficulty", 2)),
        )
        for t in raw["task"]
    ]
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    return tasks
