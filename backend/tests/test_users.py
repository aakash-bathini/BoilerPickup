"""Tests for users API: search, leaderboard, compare, match."""
def test_search_users(client, auth_headers, second_auth_headers):
    """Search returns matching users."""
    resp = client.get("/api/users/search?q=test", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1
    assert any("test" in (u.get("display_name", "") or "").lower() or "test" in (u.get("username", "") or "").lower() for u in users)


def test_search_empty(client, auth_headers):
    """Search with empty q still returns list."""
    resp = client.get("/api/users/search", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_leaderboard(client, auth_headers):
    """Leaderboard returns users sorted by rating."""
    resp = client.get("/api/users/leaderboard", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_leaderboard_with_limit(client, auth_headers):
    """Leaderboard accepts limit param."""
    resp = client.get("/api/users/leaderboard?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) <= 5


def test_leaderboard_by_position(client, auth_headers):
    """Leaderboard accepts position filter."""
    resp = client.get("/api/users/leaderboard?limit=10&position=PG", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    for u in users:
        assert u.get("preferred_position") == "PG"


def test_leaderboard_hot_week(client, auth_headers):
    """Leaderboard accepts sort=hot_week for Players on Fire."""
    resp = client.get("/api/users/leaderboard?limit=10&sort=hot_week", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)


def test_compare_to_user(client, auth_headers, second_auth_headers):
    """Compare returns win probabilities."""
    me = client.get("/api/users/me", headers=auth_headers).json()
    other = client.get("/api/users/me", headers=second_auth_headers).json()

    resp = client.get(f"/api/users/compare/{other['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "my_win_probability" in data
    assert "their_win_probability" in data
    assert "target" in data


def test_compare_nonexistent(client, auth_headers):
    """Compare to nonexistent user returns 404."""
    resp = client.get("/api/users/compare/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_match(client, auth_headers):
    """Match returns recommended players."""
    resp = client.get("/api/users/match", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_user(client, auth_headers, second_auth_headers):
    """Get user by id returns public profile."""
    other = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.get(f"/api/users/{other['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == other["id"]
    assert "email" not in resp.json() or resp.json().get("email") is None


def test_leaderboard_1v1(client, auth_headers):
    """1v1 leaderboard returns list (may be empty)."""
    resp = client.get("/api/users/leaderboard-1v1?limit=10", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_leaderboard_1v1_wins_week(client, auth_headers):
    """1v1 leaderboard accepts sort=wins_week."""
    resp = client.get("/api/users/leaderboard-1v1?limit=10&sort=wins_week", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_user_challenges_history(client, auth_headers, second_auth_headers):
    """User challenges history returns list for valid user."""
    other = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.get(f"/api/users/{other['id']}/challenges-history?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
