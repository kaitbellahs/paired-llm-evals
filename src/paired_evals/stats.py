"""Small, dependency-free statistics for paired pass/fail evaluations.

Every model answers the same tasks, so results are paired. That pairing is
the whole reason these tests are used instead of comparing two pass rates
as if they came from independent samples.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

Z_95 = 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Unlike the normal approximation it stays inside [0, 1] and behaves at
    0/n and n/n, which is where small eval sets usually live.
    """
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if successes == 0 else max(0.0, centre - half)
    hi = 1.0 if successes == n else min(1.0, centre + half)
    return (lo, hi)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar test.

    b: tasks only the first model solved. c: tasks only the second solved.
    Tasks both solved or both failed carry no information about which model
    is better and are ignored. Under the null each discordant task is a fair
    coin, so this is a binomial test on b out of b + c.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm step-down adjustment for running several pairwise tests at once."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def pairwise_wins(outcomes: dict[str, Sequence[bool]]) -> dict[tuple[str, str], int]:
    """wins[(a, b)] = number of tasks a passed and b failed."""
    models = list(outcomes)
    wins = {}
    for a in models:
        for b in models:
            if a != b:
                wins[(a, b)] = sum(1 for x, y in zip(outcomes[a], outcomes[b]) if x and not y)
    return wins


def bradley_terry(
    models: Sequence[str],
    wins: dict[tuple[str, str], int],
    prior: float = 0.5,
    tol: float = 1e-10,
    max_iter: int = 10_000,
) -> dict[str, float]:
    """Bradley-Terry strengths via Hunter's MM algorithm, on a log scale.

    Each discordant task is one "match". `prior` adds that many virtual wins
    in each direction for every pair, which keeps the fit finite when a model
    never wins (common with few tasks) and pulls estimates gently toward a tie.
    Scores are centred so they average zero; only differences mean anything.
    """
    w = {k: v + prior for k, v in wins.items()}
    p = {m: 1.0 for m in models}
    for _ in range(max_iter):
        new = {}
        for i in models:
            total_wins = sum(w[(i, j)] for j in models if j != i)
            denom = sum((w[(i, j)] + w[(j, i)]) / (p[i] + p[j]) for j in models if j != i)
            new[i] = total_wins / denom
        geo = math.exp(sum(math.log(v) for v in new.values()) / len(new))
        new = {m: v / geo for m, v in new.items()}
        delta = max(abs(new[m] - p[m]) for m in models)
        p = new
        if delta < tol:
            break
    return {m: math.log(v) for m, v in p.items()}


def ranks(scores: dict[str, float]) -> dict[str, float]:
    """Rank 1 is best. Ties share the average of the ranks they span."""
    ordered = sorted(scores, key=lambda m: -scores[m])
    out: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and math.isclose(scores[ordered[j + 1]], scores[ordered[i]]):
            j += 1
        for k in range(i, j + 1):
            out[ordered[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


@dataclass(frozen=True)
class RankBand:
    model: str
    score: float
    rank: float
    low: float
    high: float


def rank_bands(
    outcomes: dict[str, Sequence[bool]],
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> list[RankBand]:
    """Rank of each model with a bootstrap interval over tasks.

    Tasks are resampled with replacement and Bradley-Terry is refitted on
    each resample. A band like 1-2 means the data cannot tell this model
    apart from at least one neighbour; publishing the band instead of a
    single position is the honest way to report a leaderboard on few tasks.
    """
    models = list(outcomes)
    n_tasks = len(next(iter(outcomes.values())))
    point = bradley_terry(models, pairwise_wins(outcomes))
    point_rank = ranks(point)

    rng = random.Random(seed)
    samples: dict[str, list[float]] = {m: [] for m in models}
    for _ in range(n_boot):
        idx = [rng.randrange(n_tasks) for _ in range(n_tasks)]
        resampled = {m: [outcomes[m][i] for i in idx] for m in models}
        r = ranks(bradley_terry(models, pairwise_wins(resampled)))
        for m in models:
            samples[m].append(r[m])

    alpha = (1 - level) / 2
    bands = []
    for m in models:
        s = sorted(samples[m])
        lo = s[int(math.floor(alpha * (len(s) - 1)))]
        hi = s[int(math.ceil((1 - alpha) * (len(s) - 1)))]
        bands.append(RankBand(m, point[m], point_rank[m], math.floor(lo), math.ceil(hi)))
    return sorted(bands, key=lambda b: (b.rank, b.model))


@dataclass(frozen=True)
class PairTest:
    a: str
    b: str
    a_only: int
    b_only: int
    p: float
    p_holm: float


def pairwise_mcnemar(outcomes: dict[str, Sequence[bool]]) -> list[PairTest]:
    pairs = list(combinations(outcomes, 2))
    wins = pairwise_wins(outcomes)
    raw = [mcnemar_exact(wins[(a, b)], wins[(b, a)]) for a, b in pairs]
    adj = holm(raw)
    return [
        PairTest(a, b, wins[(a, b)], wins[(b, a)], p, q)
        for (a, b), p, q in zip(pairs, raw, adj)
    ]
