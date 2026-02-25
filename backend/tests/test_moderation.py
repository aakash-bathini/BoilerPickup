def test_report_user(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.post("/api/report", headers=auth_headers, json={
        "reported_id": me2["id"],
        "reason": "harassment",
        "details": "Inappropriate language in game chat",
    })
    assert resp.status_code == 201
    assert resp.json()["reason"] == "harassment"


def test_cannot_report_self(client, auth_headers):
    me = client.get("/api/users/me", headers=auth_headers).json()
    resp = client.post("/api/report", headers=auth_headers, json={
        "reported_id": me["id"],
        "reason": "test",
    })
    assert resp.status_code == 400


def test_cannot_double_report(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    client.post("/api/report", headers=auth_headers, json={
        "reported_id": me2["id"],
        "reason": "cheating",
    })
    resp = client.post("/api/report", headers=auth_headers, json={
        "reported_id": me2["id"],
        "reason": "cheating again",
    })
    assert resp.status_code == 400


def test_block_user(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    resp = client.post(f"/api/block/{me2['id']}", headers=auth_headers)
    assert resp.status_code == 201


def test_cannot_block_self(client, auth_headers):
    me = client.get("/api/users/me", headers=auth_headers).json()
    resp = client.post(f"/api/block/{me['id']}", headers=auth_headers)
    assert resp.status_code == 400


def test_unblock_user(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    client.post(f"/api/block/{me2['id']}", headers=auth_headers)
    resp = client.delete(f"/api/block/{me2['id']}", headers=auth_headers)
    assert resp.status_code == 204


def test_blocked_user_hidden_in_search(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    client.post(f"/api/block/{me2['id']}", headers=auth_headers)

    resp = client.get(f"/api/users/search?q={me2['display_name']}", headers=auth_headers)
    assert resp.status_code == 200
    ids = [u["id"] for u in resp.json()]
    assert me2["id"] not in ids


def test_blocked_user_cannot_dm(client, auth_headers, second_auth_headers):
    me2 = client.get("/api/users/me", headers=second_auth_headers).json()
    client.post(f"/api/block/{me2['id']}", headers=auth_headers)

    resp = client.post("/api/messages", headers=auth_headers, json={
        "recipient_id": me2["id"],
        "content": "hello",
    })
    assert resp.status_code == 403
