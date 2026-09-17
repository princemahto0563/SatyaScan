"""
SatyaScan Checkpoint-Wise Authentication Integration Tests
SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB)

Tests:
1. Retrieval of all 8 canonical border checkpoints via GET /api/v1/auth/checkpoints
2. Successful authentication for each of the 8 canonical checkpoint identities
3. Strict checkpoint-to-user binding validation (mismatch rejection with HTTP 401)
4. Invalid password rejection (HTTP 401)
5. Non-existent checkpoint ID rejection (HTTP 401)
6. Backward compatibility for legacy test accounts (officer, supervisor)
7. Profile retrieval (/auth/me) including checkpoint identity
8. Immutable cryptographic audit logging on successful authentication (LOGIN_SUCCESS)
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, seed_initial_demo_data
from backend.app.models.database import SessionLocal, init_db, AuditEvent, Checkpoint, User
from backend.app.core.checkpoints import CANONICAL_CHECKPOINTS, DEMO_CHECKPOINT_PASSWORD
from backend.app.core.rate_limiter import limiter

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_checkpoint_test_env():
    init_db()
    seed_initial_demo_data()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()


def test_list_canonical_checkpoints():
    """Validates that GET /api/v1/auth/checkpoints returns all 8 active border checkpoints."""
    res = client.get("/api/v1/auth/checkpoints")
    assert res.status_code == 200
    checkpoints = res.json()
    assert len(checkpoints) >= 8

    # Verify each canonical checkpoint is present with correct metadata
    codes = {cp["code"]: cp for cp in checkpoints}
    for canonical in CANONICAL_CHECKPOINTS:
        assert canonical["code"] in codes
        cp_data = codes[canonical["code"]]
        assert cp_data["name"] == canonical["name"]
        assert cp_data["location"] == canonical["location"]
        assert cp_data["username"] == canonical["username"]
        assert cp_data["role"] == canonical["role"]
        assert cp_data["is_active"] is True


@pytest.mark.parametrize("checkpoint", CANONICAL_CHECKPOINTS)
def test_each_canonical_checkpoint_login_success(checkpoint):
    """Verifies that all 8 canonical checkpoint accounts authenticate successfully."""
    login_payload = {
        "checkpoint_id": checkpoint["id"],
        "username": checkpoint["username"],
        "password": DEMO_CHECKPOINT_PASSWORD
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200, f"Failed login for {checkpoint['id']}: {res.text}"
    data = res.json()

    # Verify token and user attributes
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == checkpoint["username"]
    assert data["checkpoint_id"] == checkpoint["id"]
    assert data["checkpoint_name"] == checkpoint["name"]
    assert data["role"] == "OFFICER"

    # Verify nested user object
    assert "user" in data
    assert data["user"]["username"] == checkpoint["username"]
    assert data["user"]["checkpoint_id"] == checkpoint["id"]


def test_checkpoint_user_mismatch_rejected():
    """
    Enforces strict checkpoint-user binding:
    Selecting Delhi Airport with Attari Border username must be rejected.
    """
    mismatch_payload = {
        "checkpoint_id": "CP-DEL-AIR",
        "username": "attari_border",
        "password": DEMO_CHECKPOINT_PASSWORD
    }
    res = client.post("/api/v1/auth/login", json=mismatch_payload)
    assert res.status_code == 401
    assert "Invalid checkpoint credentials." in res.json()["detail"]


def test_checkpoint_user_mismatch_cross_check():
    """
    Enforces strict checkpoint-user binding:
    Selecting Raxaul Border with Sunauli Border username must be rejected.
    """
    mismatch_payload = {
        "checkpoint_id": "CP-RAXAUL",
        "username": "sunauli_border",
        "password": DEMO_CHECKPOINT_PASSWORD
    }
    res = client.post("/api/v1/auth/login", json=mismatch_payload)
    assert res.status_code == 401
    assert "Invalid checkpoint credentials." in res.json()["detail"]


def test_checkpoint_login_invalid_password():
    """Verifies that an incorrect password for a checkpoint account is rejected with HTTP 401."""
    invalid_pwd_payload = {
        "checkpoint_id": "CP-DEL-AIR",
        "username": "delhi_airport",
        "password": "IncorrectPassword123!"
    }
    res = client.post("/api/v1/auth/login", json=invalid_pwd_payload)
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


def test_checkpoint_login_nonexistent_checkpoint_id():
    """Verifies that an unknown checkpoint ID is rejected with HTTP 401."""
    invalid_cp_payload = {
        "checkpoint_id": "CP-NON-EXISTENT",
        "username": "delhi_airport",
        "password": DEMO_CHECKPOINT_PASSWORD
    }
    res = client.post("/api/v1/auth/login", json=invalid_cp_payload)
    assert res.status_code == 401
    assert "Invalid checkpoint credentials." in res.json()["detail"]


def test_backward_compatibility_legacy_officer():
    """
    Verifies backward compatibility:
    Legacy tests logging in without checkpoint_id using officer/officer123 continue to succeed.
    """
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "officer123"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "officer"
    assert data["role"] == "OFFICER"
    assert "access_token" in data


def test_backward_compatibility_legacy_supervisor():
    """
    Verifies backward compatibility:
    Supervisor logging in without checkpoint_id succeeds.
    """
    res = client.post("/api/v1/auth/login", json={"username": "supervisor", "password": "super123"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "supervisor"
    assert data["role"] == "SUPERVISOR"
    assert "access_token" in data


def test_auth_me_returns_checkpoint_metadata():
    """Verifies that GET /api/v1/auth/me returns checkpoint details for authenticated checkpoint officer."""
    # Login as Attari border officer
    login_res = client.post(
        "/api/v1/auth/login",
        json={"checkpoint_id": "CP-ATTARI", "username": "attari_border", "password": DEMO_CHECKPOINT_PASSWORD}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Call /auth/me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "attari_border"
    assert me_data["checkpoint_id"] == "CP-ATTARI"
    assert me_data["checkpoint_name"] == "Attari Border Checkpoint"
    assert "Attari, Punjab" in me_data["location"]


def test_audit_logging_on_login_success():
    """Verifies that successful checkpoint authentication records a LOGIN_SUCCESS event in the audit chain."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"checkpoint_id": "CP-PETRAPOLE", "username": "petrapole_border", "password": DEMO_CHECKPOINT_PASSWORD}
    )
    assert login_res.status_code == 200

    db = SessionLocal()
    try:
        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.event_type == "LOGIN_SUCCESS")
            .filter(AuditEvent.actor == "OFFICER:petrapole_border")
            .order_by(AuditEvent.id.desc())
            .first()
        )
        assert event is not None
        assert event.event_type == "LOGIN_SUCCESS"
        assert len(event.event_hash) == 64
        assert len(event.payload_hash) == 64
    finally:
        db.close()
