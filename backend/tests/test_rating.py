"""Tests for rating and player_match modules."""
import pytest
from app.ai.rating import (
    compute_game_performance_rating,
    get_alpha,
    get_learning_rate,
    compute_confidence,
    _get_position_weights,
)
from app.ai.player_match import find_matches, find_complementary_teammates, _get_career_stats


def test_get_alpha():
    """K-factor decay: depends on confidence and games played."""
    assert 0.7 <= get_alpha(0) <= 0.8  # Default confidence 0.5 -> lr 0.25 -> alpha 0.75
    assert get_alpha(10, current_confidence=0.8) == 0.9  # High confidence -> alpha 0.9
    assert get_alpha(30, current_confidence=0.95) == 0.95  # Max confidence -> alpha 0.95
    assert get_learning_rate(0, 0.2) > get_learning_rate(50, 0.9)  # Decay with confidence


def test_compute_confidence():
    assert compute_confidence(0) == 0.05  # Minimum bound
    assert compute_confidence(10) > 0.5  # Confidence rises with games
    assert compute_confidence(5, [5.0, 5.0, 5.0]) > compute_confidence(5, [3.0, 7.0, 5.0])


def test_position_weights():
    w = _get_position_weights("PG")
    assert w["apg"] > w["rpg"]
    w = _get_position_weights("C")
    assert w["rpg"] > w["apg"]


def test_compute_game_performance_rating():
    from datetime import datetime, timezone
    from app.models import PlayerGameStats, Game

    class MockStats:
        pts = 8
        reb = 4
        ast = 2
        stl = 1
        blk = 0
        tov = 2
        fgm = 4
        fga = 10
        three_pm = 0
        ftm = 0
        fta = 0

    class MockGame:
        game_type = "5v5"

    r = compute_game_performance_rating(
        MockStats(), MockGame(), won=True, score_margin=5, avg_opponent_rating=5.0
    )
    assert 1 <= r <= 10


def test_find_matches(client, auth_headers, db):
    """Find similar players."""
    users = client.get("/api/users/match?limit=5", headers=auth_headers)
    assert users.status_code == 200
    # Only one other user (second_auth_headers not used), so may be empty or have 1
    assert isinstance(users.json(), list)


def test_find_complementary_teammates(client, auth_headers, second_auth_headers, db):
    """Find complementary teammates."""
    # Need at least 2 users
    teammates = find_complementary_teammates(db, 1, limit=5)
    assert isinstance(teammates, list)
    # User 1 exists from auth_headers; user 2 from second_auth_headers
    assert len(teammates) <= 5


def test_get_career_stats_empty(db):
    """User with no games has zero stats."""
    stats = _get_career_stats(db, 99999)
    assert stats["ppg"] == 0
    assert stats["rpg"] == 0
    assert stats["apg"] == 0
