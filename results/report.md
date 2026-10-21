# Results

4 candidates, 24 tasks, one sample each. Candidates are simulated (see `src/paired_evals/simulate.py`); these numbers describe the pipeline, not any real model.

## Leaderboard, graded by execution

Rank band = 95% bootstrap interval of the Bradley-Terry rank, resampling tasks. Overlapping bands mean the data does not separate those models.

| Rank | Band | Model | Passed | Pass rate | 95% Wilson | BT score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-3 | model-a | 22/24 | 92% | 74%-98% | +1.00 |
| 2 | 1-3 | model-b | 21/24 | 88% | 69%-96% | +0.61 |
| 3 | 1-4 | model-d | 18/24 | 75% | 55%-88% | -0.14 |
| 4 | 3-4 | model-c | 14/24 | 58% | 39%-76% | -1.46 |

## What reading the code would have reported

Static grade = the answer parses, defines the function and has a real body. A false green is a task the static grade passed and execution failed.

| Model | Static pass | Executed pass | False greens | Rank if graded statically |
| --- | --- | --- | --- | --- |
| model-a | 96% | 92% | 1 | 1.5 |
| model-b | 96% | 88% | 2 | 3 |
| model-c | 75% | 58% | 4 | 4 |
| model-d | 96% | 75% | 5 | 1.5 |

12 of 87 static passes (14%) were wrong when executed.

## Pairwise tests

Exact McNemar on discordant tasks (one model passed, the other failed), Holm-adjusted across all pairs.

| A | B | Only A passed | Only B passed | p | p (Holm) | Separated at 0.05 |
| --- | --- | --- | --- | --- | --- | --- |
| model-a | model-b | 2 | 1 | 1.0000 | 1.0000 | no |
| model-a | model-c | 8 | 0 | 0.0078 | 0.0469 | yes |
| model-a | model-d | 6 | 2 | 0.2891 | 1.0000 | no |
| model-b | model-c | 7 | 0 | 0.0156 | 0.0781 | no |
| model-b | model-d | 6 | 3 | 0.5078 | 1.0000 | no |
| model-c | model-d | 2 | 6 | 0.2891 | 1.0000 | no |

## Execution outcomes

| Model | assertion | error | pass |
| --- | --- | --- | --- |
| model-a | 1 | 1 | 22 |
| model-b | 2 | 1 | 21 |
| model-c | 4 | 6 | 14 |
| model-d | 5 | 1 | 18 |
