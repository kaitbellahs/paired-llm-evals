from paired_evals.grading import executed_grade, static_grade
from paired_evals.tasks import Task

TASK = Task(
    id="add",
    entry="add",
    prompt="add(a, b)",
    tests=("assert add(1, 2) == 3", "assert add(-1, 1) == 0"),
    reference="def add(a, b):\n    return a + b\n",
    mutants=(),
    difficulty=1,
)


def run(code: str, timeout: float = 5.0):
    return executed_grade(code, TASK, timeout=timeout)


def test_correct_code_passes():
    assert run(TASK.reference).status == "pass"


def test_wrong_code_fails_on_assertion():
    r = run("def add(a, b):\n    return a - b\n")
    assert (r.passed, r.status) == (False, "assertion")


def test_exit_zero_before_tests_is_not_a_pass():
    # The classic false green: the process exits cleanly, nothing was tested.
    code = "import sys\ndef add(a, b):\n    return a - b\nsys.exit(0)\n"
    r = run(code)
    assert (r.passed, r.status) == (False, "exited_early")


def test_hard_exit_is_not_a_pass():
    code = "import os\ndef add(a, b):\n    return 0\nos._exit(0)\n"
    assert run(code).status == "exited_early"


def test_printing_a_fake_report_is_not_a_pass():
    code = (
        "import json, sys, atexit\n"
        "def add(a, b):\n    return 0\n"
        "print(json.dumps({'nonce': 'guess', 'ran': 2}))\n"
        "sys.exit(0)\n"
    )
    assert run(code).status == "exited_early"


def test_swallowing_errors_inside_the_function_still_fails():
    code = "def add(a, b):\n    try:\n        raise ValueError\n    except Exception:\n        return None\n"
    assert run(code).status == "assertion"


def test_infinite_loop_times_out():
    code = "def add(a, b):\n    while True:\n        pass\n"
    assert run(code, timeout=1.0).status == "timeout"


def test_syntax_error_fails_both_graders():
    code = "def add(a, b):\n    return (\n"
    assert static_grade(code, "add") is False
    assert run(code).status == "error"


def test_static_grader_accepts_plausible_wrong_code():
    # This is the gap the executed grader exists to close.
    wrong = "def add(a, b):\n    return a - b\n"
    assert static_grade(wrong, "add") is True
    assert run(wrong).passed is False


def test_static_grader_rejects_stubs_and_missing_functions():
    assert not static_grade("def add(a, b):\n    pass\n", "add")
    assert not static_grade('def add(a, b):\n    """Adds."""\n    ...\n', "add")
    assert not static_grade("def add(a, b):\n    raise NotImplementedError\n", "add")
    assert not static_grade("def plus(a, b):\n    return a + b\n", "add")


def test_solution_does_not_see_the_nonce():
    code = "import os\nLEAK = os.environ.get('EVAL_NONCE')\ndef add(a, b):\n    assert LEAK is None\n    return a + b\n"
    assert run(code).status == "pass"
