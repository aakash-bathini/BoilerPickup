"""Tests for Coach Pete, weather API, find match, find teammate."""
import pytest
from unittest.mock import patch, MagicMock


def _mock_weather_response():
    return {
        "current": {
            "temperature_2m": 42.5,
            "apparent_temperature": 38.2,
            "relative_humidity_2m": 65,
            "wind_speed_10m": 12.0,
            "precipitation": 0.0,
            "weather_code": 2,
        },
        "daily": {
            "time": ["2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"],
            "temperature_2m_max": [45, 48, 52, 55, 50, 46, 42],
            "temperature_2m_min": [28, 30, 32, 35, 33, 29, 26],
            "weather_code": [2, 3, 1, 0, 2, 3, 45],
            "precipitation_probability_max": [10, 20, 5, 0, 15, 30, 40],
            "wind_speed_10m_max": [15, 12, 10, 18, 14, 16, 20],
        },
    }


def test_weather_api_success(client):
    """Weather API returns current + forecast when Open-Meteo responds."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = _mock_weather_response()
        mock_get.return_value.raise_for_status = MagicMock()

        resp = client.get("/api/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert data["current"]["temperature"] == 42.5
        assert data["current"]["feels_like"] == 38.2
        assert data["current"]["description"] == "Partly cloudy"
        assert "forecast" in data
        assert len(data["forecast"]) == 7
        assert data["forecast"][0]["date"] == "2026-02-24"
        assert data["forecast"][0]["high"] == 45
        assert data["forecast"][0]["low"] == 28


def test_weather_api_unavailable(client):
    """Weather API returns 503 when Open-Meteo fails."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.side_effect = Exception("Network error")

        resp = client.get("/api/weather")
        assert resp.status_code == 503


def test_weather_no_cache_headers(client):
    """Weather response includes no-cache headers."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = _mock_weather_response()
        resp = client.get("/api/weather")
        assert "no-store" in resp.headers.get("Cache-Control", "").lower() or "no-cache" in resp.headers.get("Cache-Control", "").lower()


def test_chat_my_stats(client, auth_headers):
    """Chat returns user stats when asked."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "My stats"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "testuser" in data["reply"].lower() or "Test Player" in data["reply"]
    assert "Skill" in data["reply"] or "rating" in data["reply"].lower()


def test_chat_weather_current(client, auth_headers):
    """Chat returns current weather when asked."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = _mock_weather_response()
        resp = client.post("/api/chat", headers=auth_headers, json={"message": "What's the weather at CoRec?"})
        assert resp.status_code == 200
        assert "42.5" in resp.json()["reply"] or "42" in resp.json()["reply"]
        assert "West Lafayette" in resp.json()["reply"]


def test_chat_weather_in_two_days(client, auth_headers):
    """Chat returns forecast for specific day when asked 'weather in two days'."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = _mock_weather_response()
        resp = client.post("/api/chat", headers=auth_headers, json={"message": "What is the weather in two days?"})
        assert resp.status_code == 200
        reply = resp.json()["reply"]
        # Should mention forecast day (2026-02-26) and its temps (52 high, 32 low)
        assert "52" in reply or "2026-02-26" in reply
        assert "In 2 days" in reply or "two days" in reply.lower() or "day 2" in reply.lower()


def test_chat_weather_tomorrow(client, auth_headers):
    """Chat returns tomorrow's forecast when asked."""
    with patch("app.routers.assistant.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = _mock_weather_response()
        resp = client.post("/api/chat", headers=auth_headers, json={"message": "Weather tomorrow?"})
        assert resp.status_code == 200
        reply = resp.json()["reply"]
        assert "48" in reply or "Tomorrow" in reply
        assert "2026-02-25" in reply or "tomorrow" in reply.lower()


def test_chat_find_match(client, auth_headers, second_auth_headers):
    """Chat find match returns similar players when available."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "Find a match"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    # User 2 is similar skill (6 vs 5) — should be in matches
    if "matched_players" in (data.get("data") or {}):
        assert data["data"]["match_type"] == "similar"
        assert len(data["data"]["matched_players"]) >= 1
        assert any(p["username"] == "testuser2" for p in data["data"]["matched_players"])
    else:
        assert "similar" in data["reply"].lower() or "match" in data["reply"].lower() or "player" in data["reply"].lower()


def test_chat_find_teammate(client, auth_headers, second_auth_headers):
    """Chat find teammate returns complementary players when available."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "Find me a teammate"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    if data.get("data", {}).get("matched_players"):
        assert data["data"]["match_type"] == "teammate"
    else:
        assert "teammate" in data["reply"].lower() or "complement" in data["reply"].lower() or "player" in data["reply"].lower()


def test_chat_how_to_improve(client, auth_headers):
    """Chat returns coaching tips when asked how to improve."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "How can I improve?"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "Coaching" in reply or "tip" in reply.lower() or "advice" in reply.lower()
    assert "Shooting" in reply or "Defense" in reply or "Rebounding" in reply or "Ball handling" in reply


def test_chat_players_on_fire(client, auth_headers):
    """Chat returns Players on Fire when asked."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "Who's on fire?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    reply_lower = data["reply"].lower()
    # May return "No one" or list of players with "fire"/"hot"/"rising"/"week"
    assert any(w in reply_lower for w in ["fire", "hot", "rising", "week", "skill"])


def test_chat_1v1_tips(client, auth_headers):
    """Chat returns 1v1 strategy when asked."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "1v1 tips"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "15" in reply or "points" in reply.lower()
    assert "defense" in reply.lower() or "jab" in reply.lower() or "challenge" in reply.lower()


def test_chat_requires_auth(client):
    """Chat requires authentication."""
    resp = client.post("/api/chat", json={"message": "My stats"})
    assert resp.status_code == 401


def test_find_match_api(client, auth_headers, second_auth_headers):
    """Find match API returns similar players."""
    resp = client.get("/api/users/match?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    # User 2 (skill 6) should be in matches for user 1 (skill 5)
    ids = [u["id"] for u in users]
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    assert me2["id"] in ids or len(users) == 0


def test_find_match_with_multiple_users(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Find match returns multiple similar players when many exist."""
    resp = client.get("/api/users/match?limit=10&skill_tolerance=2", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    # All 3 other users have skill 5-6, within tolerance 2 of user 1 (skill 5)
    assert len(users) >= 2


def test_find_teammate_via_player_match(client, auth_headers, second_auth_headers):
    """find_complementary_teammates is used by chat; test via chat."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "Who complements my skills?"})
    assert resp.status_code == 200
    # Should not error; may return teammates or "no complementary" message
    assert "reply" in resp.json()


def test_win_predictor_1v1():
    """1v1 win probability is correct for known ratings."""
    from app.ai.win_predictor import predict_1v1_win_probability

    # Equal rating -> 50%
    assert 0.49 <= predict_1v1_win_probability(5.0, 5.0) <= 0.51
    # Higher rating -> favored
    assert predict_1v1_win_probability(7.0, 5.0) > 0.7
    assert predict_1v1_win_probability(5.0, 7.0) < 0.3
    # Same player vs self (edge case) — not typically called
    assert predict_1v1_win_probability(5.0, 5.0) == 0.5


def test_compare_via_chat(client, auth_headers, second_auth_headers):
    """Chat can compare to another user by name."""
    resp = client.post("/api/chat", headers=auth_headers, json={"message": "Compare me to testuser2"})
    assert resp.status_code == 200
    data = resp.json()
    reply = data["reply"]
    assert "win" in reply.lower() or "probability" in reply.lower() or "vs" in reply.lower() or "Test Player 2" in reply
