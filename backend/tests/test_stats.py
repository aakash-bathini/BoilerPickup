"""Tests for stats API: submit, get, career, history. Scorekeeper can submit."""
from datetime import datetime, timedelta, timezone


def _future_time():
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def _create_full_game(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Create 2v2 game, fill roster, start. Returns game_id and participant user_ids."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)
    client.post(f"/api/games/{game_id}/join", headers=third_auth_headers)
    client.post(f"/api/games/{game_id}/join", headers=fourth_auth_headers)
    client.post(f"/api/games/{game_id}/start", headers=auth_headers)

    participants = client.get(f"/api/games/{game_id}").json()["participants"]
    user_ids = [p["user_id"] for p in participants if p.get("user_id")]

    return game_id, user_ids


def test_submit_stats_as_creator(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
):
    """Creator can submit stats for in-progress game."""
    game_id, user_ids = _create_full_game(
        client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
    )

    stats = [
        {"user_id": user_ids[0], "pts": 8, "reb": 3, "ast": 2, "stl": 1, "blk": 0, "tov": 1,
         "fgm": 4, "fga": 8, "three_pm": 0, "three_pa": 2, "ftm": 0, "fta": 0},
        {"user_id": user_ids[1], "pts": 6, "reb": 5, "ast": 1, "stl": 0, "blk": 1, "tov": 2,
         "fgm": 3, "fga": 7, "three_pm": 0, "three_pa": 1, "ftm": 0, "fta": 0},
        {"user_id": user_ids[2], "pts": 10, "reb": 2, "ast": 4, "stl": 2, "blk": 0, "tov": 1,
         "fgm": 5, "fga": 9, "three_pm": 0, "three_pa": 0, "ftm": 0, "fta": 0},
        {"user_id": user_ids[3], "pts": 4, "reb": 4, "ast": 3, "stl": 1, "blk": 0, "tov": 2,
         "fgm": 2, "fga": 5, "three_pm": 0, "three_pa": 1, "ftm": 0, "fta": 0},
    ]

    resp = client.post(
        f"/api/games/{game_id}/stats",
        headers=auth_headers,
        json={"stats": stats},
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 4


def test_submit_stats_as_scorekeeper(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers, scorekeeper_headers
):
    """Scorekeeper can submit stats (not just creator/participant)."""
    game_id, user_ids = _create_full_game(
        client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
    )

    sk_user_id = client.get("/api/users/me", headers=scorekeeper_headers).json()["id"]
    client.post(f"/api/games/{game_id}/invite-scorekeeper", headers=auth_headers, json={"user_id": sk_user_id})
    client.post(f"/api/games/{game_id}/accept-scorekeeper", headers=scorekeeper_headers)

    stats = [
        {"user_id": uid, "pts": 5, "reb": 2, "ast": 1, "stl": 0, "blk": 0, "tov": 1,
         "fgm": 2, "fga": 5, "three_pm": 0, "three_pa": 1, "ftm": 1, "fta": 1}
        for uid in user_ids
    ]

    resp = client.post(
        f"/api/games/{game_id}/stats",
        headers=scorekeeper_headers,
        json={"stats": stats},
    )
    assert resp.status_code == 201


def test_submit_stats_forbidden_for_random_user(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers, scorekeeper_headers
):
    """User who is not participant/creator/scorekeeper cannot submit stats."""
    game_id, user_ids = _create_full_game(
        client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
    )
    # Do NOT invite scorekeeper - so scorekeeper_headers user has no role

    stats = [{"user_id": uid, "pts": 5, "reb": 2, "ast": 1, "stl": 0, "blk": 0, "tov": 1,
              "fgm": 2, "fga": 5, "three_pm": 0, "three_pa": 1, "ftm": 1, "fta": 1}
             for uid in user_ids]

    resp = client.post(
        f"/api/games/{game_id}/stats",
        headers=scorekeeper_headers,
        json={"stats": stats},
    )
    assert resp.status_code == 403


def test_get_game_stats(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
):
    """Anyone can get game stats (public)."""
    game_id, user_ids = _create_full_game(
        client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
    )

    stats = [{"user_id": uid, "pts": 5, "reb": 2, "ast": 1, "stl": 0, "blk": 0, "tov": 1,
              "fgm": 2, "fga": 5, "three_pm": 0, "three_pa": 1, "ftm": 1, "fta": 1}
             for uid in user_ids]
    client.post(f"/api/games/{game_id}/stats", headers=auth_headers, json={"stats": stats})

    resp = client.get(f"/api/games/{game_id}/stats")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_get_career_stats(client, auth_headers):
    """Career stats returns for user."""
    me = client.get("/api/users/me", headers=auth_headers).json()
    resp = client.get(f"/api/users/{me['id']}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "ppg" in data
    assert "rpg" in data
    assert "games_played" in data


def test_get_stats_history(client, auth_headers):
    """Stats history returns list."""
    me = client.get("/api/users/me", headers=auth_headers).json()
    resp = client.get(f"/api/users/{me['id']}/stats/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
