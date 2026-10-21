import math

import pytest

from paired_evals.stats import (
    bradley_terry,
    holm,
    mcnemar_exact,
    pairwise_mcnemar,
    pairwise_wins,
    rank_bands,
    ranks,
    wilson_interval,
)


def test_wilson_matches_known_values():
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4)
    assert hi == pytest.approx(0.7634, abs=1e-4)


def test_wilson_stays_inside_unit_interval_at_the_edges():
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    lo, hi = wilson_interval(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.7225, abs=1e-4)


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(0, 6) == pytest.approx(2 / 64)
    assert mcnemar_exact(6, 0) == mcnemar_exact(0, 6)
    assert mcnemar_exact(3, 3) == 1.0
    # 1 vs 9: 2 * (C(10,0) + C(10,1)) / 2^10
    assert mcnemar_exact(1, 9) == pytest.approx(2 * 11 / 1024)


def test_mcnemar_ignores_agreement():
    # Same discordant counts, very different numbers of shared passes.
    a = {"x": [True] * 50 + [True, False], "y": [True] * 50 + [False, True]}
    b = {"x": [True, False], "y": [False, True]}
    assert pairwise_mcnemar(a)[0].p == pairwise_mcnemar(b)[0].p


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])


def test_bradley_terry_symmetric_data_gives_equal_scores():
    wins = {("a", "b"): 4, ("b", "a"): 4}
    s = bradley_terry(["a", "b"], wins)
    assert s["a"] == pytest.approx(s["b"])
    assert s["a"] + s["b"] == pytest.approx(0)


def test_bradley_terry_two_player_closed_form():
    # With prior p, strength ratio is (w_ab + p) / (w_ba + p).
    s = bradley_terry(["a", "b"], {("a", "b"): 7, ("b", "a"): 1}, prior=0.5)
    assert math.exp(s["a"] - s["b"]) == pytest.approx(7.5 / 1.5)


def test_bradley_terry_stays_finite_when_a_model_never_wins():
    s = bradley_terry(["a", "b", "c"], {("a", "b"): 5, ("b", "a"): 0, ("a", "c"): 5, ("c", "a"): 0, ("b", "c"): 5, ("c", "b"): 0})
    assert all(math.isfinite(v) for v in s.values())
    assert s["a"] > s["b"] > s["c"]


def test_ranks_share_ties():
    assert ranks({"a": 1.0, "b": 1.0, "c": 0.0}) == {"a": 1.5, "b": 1.5, "c": 3}


def test_rank_bands_separate_clear_differences_and_merge_close_ones():
    n = 60
    outcomes = {
        "strong": [True] * n,
        "close": [True] * (n - 1) + [False],
        "weak": [i % 4 == 0 for i in range(n)],
    }
    bands = {b.model: b for b in rank_bands(outcomes, n_boot=300, seed=1)}
    assert bands["weak"].low == bands["weak"].high == 3
    assert bands["strong"].low == 1 and bands["close"].low == 1  # cannot be told apart


def test_rank_bands_are_reproducible():
    outcomes = {"a": [True, False, True, True], "b": [False, False, True, True]}
    assert rank_bands(outcomes, n_boot=200, seed=3) == rank_bands(outcomes, n_boot=200, seed=3)


def test_pairwise_wins():
    w = pairwise_wins({"a": [True, True, False], "b": [False, True, True]})
    assert w == {("a", "b"): 1, ("b", "a"): 1}
