from datetime import datetime, timedelta, timezone


def _future_time():
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def test_create_game(client, auth_headers):
    resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 3.0,
        "skill_max": 8.0,
        "court_type": "fullcourt",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["game_type"] == "5v5"
    assert data["max_players"] == 10
    assert data["status"] == "open"
    assert len(data["participants"]) == 1


def test_create_game_3v3(client, auth_headers):
    resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "3v3",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
        "court_type": "halfcourt",
    })
    assert resp.status_code == 201
    assert resp.json()["max_players"] == 6


def test_list_games(client, auth_headers):
    client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    resp = client.get("/api/games", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_join_game(client, auth_headers, second_auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    join_resp = client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)
    assert join_resp.status_code == 200
    assert len(join_resp.json()["participants"]) == 2


def test_join_game_skill_check(client, auth_headers, db):
    from unittest.mock import patch
    from app.models import PendingRegistration

    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 8.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": "lowskill@purdue.edu",
            "username": "lowskill",
            "password": "testpass123",
            "display_name": "Low Skill",
            "self_reported_skill": 2,
        })
    pending = db.query(PendingRegistration).filter(PendingRegistration.email == "lowskill@purdue.edu").first()
    assert pending, "PendingRegistration should exist"
    client.post("/api/auth/verify-email", json={"email": "lowskill@purdue.edu", "code": pending.verification_code})

    login_resp = client.post("/api/auth/login", json={
        "email": "lowskill@purdue.edu",
        "password": "testpass123",
    })
    assert "access_token" in login_resp.json(), f"Login failed: {login_resp.json()}"
    low_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    join_resp = client.post(f"/api/games/{game_id}/join", headers=low_headers)
    assert join_resp.status_code == 403


