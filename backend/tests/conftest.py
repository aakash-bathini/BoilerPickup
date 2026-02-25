import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, PendingRegistration  # PendingRegistration ensures table is in metadata

# In-memory SQLite with StaticPool = single connection, avoids disk I/O and "no such table" errors
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def _verify_and_create_user(client, db, email: str):
    """Complete verification flow: get code from PendingRegistration, verify, create User."""
    pending = db.query(PendingRegistration).filter(PendingRegistration.email == email).first()
    if pending:
        client.post("/api/auth/verify-email", json={"email": email, "code": pending.verification_code})


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(client):
    """Register a user and return auth headers."""
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": "test@purdue.edu",
            "username": "testuser",
            "password": "testpass123",
            "display_name": "Test Player",
            "self_reported_skill": 5,
            "preferred_position": "PG",
        })
    db = TestingSessionLocal()
    _verify_and_create_user(client, db, "test@purdue.edu")
    db.close()
    resp = client.post("/api/auth/login", json={
        "email": "test@purdue.edu",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_auth_headers(client):
    """Register a second user and return auth headers."""
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": "test2@purdue.edu",
            "username": "testuser2",
            "password": "testpass123",
            "display_name": "Test Player 2",
            "self_reported_skill": 6,
            "preferred_position": "SG",
        })
    db = TestingSessionLocal()
    _verify_and_create_user(client, db, "test2@purdue.edu")
    db.close()
    resp = client.post("/api/auth/login", json={
        "email": "test2@purdue.edu",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, db, email: str, username: str, display_name: str):
    """Register, verify, login; return auth headers."""
    with patch("app.routers.users.send_verification_email", return_value=(True, "")):
        client.post("/api/auth/register", json={
            "email": email,
            "username": username,
            "password": "testpass123",
            "display_name": display_name,
            "self_reported_skill": 5,
        })
    _verify_and_create_user(client, db, email)
    resp = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def third_auth_headers(client):
    """Third user (for 2v2 participant or scorekeeper)."""
    db = TestingSessionLocal()
    try:
        return _make_user(client, db, "test3@purdue.edu", "testuser3", "Test Player 3")
    finally:
        db.close()


@pytest.fixture
def fourth_auth_headers(client):
    """Fourth user (for 2v2 full roster)."""
    db = TestingSessionLocal()
    try:
        return _make_user(client, db, "test4@purdue.edu", "testuser4", "Test Player 4")
    finally:
        db.close()


@pytest.fixture
def scorekeeper_headers(client):
    """User who is NOT a participant (for scorekeeper role)."""
    db = TestingSessionLocal()
    try:
        return _make_user(client, db, "scorekeeper@purdue.edu", "scorekeeper", "Score Keeper")
    finally:
        db.close()
