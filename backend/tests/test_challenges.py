def _challenge_payload(challenged_id: int, scheduled_time: str = "2026-03-01T18:00:00-05:00"):
    return {"challenged_id": challenged_id, "scheduled_time": scheduled_time}


def test_create_challenge(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me2["id"]))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["challenged_id"] == me2["id"]


def test_accept_challenge(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    create = client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me2["id"]))
    cid = create.json()["id"]

    resp = client.post(f"/api/challenges/{cid}/accept", headers=second_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_decline_challenge(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    create = client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me2["id"]))
    cid = create.json()["id"]

    resp = client.post(f"/api/challenges/{cid}/decline", headers=second_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


def test_submit_and_confirm_score(client, auth_headers, second_auth_headers):
    me1 = client.get("/api/users/me", headers=auth_headers).json()
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    create = client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me2["id"]))
    cid = create.json()["id"]

    client.post(f"/api/challenges/{cid}/accept", headers=second_auth_headers)

    client.post(f"/api/challenges/{cid}/submit-score", headers=auth_headers, json={
        "my_score": 15, "opponent_score": 10,
    })

    resp = client.post(f"/api/challenges/{cid}/submit-score", headers=second_auth_headers, json={
        "my_score": 10, "opponent_score": 15,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["winner_id"] == me1["id"]

    # Records updated: challenger (me1) won, challenged (me2) lost
    u1 = client.get("/api/users/me", headers=auth_headers).json()
    u2 = client.get("/api/users/me", headers=second_auth_headers).json()
    assert u1["challenge_wins"] == 1 and u1["challenge_losses"] == 0
    assert u2["challenge_wins"] == 0 and u2["challenge_losses"] == 1


def test_create_challenge_requires_date(client, auth_headers, second_auth_headers):
    """Challenge cannot be sent without a scheduled date/time."""
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.post("/api/challenges", headers=auth_headers, json={"challenged_id": me2["id"]})
    assert resp.status_code == 422  # Validation error (missing required field)


def test_cannot_challenge_self(client, auth_headers):
    me = client.get("/api/users/me", headers=auth_headers).json()
    resp = client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me["id"]))
    assert resp.status_code == 400


def test_list_challenges(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    client.post("/api/challenges", headers=auth_headers, json=_challenge_payload(me2["id"]))
    resp = client.get("/api/challenges", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