def test_leave_game(client, auth_headers, second_auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    leave_resp = client.post(f"/api/games/{game_id}/leave", headers=second_auth_headers)
    assert leave_resp.status_code == 200
    assert len(leave_resp.json()["participants"]) == 1


def test_creator_cannot_leave(client, auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    leave_resp = client.post(f"/api/games/{game_id}/leave", headers=auth_headers)
    assert leave_resp.status_code == 400


def test_get_game_detail(client, auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "3v3",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
        "court_type": "halfcourt",
        "notes": "Let's ball!",
    })
    game_id = create_resp.json()["id"]

    resp = client.get(f"/api/games/{game_id}")
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Let's ball!"


def test_double_join_prevented(client, auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    resp = client.post(f"/api/games/{game_id}/join", headers=auth_headers)
    assert resp.status_code == 400


# ── Scorekeeper ──────────────────────────────────────────────────────────────

def test_invite_scorekeeper(client, auth_headers, second_auth_headers, scorekeeper_headers):
    """Creator can invite a non-participant as scorekeeper."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    creator_id = create_resp.json()["creator_id"]

    # Get scorekeeper user id (user 3 = scorekeeper)
    me_resp = client.get("/api/users/me", headers=scorekeeper_headers)
    sk_user_id = me_resp.json()["id"]

    resp = client.post(
        f"/api/games/{game_id}/invite-scorekeeper",
        headers=auth_headers,
        json={"user_id": sk_user_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scorekeeper_id"] == sk_user_id
    assert data["scorekeeper_status"] == "pending"


def test_invite_scorekeeper_cannot_be_participant(client, auth_headers, second_auth_headers):
    """Scorekeeper cannot be a game participant."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    participant_id = client.get("/api/users/me", headers=second_auth_headers).json()["id"]

    resp = client.post(
        f"/api/games/{game_id}/invite-scorekeeper",
        headers=auth_headers,
        json={"user_id": participant_id},
    )
    assert resp.status_code == 400
    assert "participant" in resp.json()["detail"].lower()


def test_accept_scorekeeper(client, auth_headers, second_auth_headers, scorekeeper_headers):
    """Invited user can accept scorekeeper role."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    sk_user_id = client.get("/api/users/me", headers=scorekeeper_headers).json()["id"]
    client.post(f"/api/games/{game_id}/invite-scorekeeper", headers=auth_headers, json={"user_id": sk_user_id})

    resp = client.post(f"/api/games/{game_id}/accept-scorekeeper", headers=scorekeeper_headers)
    assert resp.status_code == 200
    assert resp.json()["scorekeeper_status"] == "accepted"


def test_accept_scorekeeper_wrong_user(client, auth_headers, scorekeeper_headers):
    """Only invited user can accept."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    sk_user_id = client.get("/api/users/me", headers=scorekeeper_headers).json()["id"]
    client.post(f"/api/games/{game_id}/invite-scorekeeper", headers=auth_headers, json={"user_id": sk_user_id})

    # second user (not scorekeeper) tries to accept
    resp = client.post(f"/api/games/{game_id}/accept-scorekeeper", headers=auth_headers)
    assert resp.status_code == 403


def test_my_scorekeeping_games(client, auth_headers, scorekeeper_headers):
    """Scorekeeper sees games they're scorekeeping."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    sk_user_id = client.get("/api/users/me", headers=scorekeeper_headers).json()["id"]
    client.post(f"/api/games/{game_id}/invite-scorekeeper", headers=auth_headers, json={"user_id": sk_user_id})
    client.post(f"/api/games/{game_id}/accept-scorekeeper", headers=scorekeeper_headers)

    resp = client.get("/api/games/scorekeeping/mine", headers=scorekeeper_headers)
    assert resp.status_code == 200
    games = resp.json()
    assert len(games) >= 1
    assert any(g["id"] == game_id for g in games)


# ── Start, Complete, Stats ───────────────────────────────────────────────────

def test_start_game(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Creator can start when roster is full (2v2 = 4 players)."""
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

    resp = client.post(f"/api/games/{game_id}/start", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    teams = [p["team"] for p in resp.json()["participants"]]
    assert set(teams) == {"A", "B"}


def test_complete_game_as_creator(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Creator can complete game with final score."""
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

    resp = client.post(
        f"/api/games/{game_id}/complete",
        headers=auth_headers,
        json={"team_a_score": 15, "team_b_score": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["team_a_score"] == 15
    assert resp.json()["team_b_score"] == 10

    # Team records updated: Team A (2 players) each +1 win, Team B (2 players) each +1 loss
    participants = resp.json()["participants"]
    team_a_ids = [p["user_id"] for p in participants if p["team"] == "A"]
    team_b_ids = [p["user_id"] for p in participants if p["team"] == "B"]
    me = client.get("/api/users/me", headers=auth_headers).json()
    assert me["id"] in team_a_ids or me["id"] in team_b_ids
    # At least one user has games_played=1 (all 4 should)
    all_users = [client.get("/api/users/me", headers=auth_headers).json()]
    all_users.append(client.get("/api/users/me", headers=second_auth_headers).json())
    all_users.append(client.get("/api/users/me", headers=third_auth_headers).json())
    all_users.append(client.get("/api/users/me", headers=fourth_auth_headers).json())
    total_wins = sum(u["wins"] for u in all_users)
    total_losses = sum(u["losses"] for u in all_users)
    total_gp = sum(u["games_played"] for u in all_users)
    assert total_gp == 4
    assert total_wins == 2 and total_losses == 2


def test_complete_game_as_scorekeeper(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers, scorekeeper_headers
):
    """Scorekeeper can also complete the game."""
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

    sk_user_id = client.get("/api/users/me", headers=scorekeeper_headers).json()["id"]
    client.post(f"/api/games/{game_id}/invite-scorekeeper", headers=auth_headers, json={"user_id": sk_user_id})
    client.post(f"/api/games/{game_id}/accept-scorekeeper", headers=scorekeeper_headers)

    resp = client.post(
        f"/api/games/{game_id}/complete",
        headers=scorekeeper_headers,
        json={"team_a_score": 12, "team_b_score": 15},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_complete_game_forbidden_for_participant(
    client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers
):
    """Only creator or scorekeeper can complete; participant cannot."""
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

    resp = client.post(
        f"/api/games/{game_id}/complete",
        headers=second_auth_headers,
        json={"team_a_score": 15, "team_b_score": 10},
    )
    assert resp.status_code == 403


def test_kick_player(client, auth_headers, second_auth_headers):
    """Creator can kick a participant."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    participant_id = client.get("/api/users/me", headers=second_auth_headers).json()["id"]

    resp = client.post(f"/api/games/{game_id}/kick/{participant_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["participants"]) == 1


# ── Stats Contest ───────────────────────────────────────────────────────────

def test_create_contest(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Participant can create contest on completed game."""
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
    client.post(
        f"/api/games/{game_id}/complete",
        headers=auth_headers,
        json={"team_a_score": 15, "team_b_score": 10},
    )

    resp = client.post(
        f"/api/games/{game_id}/contest",
        headers=second_auth_headers,
        json={"reason": "My stats are wrong, should be 12 pts not 8."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert "My stats are wrong" in data["reason"]


def test_vote_on_contest(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Participants can vote on contest."""
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
    client.post(
        f"/api/games/{game_id}/complete",
        headers=auth_headers,
        json={"team_a_score": 15, "team_b_score": 10},
    )

    contest_resp = client.post(
        f"/api/games/{game_id}/contest",
        headers=second_auth_headers,
        json={"reason": "Stats need review."},
    )
    contest_id = contest_resp.json()["id"]

    resp = client.post(
        f"/api/games/{game_id}/contest/{contest_id}/vote",
        headers=third_auth_headers,
        json={"support": True},
    )
    assert resp.status_code == 200
    assert resp.json()["votes_for"] >= 1


def test_delete_game_creator_no_strike_when_alone(client, auth_headers, db):
    """Creator can delete game when alone; no strike."""
    from app.models import User
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    creator_id = create_resp.json()["creator_id"]
    creator_before = db.query(User).filter(User.id == creator_id).first()
    report_before = creator_before.report_count or 0

    resp = client.delete(f"/api/games/{game_id}", headers=auth_headers)
    assert resp.status_code == 204

    creator_after = db.query(User).filter(User.id == creator_id).first()
    assert (creator_after.report_count or 0) == report_before


def test_delete_game_creator(client, auth_headers, second_auth_headers):
    """Creator can delete game when others joined; participants no longer see it. Creator gets strike."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    resp = client.delete(f"/api/games/{game_id}", headers=auth_headers)
    assert resp.status_code == 204

    get_resp = client.get(f"/api/games/{game_id}")
    assert get_resp.status_code == 404

    games = client.get("/api/games", headers=second_auth_headers).json()
    assert not any(g["id"] == game_id for g in games)


def test_delete_game_forbidden_non_creator(client, auth_headers, second_auth_headers):
    """Only creator can delete."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    resp = client.delete(f"/api/games/{game_id}", headers=second_auth_headers)
    assert resp.status_code == 403


def test_delete_game_forbidden_started(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Cannot delete started game."""
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

    resp = client.delete(f"/api/games/{game_id}", headers=auth_headers)
    assert resp.status_code == 400


def test_update_game_when_alone(client, auth_headers):
    """Creator can edit game when no one else has joined."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    new_time = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT14:00:00-05:00")
    resp = client.patch(f"/api/games/{game_id}", headers=auth_headers, json={"scheduled_time": new_time})
    assert resp.status_code == 200
    assert "14" in resp.json()["scheduled_time"] or "15" in resp.json()["scheduled_time"]


def test_update_game_forbidden_when_others_joined(client, auth_headers, second_auth_headers):
    """Creator cannot edit when others have joined; must use propose reschedule."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)
    new_time = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT14:00:00-05:00")
    resp = client.patch(f"/api/games/{game_id}", headers=auth_headers, json={"scheduled_time": new_time})
    assert resp.status_code == 400
    assert "reschedule" in resp.json().get("detail", "").lower()


def test_propose_reschedule_forbidden_when_alone(client, auth_headers):
    """Creator cannot propose reschedule when no one else has joined; should edit instead."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    new_time = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT18:00:00-05:00")
    resp = client.post(f"/api/games/{game_id}/reschedule", headers=auth_headers, json={"scheduled_time": new_time})
    assert resp.status_code == 400
    assert "edit" in resp.json().get("detail", "").lower() or "alone" in resp.json().get("detail", "").lower()


def test_propose_reschedule(client, auth_headers, second_auth_headers):
    """Creator can propose reschedule when others have joined."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    new_time = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT18:00:00-05:00")
    resp = client.post(
        f"/api/games/{game_id}/reschedule",
        headers=auth_headers,
        json={"scheduled_time": new_time},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert resp.json()["total_participants"] == 2


def test_vote_reschedule_approve(client, auth_headers, second_auth_headers):
    """Participants can vote; all approve -> game rescheduled."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    new_time = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT19:00:00-05:00")
    prop = client.post(f"/api/games/{game_id}/reschedule", headers=auth_headers, json={"scheduled_time": new_time}).json()
    reschedule_id = prop["id"]

    client.post(f"/api/games/{game_id}/reschedule/{reschedule_id}/vote", headers=auth_headers, json={"approved": True})
    resp = client.post(f"/api/games/{game_id}/reschedule/{reschedule_id}/vote", headers=second_auth_headers, json={"approved": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    game = client.get(f"/api/games/{game_id}").json()
    assert "19:00" in game["scheduled_time"] or "19" in game["scheduled_time"]


def test_vote_reschedule_reject(client, auth_headers, second_auth_headers):
    """One reject -> reschedule rejected."""
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "2v2",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]
    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    new_time = (datetime.now(timezone.utc) + timedelta(days=4)).strftime("%Y-%m-%dT20:00:00-05:00")
    prop = client.post(f"/api/games/{game_id}/reschedule", headers=auth_headers, json={"scheduled_time": new_time}).json()

    resp = client.post(
        f"/api/games/{game_id}/reschedule/{prop['id']}/vote",
        headers=second_auth_headers,
        json={"approved": False},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_list_contests(client, auth_headers, second_auth_headers, third_auth_headers, fourth_auth_headers):
    """Anyone can list contests for a game."""
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
    client.post(
        f"/api/games/{game_id}/complete",
        headers=auth_headers,
        json={"team_a_score": 15, "team_b_score": 10},
    )
    client.post(
        f"/api/games/{game_id}/contest",
        headers=second_auth_headers,
        json={"reason": "Stats dispute."},
    )

    resp = client.get(f"/api/games/{game_id}/contests")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
