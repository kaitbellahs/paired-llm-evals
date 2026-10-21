from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .grading import ExecResult, executed_grade, static_grade
from .stats import pairwise_mcnemar, rank_bands, wilson_interval
from .tasks import Task


@dataclass(frozen=True)
class Grade:
    task_id: str
    model: str
    static_pass: bool
    executed: ExecResult


def load_completions(path: str | Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def grade_all(tasks: list[Task], completions: list[dict], workers: int = 8) -> list[Grade]:
    by_id = {t.id: t for t in tasks}
    seen = set()
    for c in completions:
        if c["task_id"] not in by_id:
            raise ValueError(f"completion for unknown task {c['task_id']}")
        key = (c["model"], c["task_id"])
        if key in seen:
            raise ValueError(f"two completions for {key}; keep one sample per task and model")
        seen.add(key)
    models = {c["model"] for c in completions}
    for m in models:
        missing = set(by_id) - {c["task_id"] for c in completions if c["model"] == m}
        if missing:
            raise ValueError(f"{m} has no answer for {sorted(missing)}; paired tests need every task")

    def one(c: dict) -> Grade:
        task = by_id[c["task_id"]]
        return Grade(c["task_id"], c["model"], static_grade(c["completion"], task.entry), executed_grade(c["completion"], task))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        grades = list(pool.map(one, completions))
    order = {t.id: i for i, t in enumerate(tasks)}
    return sorted(grades, key=lambda g: (g.model, order[g.task_id]))


def outcomes(grades: list[Grade], field: str = "executed") -> dict[str, list[bool]]:
    out: dict[str, list[bool]] = {}
    for g in grades:
        passed = g.executed.passed if field == "executed" else g.static_pass
        out.setdefault(g.model, []).append(passed)
    return dict(sorted(out.items()))


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def render_report(grades: list[Grade], n_boot: int = 2000, seed: int = 0) -> str:
    executed = outcomes(grades, "executed")
    static = outcomes(grades, "static")
    n = len(next(iter(executed.values())))
    bands = rank_bands(executed, n_boot=n_boot, seed=seed)
    static_bands = {b.model: b for b in rank_bands(static, n_boot=n_boot, seed=seed)}

    lines = [
        "# Results",
        "",
        f"{len(executed)} candidates, {n} tasks, one sample each. Candidates are simulated "
        "(see `src/paired_evals/simulate.py`); these numbers describe the pipeline, not any real model.",
        "",
        "## Leaderboard, graded by execution",
        "",
        "Rank band = 95% bootstrap interval of the Bradley-Terry rank, resampling tasks. "
        "Overlapping bands mean the data does not separate those models.",
        "",
        "| Rank | Band | Model | Passed | Pass rate | 95% Wilson | BT score |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for b in bands:
        k = sum(executed[b.model])
        lo, hi = wilson_interval(k, n)
        band = f"{b.low:.0f}" if b.low == b.high else f"{b.low:.0f}-{b.high:.0f}"
        lines.append(
            f"| {b.rank:g} | {band} | {b.model} | {k}/{n} | {pct(k / n)} | {pct(lo)}-{pct(hi)} | {b.score:+.2f} |"
        )

    lines += [
        "",
        "## What reading the code would have reported",
        "",
        "Static grade = the answer parses, defines the function and has a real body. "
        "A false green is a task the static grade passed and execution failed.",
        "",
        "| Model | Static pass | Executed pass | False greens | Rank if graded statically |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in executed:
        fg = sum(1 for s, e in zip(static[m], executed[m]) if s and not e)
        sb = static_bands[m]
        lines.append(
            f"| {m} | {pct(sum(static[m]) / n)} | {pct(sum(executed[m]) / n)} | {fg} | {sb.rank:g} |"
        )
    total_fg = sum(1 for g in grades if g.static_pass and not g.executed.passed)
    total_static = sum(1 for g in grades if g.static_pass)
    lines += ["", f"{total_fg} of {total_static} static passes ({pct(total_fg / max(1, total_static))}) were wrong when executed."]

    lines += [
        "",
        "## Pairwise tests",
        "",
        "Exact McNemar on discordant tasks (one model passed, the other failed), Holm-adjusted across all pairs.",
        "",
        "| A | B | Only A passed | Only B passed | p | p (Holm) | Separated at 0.05 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for t in pairwise_mcnemar(executed):
        lines.append(
            f"| {t.a} | {t.b} | {t.a_only} | {t.b_only} | {t.p:.4f} | {t.p_holm:.4f} | {'yes' if t.p_holm < 0.05 else 'no'} |"
        )

    statuses = sorted({g.executed.status for g in grades})
    lines += ["", "## Execution outcomes", "", "| Model | " + " | ".join(statuses) + " |", "| --- |" + " --- |" * len(statuses)]
    for m in executed:
        c = Counter(g.executed.status for g in grades if g.model == m)
        lines.append(f"| {m} | " + " | ".join(str(c.get(s, 0)) for s in statuses) + " |")
    return "\n".join(lines) + "\n"


def write_grades(grades: list[Grade], path: str | Path) -> None:
    with open(path, "w") as f:
        for g in grades:
            f.write(
                json.dumps(
                    {
                        "task_id": g.task_id,
                        "model": g.model,
                        "static_pass": g.static_pass,
                        "executed_pass": g.executed.passed,
                        "status": g.executed.status,
                        "detail": g.executed.detail,
                    }
                )
                + "\n"
            )
