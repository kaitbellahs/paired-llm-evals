# paired-llm-evals

Compare models on the same tasks, grade their answers by running them, and publish the ranking with the uncertainty it actually has.

Two things this repo cares about:

1. **A green check has to mean the thing ran.** Grading code by reading it (a reviewer skimming a diff, or a judge model) passes answers that look right and are wrong. Here every answer is executed against hidden tests in a separate process, and a pass only counts if the harness proves all tests ran.
2. **A leaderboard on 24 tasks is mostly noise, so say so.** Models are compared pairwise on the tasks they disagree on, and positions are published as bands, not single ranks.

Pure standard library at runtime. No API keys needed to run it.

## Results on the bundled data

The candidates are simulated (see [Data](#data)), so these numbers describe the method, not any real model. Full output in [`results/report.md`](results/report.md).

| Rank | Band | Model | Passed | 95% Wilson | BT score |
| --- | --- | --- | --- | --- | --- |
| 1 | 1-3 | model-a | 22/24 | 74%-98% | +1.00 |
| 2 | 1-3 | model-b | 21/24 | 69%-96% | +0.61 |
| 3 | 1-4 | model-d | 18/24 | 55%-88% | -0.14 |
| 4 | 3-4 | model-c | 14/24 | 39%-76% | -1.46 |

How to read it: model-a has the best point estimate, but its band overlaps with model-b and model-d, so this data does not support "a beats b". The exact McNemar tests agree: after Holm correction the only separated pair is a vs c.

Graded by reading instead of running, model-d would have tied for first (96% static pass rate against 75% executed). 12 of the 87 answers that looked right were wrong.

## Run it

```bash
uv run pytest                                    # 77 tests
uv run python -m paired_evals run                # grade data/completions.jsonl, write results/
uv run python -m paired_evals simulate --seed 7  # regenerate the simulated completions
```

Without uv: `pip install -e . pytest`, then the same commands without `uv run`.

### Grading your own models

Put one answer per model per task in a JSONL file:

```json
{"task_id": "median", "model": "my-model", "completion": "def median(nums):\n    ..."}
```

and run `python -m paired_evals run --completions your_file.jsonl`. Every model must answer every task, because the tests are paired. Missing or duplicate answers are an error, not something silently averaged over.

To use your own tasks, follow the format of [`data/tasks.toml`](data/tasks.toml): a prompt, the function name, hidden tests, a reference solution, and at least one plausible wrong solution.

**Executing model output runs untrusted code with your permissions.** The harness isolates the interpreter (`python -I`, minimal environment, temporary directory, timeout) but it is not a sandbox. Run real model outputs inside a container or VM with no network and no credentials.

## Design decisions

**Execution, with proof of completion.** Exit code 0 is not a pass. Code that calls `sys.exit(0)` or `os._exit(0)` at import time exits cleanly without running a single test, which is exactly the kind of green that looks fine in CI. The harness reads a random nonce from its environment and removes it before importing the answer, runs every test, and only then prints the nonce with the number of tests it ran. The parent process checks both. There are tests for early exit, hard exit, a faked report line, and the nonce not leaking to the answer.

This catches accidents, not an adversary. An answer written specifically to attack the harness (monkeypatching `json`, reading the parent's memory) is out of scope; that needs a real sandbox.

**The benchmark is tested like code.** Each task ships with mutants: wrong solutions that parse, define the function and have a real body. `tests/test_dataset.py` executes all of them and fails if the reference does not pass, if a mutant survives the hidden tests, or if a mutant would fail the static grader (then it is not a convincing mistake). A test suite that a wrong answer can pass would report false greens of its own.

**Paired tests, not two proportions.** All models answer the same tasks, so outcomes are paired. Tasks where both models pass or both fail say nothing about which is better. The exact McNemar test uses only the discordant tasks (one passed, the other failed), as a binomial test with p = 0.5. With several models every pair is tested, so p-values are Holm-adjusted.

**Bradley-Terry over discordant tasks for the ranking.** Each discordant task is one match won by the model that passed. Strengths are fit with Hunter's MM algorithm. A small prior (half a virtual win each way per pair) keeps the fit finite when a model never wins, which is common with few tasks, and shrinks estimates slightly toward a tie.

**Ranks as bands.** Tasks are resampled with replacement 2,000 times and Bradley-Terry is refit on each resample. The band is the 95% interval of the rank a model gets across resamples. Resampling tasks (not answers) is the right unit because the question is how much the ranking depends on which tasks happened to be in the set.

**Wilson intervals for single pass rates.** The normal approximation breaks near 0% and 100% and with small n, which is where small eval sets live. Wilson stays inside [0, 1] and behaves at the edges.

**Reproducible by construction.** The bootstrap and the simulator are seeded. `tests/test_report.py` regenerates the report from the committed completions and fails if it differs from `results/report.md`, so the numbers in this README come from the code in this repo.

## Data

24 small Python tasks in [`data/tasks.toml`](data/tasks.toml), written for this repo (clamp, median, roman numerals, interval merging and similar). No customer data and nothing scraped.

The four candidates are simulated by [`simulate.py`](src/paired_evals/simulate.py): each has a skill level, and on each task it returns the reference solution, one of the plausible mutants, or an unfinished answer. The point is to have realistic failure modes to grade offline. Replace `data/completions.jsonl` with real outputs to evaluate real models.

## Layout

```
src/paired_evals/
  grading.py    static grader, executing grader and harness
  stats.py      Wilson, exact McNemar, Holm, Bradley-Terry, bootstrap rank bands
  run.py        grading pipeline and report
  simulate.py   offline candidates
  tasks.py      dataset loader
tests/          stats against known values, grader edge cases, dataset self-check, report reproducibility
```

## License

MIT
