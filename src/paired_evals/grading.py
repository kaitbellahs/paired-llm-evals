"""Two graders for the same completions.

`static_grade` reads the code: it parses, defines the requested function and
has a real body. That is roughly what a reviewer skimming a diff, or a judge
model reading it, can confirm.

`executed_grade` runs the code against hidden tests in a separate Python
process and only counts a pass if the harness itself reports that every
test ran. Exit code 0 is not enough on its own: code that calls sys.exit(0)
at import time also exits with 0.
"""

from __future__ import annotations

import ast
import json
import os
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .tasks import Task

TIMEOUT_SECONDS = 5.0

HARNESS = r'''
import importlib.util, json, os, sys

nonce = os.environ.pop("EVAL_NONCE")
spec = json.loads(os.environ.pop("EVAL_SPEC"))

module_spec = importlib.util.spec_from_file_location("solution", "solution.py")
solution = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(solution)
fn = getattr(solution, spec["entry"])

ran = 0
for test in spec["tests"]:
    exec(test, {spec["entry"]: fn})
    ran += 1

sys.stdout.write("\n" + json.dumps({"nonce": nonce, "ran": ran}) + "\n")
sys.stdout.flush()
'''


@dataclass(frozen=True)
class ExecResult:
    passed: bool
    status: str  # pass | assertion | error | timeout | exited_early
    detail: str = ""


def static_grade(code: str, entry: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == entry:
            body = [n for n in node.body if not _is_docstring(n)]
            return not all(_is_placeholder(n) for n in body)
    return False


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _is_placeholder(node: ast.stmt) -> bool:
    if isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value.value is Ellipsis:
        return True
    if isinstance(node, ast.Raise):
        exc = node.exc
        name = exc.func.id if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) else getattr(exc, "id", "")
        return name == "NotImplementedError"
    return False


def executed_grade(code: str, task: Task, timeout: float = TIMEOUT_SECONDS) -> ExecResult:
    nonce = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
        Path(tmp, "solution.py").write_text(code)
        Path(tmp, "harness.py").write_text(HARNESS)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "EVAL_NONCE": nonce,
            "EVAL_SPEC": json.dumps({"entry": task.entry, "tests": list(task.tests)}),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "harness.py"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(False, "timeout", f"no result after {timeout}s")

    if proc.returncode != 0:
        last = proc.stderr.strip().splitlines()[-1:] or [""]
        status = "assertion" if last[0].startswith("AssertionError") else "error"
        return ExecResult(False, status, last[0][:200])

    lines = proc.stdout.strip().splitlines()
    try:
        report = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError:
        report = {}
    if report.get("nonce") != nonce or report.get("ran") != len(task.tests):
        return ExecResult(False, "exited_early", "exit code 0 but the harness never reported")
    return ExecResult(True, "pass")
