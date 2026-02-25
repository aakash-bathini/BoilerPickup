from datetime import datetime, timedelta, timezone


def _future_time():
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def test_send_dm(client, auth_headers, second_auth_headers):
    me_resp = client.get("/api/users/me", headers=second_auth_headers)
    recipient_id = me_resp.json()["id"]

    resp = client.post("/api/messages", headers=auth_headers, json={
        "recipient_id": recipient_id,
        "content": "Want to run some 5s?",
    })
    assert resp.status_code == 201
    assert resp.json()["content"] == "Want to run some 5s?"


def test_get_dm_thread(client, auth_headers, second_auth_headers):
    me_resp = client.get("/api/users/me", headers=second_auth_headers)
    recipient_id = me_resp.json()["id"]

    client.post("/api/messages", headers=auth_headers, json={
        "recipient_id": recipient_id,
        "content": "Hey!",
    })

    resp = client.get(f"/api/messages/dm/{recipient_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_game_chat(client, auth_headers, second_auth_headers):
    create_resp = client.post("/api/games", headers=auth_headers, json={
        "game_type": "5v5",
        "scheduled_time": _future_time(),
        "skill_min": 1.0,
        "skill_max": 10.0,
    })
    game_id = create_resp.json()["id"]

    client.post(f"/api/games/{game_id}/join", headers=second_auth_headers)

    resp = client.post("/api/messages", headers=auth_headers, json={
        "game_id": game_id,
        "content": "I'll be there at 5pm",
    })
    assert resp.status_code == 201

    chat_resp = client.get(f"/api/messages/game/{game_id}", headers=auth_headers)
    assert chat_resp.status_code == 200
    assert len(chat_resp.json()) == 1


def test_must_specify_target(client, auth_headers):
    resp = client.post("/api/messages", headers=auth_headers, json={
        "content": "Hello",
    })
    assert resp.status_code == 400


def test_conversations_list(client, auth_headers, second_auth_headers):
    me_resp = client.get("/api/users/me", headers=second_auth_headers)
    recipient_id = me_resp.json()["id"]

    client.post("/api/messages", headers=auth_headers, json={
        "recipient_id": recipient_id,
        "content": "Hey there",
    })

    resp = client.get("/api/messages/conversations", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
