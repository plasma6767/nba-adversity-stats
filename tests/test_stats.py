import pytest

from nba_adversity_stats.stats import _pct_diff, _shot_pool_stats


def test_shot_pool_stats_empty():
    result = _shot_pool_stats([])
    assert result["n_fg"] == 0
    assert result["fg_pct"] is None
    assert result["n_3pt"] == 0
    assert result["three_pct"] is None


def test_shot_pool_stats_mixed_makes_and_misses():
    shots = [
        {"made": True, "shot_value": 2},
        {"made": False, "shot_value": 2},
        {"made": True, "shot_value": 3},
        {"made": False, "shot_value": 3},
        {"made": False, "shot_value": 3},
    ]
    result = _shot_pool_stats(shots)
    assert result["n_fg"] == 5
    assert result["fg_made"] == 2
    assert result["fg_pct"] == 2 / 5
    assert result["n_3pt"] == 3
    assert result["three_made"] == 1
    assert result["three_pct"] == 1 / 3


def test_shot_pool_stats_no_threes_taken():
    shots = [{"made": True, "shot_value": 2}, {"made": False, "shot_value": 2}]
    result = _shot_pool_stats(shots)
    assert result["fg_pct"] == 0.5
    assert result["n_3pt"] == 0
    assert result["three_pct"] is None  # not 0% -- genuinely no data, not a bad shooting night


def test_pct_diff_normal_case():
    assert _pct_diff(0.40, 0.50) == pytest.approx(-0.10)


def test_pct_diff_none_when_post_missing():
    assert _pct_diff(None, 0.50) is None


def test_pct_diff_none_when_baseline_missing():
    assert _pct_diff(0.40, None) is None


def test_pct_diff_none_when_both_missing():
    assert _pct_diff(None, None) is None
