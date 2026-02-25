"""
Accuracy tests for rating and prediction models.

Covers: 1v1 Elo win predictor, position-aware rating, K-factor decay,
confidence (Bayesian-inspired), and player matching distance metric.
"""
import math
import pytest
from app.ai.win_predictor import predict_1v1_win_probability
from app.ai.rating import (
    get_learning_rate,
    get_alpha,
    compute_confidence,
    compute_game_performance_rating,
    _get_position_weights,
)
from app.ai.player_match import _parse_height, _distance


# ─── 1v1 Win Predictor (Elo-style logistic) ────────────────────────────────

def test_1v1_win_probability_exact_elo():
    """Elo formula: P(A beats B) = 1 / (1 + 10^((B-A)/400)). Scale 1-10 uses divisor 4."""
    # Equal rating -> exactly 0.5
    assert predict_1v1_win_probability(5.0, 5.0) == 0.5

    # 4-point difference (1-10 scale) -> ~76% for higher, ~24% for lower
    p_high = predict_1v1_win_probability(7.0, 5.0)
    p_low = predict_1v1_win_probability(5.0, 7.0)
    assert 0.74 <= p_high <= 0.78
    assert 0.22 <= p_low <= 0.26
    assert abs((p_high + p_low) - 1.0) < 0.001


def test_1v1_win_probability_symmetry():
    """P(A beats B) + P(B beats A) = 1."""
    for ra, rb in [(3.0, 7.0), (1.0, 10.0), (4.5, 6.2)]:
        p_ab = predict_1v1_win_probability(ra, rb)
        p_ba = predict_1v1_win_probability(rb, ra)
        assert abs((p_ab + p_ba) - 1.0) < 1e-10


def test_1v1_win_probability_monotonicity():
    """Higher rating A -> higher P(A beats B)."""
    rb = 5.0
    prev = 0.0
    for ra in [1.0, 3.0, 5.0, 7.0, 9.0]:
        p = predict_1v1_win_probability(ra, rb)
        assert p >= prev
        prev = p


# ─── Rating: K-factor decay ────────────────────────────────────────────────

def test_learning_rate_decay():
    """Learning rate decreases with games (sqrt decay)."""
    lr_0 = get_learning_rate(0)
    lr_5 = get_learning_rate(5)
    lr_25 = get_learning_rate(25)
    lr_50 = get_learning_rate(50)
    assert lr_0 >= lr_5 >= lr_25 >= lr_50
    assert lr_0 <= 0.25  # Capped for first few games
    assert lr_50 < 0.1


def test_alpha_increases_with_games():
    """Alpha (prior weight) increases as history grows."""
    a0 = get_alpha(0)
    a10 = get_alpha(10)
    a30 = get_alpha(30)
    assert a0 < a10 < a30
    assert 0.7 <= a0 <= 0.8
    assert a30 > 0.9


# ─── Rating: Position-aware performance ────────────────────────────────────

def test_compute_game_performance_rating_bounds():
    """Performance rating always in [1, 10]."""
    class MockStats:
        pts = reb = ast = stl = blk = tov = 0
        fgm = fga = three_pm = three_pa = ftm = fta = 0

    class MockGame:
        game_type = "5v5"

    for won in [True, False]:
        r = compute_game_performance_rating(MockStats(), MockGame(), won=won, score_margin=15, avg_opponent_rating=5.0)
        assert 1.0 <= r <= 10.0


def test_compute_game_performance_rating_win_vs_loss():
    """Winning yields higher performance rating than losing (same stats)."""
    class MockStats:
        pts, reb, ast, stl, blk, tov = 6, 3, 2, 1, 0, 1
        fgm, fga, three_pm, three_pa, ftm, fta = 3, 6, 0, 0, 0, 0

    class MockGame:
        game_type = "5v5"

    r_win = compute_game_performance_rating(MockStats(), MockGame(), won=True, score_margin=5, avg_opponent_rating=5.0)
    r_loss = compute_game_performance_rating(MockStats(), MockGame(), won=False, score_margin=5, avg_opponent_rating=5.0)
    assert r_win > r_loss


def test_compute_game_performance_rating_better_stats_higher():
    """Better stats (more pts, reb, ast) yield higher performance rating."""
    class MockGame:
        game_type = "5v5"

    class MockStatsLow:
        pts, reb, ast, stl, blk, tov = 2, 1, 0, 0, 0, 2
        fgm, fga, three_pm, three_pa, ftm, fta = 1, 5, 0, 0, 0, 0

    class MockStatsHigh:
        pts, reb, ast, stl, blk, tov = 12, 6, 4, 2, 1, 1
        fgm, fga, three_pm, three_pa, ftm, fta = 6, 10, 2, 4, 2, 2

    r_low = compute_game_performance_rating(MockStatsLow(), MockGame(), won=True, score_margin=5, avg_opponent_rating=5.0)
    r_high = compute_game_performance_rating(MockStatsHigh(), MockGame(), won=True, score_margin=5, avg_opponent_rating=5.0)
    assert r_high > r_low


def test_position_weights_pg_vs_c():
    """PG: assists/steals matter more. C: rebounds/blocks matter more."""
    pg = _get_position_weights("PG")
    c = _get_position_weights("C")
    assert pg["apg"] > c["apg"]
    assert pg["spg"] > c["spg"]
    assert c["rpg"] > pg["rpg"]
    assert c["bpg"] > pg["bpg"]
    assert pg["topg"] < 0  # Low TOV is good
    assert c["topg"] < 0


# ─── Confidence (Bayesian-inspired) ─────────────────────────────────────────

def test_confidence_increases_with_games():
    """Confidence grows with more games (1 - exp decay)."""
    c0 = compute_confidence(0)
    c5 = compute_confidence(5)
    c15 = compute_confidence(15)
    assert c0 == 0
    assert 0 < c5 < c15
    assert c15 > 0.9


def test_confidence_penalizes_variance():
    """High variance in rating history reduces confidence."""
    c_stable = compute_confidence(10, [5.0, 5.1, 4.9, 5.0, 5.0])
    c_volatile = compute_confidence(10, [3.0, 7.0, 5.0, 4.0, 6.0])
    assert c_stable > c_volatile


# ─── Player matching (distance metric) ─────────────────────────────────────

def test_parse_height():
    """Height parsing: feet'inches" -> inches."""
    assert _parse_height("6'2\"") == 74
    assert _parse_height("5'10") == 70
    assert _parse_height(None) == 70
    assert _parse_height("") == 70
    assert 60 <= _parse_height("7'0") <= 96


def test_distance_metric():
    """Euclidean distance with weights; identical points = 0."""
    a = (0.5, 0.5, 0.5, 0.5)
    w = (1.0, 1.0, 1.0, 1.0)
    assert _distance(a, a, w) == 0
    assert _distance(a, (0.5, 0.5, 0.5, 0.6), w) > 0
    # Triangle inequality
    b, c = (0.4, 0.4, 0.4, 0.4), (0.6, 0.6, 0.6, 0.6)
    d_ab = _distance(a, b, w)
    d_bc = _distance(b, c, w)
    d_ac = _distance(a, c, w)
    assert d_ac <= d_ab + d_bc + 1e-9
