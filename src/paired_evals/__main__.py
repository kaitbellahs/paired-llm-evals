from __future__ import annotations

import argparse
from pathlib import Path

from .run import grade_all, load_completions, render_report, write_grades
from .simulate import simulate, write_jsonl
from .tasks import load_tasks


def main() -> None:
    parser = argparse.ArgumentParser(prog="paired_evals")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="write simulated completions")
    s.add_argument("--tasks", default="data/tasks.toml")
    s.add_argument("--out", default="data/completions.jsonl")
    s.add_argument("--seed", type=int, default=7)

    r = sub.add_parser("run", help="grade completions and write the report")
    r.add_argument("--tasks", default="data/tasks.toml")
    r.add_argument("--completions", default="data/completions.jsonl")
    r.add_argument("--out", default="results")
    r.add_argument("--bootstrap", type=int, default=2000)
    r.add_argument("--seed", type=int, default=0)

    args = parser.parse_args()
    tasks = load_tasks(args.tasks)

    if args.cmd == "simulate":
        write_jsonl(simulate(tasks, args.seed), args.out)
        print(f"wrote {args.out}")
        return

    grades = grade_all(tasks, load_completions(args.completions))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_grades(grades, out / "grades.jsonl")
    report = render_report(grades, n_boot=args.bootstrap, seed=args.seed)
    (out / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
