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

    # 4-point difference (1-10 scale) -> ~80% for higher, ~20% for lower (DraftKings formula)
    p_high = predict_1v1_win_probability(7.0, 5.0)
    p_low = predict_1v1_win_probability(5.0, 7.0)
    assert 0.78 <= p_high <= 0.82
    assert 0.18 <= p_low <= 0.22
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
    """Learning rate decreases with confidence."""
    # Low confidence = high learning rate
    lr_low = get_learning_rate(10, 0.1)
    # High confidence = low learning rate
    lr_high = get_learning_rate(10, 0.9)
    assert lr_low > lr_high
    assert lr_high >= 0.05


def test_alpha_increases_with_games():
    """Alpha (prior weight) increases as confidence grows."""
    a_low = get_alpha(10, 0.1)
    a_high = get_alpha(10, 0.9)
    assert a_high > a_low
    assert 0.9 <= a_high <= 0.95


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
    """Confidence grows with more games as RD base shrinks."""
    c0 = compute_confidence(0)
    c5 = compute_confidence(5)
    c25 = compute_confidence(25)
    
    assert c0 < c5 < c25
    assert c25 > 0.7


def test_confidence_penalizes_variance():
    """High variance (volatility) in rating history reduces confidence."""
    # Stable ratings
    c_stable = compute_confidence(10, [5.0, 5.1, 4.9, 5.0, 5.0])
    # Very volatile ratings
    c_volatile = compute_confidence(10, [1.0, 9.0, 2.0, 8.0, 1.0])
    
    # Due to volatility penalty, stable should have higher confidence
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
