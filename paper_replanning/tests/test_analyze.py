"""Tests for the statistics helpers in analysis/analyze.py."""

import numpy as np
import pytest

from analysis.analyze import bootstrap_ci, holm, paired_test


def test_holm_matches_hand_computation():
    # p sorted: 0.01, 0.02, 0.04 -> 3*0.01=0.03, max(0.03, 2*0.02)=0.04, max(0.04, 1*0.04)=0.04
    assert np.allclose(holm([0.04, 0.01, 0.02]), [0.04, 0.03, 0.04])
    out = holm([np.nan, 0.5])
    assert np.isnan(out[0]) and out[1] == 0.5


def test_paired_test_counts_sign_and_ratio():
    dstar = [1, 2, 3, 10, 5]
    base = [2, 4, 3, 5, 0]
    r = paired_test(dstar, base)
    assert (r["wins"], r["ties"], r["losses"]) == (2, 1, 2)
    assert r["n_nonzero"] == 4
    # |d| = 1, 2, 5, 5 -> ranks 1, 2, 3.5, 3.5; D* better on the first two: (3 - 7) / 10
    assert r["r_rank_biserial"] == pytest.approx(-0.4)
    # ratio only where base > 0: 0.5, 0.5, 1.0, 2.0 -> median 0.75
    assert r["median_ratio"] == pytest.approx(0.75) and r["n_ratio"] == 4


def test_paired_test_all_ties_gives_no_p_value():
    r = paired_test([0, 0, 0], [0, 0, 0])
    assert r["ties"] == 3 and np.isnan(r["p"]) and np.isnan(r["r_rank_biserial"])


def test_bootstrap_ci_is_reproducible_and_contains_the_mean():
    x = np.arange(100.0)
    a, b = bootstrap_ci(x, 7, 2000), bootstrap_ci(x, 7, 2000)
    assert a == b
    mean, lo, hi = a
    assert lo < mean < hi and mean == pytest.approx(49.5)
