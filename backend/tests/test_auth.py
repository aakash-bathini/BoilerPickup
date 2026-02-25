def test_register_success(client):
    from unittest.mock import patch
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        resp = client.post("/api/auth/register", json={
            "email": "player1@purdue.edu",
            "username": "player1",
            "password": "secure123",
            "display_name": "Player One",
            "self_reported_skill": 7,
            "preferred_position": "SF",
            "height": "6'2\"",
            "weight": 185,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Verification code sent to your email"


def test_register_non_allowed_email(client):
    """Only @purdue.edu and @purdoo.com allowed."""
    resp = client.post("/api/auth/register", json={
        "email": "player1@gmail.com",
        "username": "player1",
        "password": "secure123",
        "display_name": "Player One",
        "self_reported_skill": 7,
    })
    assert resp.status_code == 422


def test_register_purdoo_com_skips_verification(client):
    """@purdoo.com creates account immediately, no email verification."""
    resp = client.post("/api/auth/register", json={
        "email": "test@purdoo.com",
        "username": "purdoouser",
        "password": "testpass123",
        "display_name": "Purdoo Test",
        "self_reported_skill": 5,
    })
    assert resp.status_code == 200
    assert "purdoo" in resp.json()["message"].lower() or "created" in resp.json()["message"].lower()
    resp2 = client.post("/api/auth/login", json={"email": "test@purdoo.com", "password": "testpass123"})
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()


def test_register_duplicate_email(client):
    from unittest.mock import patch
    payload = {
        "email": "dup@purdue.edu",
        "username": "user1",
        "password": "secure123",
        "display_name": "User One",
        "self_reported_skill": 5,
    }
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json=payload)
        payload["username"] = "user2"
        resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_duplicate_username(client):
    from unittest.mock import patch
    payload = {
        "email": "a@purdue.edu",
        "username": "sameuser",
        "password": "secure123",
        "display_name": "User A",
        "self_reported_skill": 5,
    }
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json=payload)
        payload["email"] = "b@purdue.edu"
        resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_invalid_skill(client):
    resp = client.post("/api/auth/register", json={
        "email": "x@purdue.edu",
        "username": "x",
        "password": "secure123",
        "display_name": "X",
        "self_reported_skill": 11,
    })
    assert resp.status_code == 422


def test_login_success(client, db):
    from unittest.mock import patch
    from tests.conftest import _verify_and_create_user
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": "login@purdue.edu",
            "username": "loginuser",
            "password": "mypassword",
            "display_name": "Login User",
            "self_reported_skill": 5,
        })
    _verify_and_create_user(client, db, "login@purdue.edu")
    resp = client.post("/api/auth/login", json={
        "email": "login@purdue.edu",
        "password": "mypassword",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client, db):
    from unittest.mock import patch
    from tests.conftest import _verify_and_create_user
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": "login2@purdue.edu",
            "username": "loginuser2",
            "password": "mypassword",
            "display_name": "Login User 2",
            "self_reported_skill": 5,
        })
    _verify_and_create_user(client, db, "login2@purdue.edu")
    resp = client.post("/api/auth/login", json={
        "email": "login2@purdue.edu",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_get_me(client, auth_headers):
    resp = client.get("/api/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


def test_get_me_no_auth(client):
    resp = client.get("/api/users/me")
    assert resp.status_code == 401


def test_update_profile(client, auth_headers):
    resp = client.put("/api/users/me", headers=auth_headers, json={
        "bio": "Ball is life",
        "display_name": "Updated Name",
    })
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Ball is life"
    assert resp.json()["display_name"] == "Updated Name"
