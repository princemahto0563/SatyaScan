"""
SatyaScan Enterprise Cybersecurity Hardening Test Suite
SIH26188 · Theme: Blockchain & Cybersecurity

Validates the 15 Required Threat Vectors (T-01 to T-15):
- T-01: Authentication Bypass (Strict Auth & Token Validation)
- T-02: JWT Tampering & Algorithm Confusion (HS256 only, reject none/RS256, expired)
- T-03: Privilege Escalation (Centralized RBAC: Officer vs Supervisor vs Admin)
- T-04: Insecure Direct Object Reference (IDOR) & Checkpoint Isolation Policy
- T-05: Malicious File Upload & Polyglot Defense (Magic bytes, decode check, dimension limits)
- T-06: Directory & Path Traversal Safeguards
- T-07: Denial of Service & In-Memory Rate Limiting
- T-08: SQL Injection / Input Validation Defenses
- T-09: XSS / Template Injection / PDF ReportLab Escaping
- T-10: Password Cracking & Credential Protection (bcrypt work factor 12, zero leaks)
- T-11: Cross-Origin Resource Sharing (CORS) Non-Wildcard Integrity
- T-12: Sensitive Data Exposure & PII Masking (Zero PII on-chain)
- T-13: Cryptographic Audit Trail Tampering & Security Auditing (LOGIN_FAILURE, ACCESS_DENIED)
- T-14: Blockchain Anchor Forgery & Local Discrepancy Detection
- T-15: Information Disclosure & Traceback Suppression
"""

import pytest
import os
import io
import time
import base64
import json
from datetime import datetime, timedelta, timezone
import jwt
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app, seed_initial_demo_data
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token, decode_access_token, get_password_hash, verify_password,
    mask_document_number, mask_full_name, mask_date_of_birth,
    sanitize_filename, validate_uploaded_image_bytes
)
from backend.app.core.permissions import (
    has_permission, check_checkpoint_access,
    PERM_SCREENING_VIEW, PERM_WATCHLIST_MANAGE, PERM_CASE_REVIEW
)
from backend.app.core.rate_limiter import limiter
from backend.app.models.database import (
    SessionLocal, init_db, Screening, AuditEvent, User, Checkpoint,
    ReferenceWatchlist, BlockchainAnchor
)
from backend.app.services.audit_service import AuditService
from backend.app.services.report_generator import ReportGenerator
from backend.app.services.fabric_service import FabricAnchorService

client = TestClient(app)


# --- Test Fixtures ---

@pytest.fixture(scope="module", autouse=True)
def setup_cybersecurity_suite():
    """Initializes clean database schema, demo data, and resets rate limiter."""
    init_db()
    seed_initial_demo_data()
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def per_test_rate_limiter_reset():
    limiter.reset()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def delhi_officer_token():
    res = client.post("/api/v1/auth/login", json={"username": "delhi_airport", "password": "Demo@123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def raxaul_officer_token():
    res = client.post("/api/v1/auth/login", json={"username": "raxaul_border", "password": "Demo@123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def supervisor_token():
    res = client.post("/api/v1/auth/login", json={"username": "supervisor", "password": "super123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def checkpoint_screenings(db_session):
    """Creates two isolated test screenings for Delhi and Raxaul checkpoints."""
    delhi_sc = db_session.query(Screening).filter(Screening.id == "SCREEN-DELHI-SEC-01").first()
    if not delhi_sc:
        delhi_sc = Screening(
            id="SCREEN-DELHI-SEC-01",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint",
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="CLEARED",
            risk_score=10.0,
            risk_band="LOW",
            recommendation="CLEAR",
            operator_id=1
        )
        db_session.add(delhi_sc)

    raxaul_sc = db_session.query(Screening).filter(Screening.id == "SCREEN-RAXAUL-SEC-01").first()
    if not raxaul_sc:
        raxaul_sc = Screening(
            id="SCREEN-RAXAUL-SEC-01",
            checkpoint_id="CP-RAXAUL",
            checkpoint_name="Raxaul Land Customs Station (SSB Border Outpost)",
            document_type="PASSPORT",
            masked_document_id="P88****99",
            status="MANUAL_REVIEW_REQUIRED",
            risk_score=65.0,
            risk_band="MEDIUM",
            recommendation="INVESTIGATE",
            operator_id=1
        )
        db_session.add(raxaul_sc)

    db_session.commit()
    return {"delhi_id": "SCREEN-DELHI-SEC-01", "raxaul_id": "SCREEN-RAXAUL-SEC-01"}


# ==============================================================================
# T-01: Authentication Bypass Defenses
# ==============================================================================

def test_t01_strict_auth_rejects_missing_token():
    """Validates that in strict mode, requests without Authorization header return 401."""
    original_strict = settings.STRICT_AUTH
    try:
        settings.STRICT_AUTH = True
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401
        assert "not provided" in res.json()["detail"].lower()
    finally:
        settings.STRICT_AUTH = original_strict


def test_t01_malformed_bearer_token_rejected():
    """Validates that malformed or garbage Bearer tokens return HTTP 401."""
    for bad_token in ["Bearer abc", "Bearer foo.bar", "Bearer not-a-jwt", "Bearer 123.456"]:
        res = client.get("/api/v1/auth/me", headers={"Authorization": bad_token})
        assert res.status_code == 401
        assert "invalid or expired" in res.json()["detail"].lower()


# ==============================================================================
# T-02: JWT Tampering & Algorithm Confusion
# ==============================================================================

def test_t02_jwt_alg_none_rejected():
    """Validates that tokens with alg='none' are strictly rejected by header inspection."""
    header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b'=').decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps({
        "sub": "officer", "role": "OFFICER", "exp": int(time.time()) + 3600
    }).encode()).rstrip(b'=').decode()
    tampered_token = f"{header_b64}.{payload_b64}."
    
    assert decode_access_token(tampered_token) is None
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401


def test_t02_jwt_algorithm_confusion_rejected():
    """Validates that tokens encoded with unexpected algorithms (e.g. HS512, RS256) are rejected."""
    payload = {
        "sub": "officer",
        "role": "OFFICER",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    hs512_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS512")
    assert decode_access_token(hs512_token) is None

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {hs512_token}"})
    assert res.status_code == 401


def test_t02_jwt_signature_tampering_rejected():
    """Validates that modifying the signature portion of a valid JWT causes immediate rejection."""
    valid_token = create_access_token({"sub": "officer", "role": "OFFICER"})
    tampered_token = valid_token[:-1] + ("A" if valid_token[-1] != "A" else "B")
    
    assert decode_access_token(tampered_token) is None
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401


def test_t02_jwt_expired_token_rejected():
    """Validates that expired tokens fail verification and return HTTP 401."""
    expired_token = create_access_token(
        {"sub": "officer", "role": "OFFICER"},
        expires_delta=timedelta(seconds=-3600)
    )
    assert decode_access_token(expired_token) is None
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


def test_t02_jwt_missing_required_sub_claim_rejected():
    """Validates that tokens missing required 'sub' claim are rejected."""
    token_missing_sub = jwt.encode(
        {"role": "OFFICER", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.JWT_SECRET,
        algorithm=settings.ALGORITHM
    )
    assert decode_access_token(token_missing_sub) is None


# ==============================================================================
# T-03: Privilege Escalation & Centralized RBAC
# ==============================================================================

def test_t03_rbac_officer_cannot_add_watchlist(delhi_officer_token):
    """Validates that an OFFICER cannot modify reference watchlists (HTTP 403)."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    payload = {
        "document_id": "STOLEN-TEST-001",
        "full_name": "ESCALATION ATTEMPT",
        "reason": "Test RBAC boundary"
    }
    res = client.post("/api/v1/watchlist", headers=headers, json=payload)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


def test_t03_rbac_supervisor_can_add_watchlist(supervisor_token, db_session):
    """Validates that a SUPERVISOR possesses legitimate authority to add reference watchlist entries."""
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    test_doc_id = f"WATCH-SUP-{int(time.time())}"
    payload = {
        "document_id": test_doc_id,
        "full_name": "LEGITIMATE WATCHLIST ENTRY",
        "nationality": "IND",
        "reason": "Authorized supervisory entry",
        "risk_category": "LOOKOUT_CIRCULAR",
        "status": "ACTIVE"
    }
    res = client.post("/api/v1/watchlist", headers=headers, json=payload)
    assert res.status_code == 200
    assert res.json()["document_id"] == test_doc_id


def test_t03_centralized_permissions_logic():
    """Directly tests centralized permission definitions in backend.app.core.permissions."""
    officer_user = User(username="off1", role="OFFICER")
    supervisor_user = User(username="sup1", role="SUPERVISOR")

    assert has_permission(officer_user, PERM_SCREENING_VIEW) is True
    assert has_permission(officer_user, PERM_WATCHLIST_MANAGE) is False
    assert has_permission(supervisor_user, PERM_WATCHLIST_MANAGE) is True
    assert has_permission(supervisor_user, PERM_CASE_REVIEW) is True


# ==============================================================================
# T-04: Insecure Direct Object Reference (IDOR) & Checkpoint Isolation Policy
# ==============================================================================

def test_t04_delhi_officer_can_access_delhi_screening(delhi_officer_token, checkpoint_screenings):
    """Delhi officer accessing Delhi screening succeeds (200 OK)."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get(f"/api/v1/screenings/{checkpoint_screenings['delhi_id']}", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == checkpoint_screenings["delhi_id"]


def test_t04_delhi_officer_denied_raxaul_screening_detail(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to inspect Raxaul screening returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get(f"/api/v1/screenings/{checkpoint_screenings['raxaul_id']}", headers=headers)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_delhi_officer_denied_raxaul_media_asset(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to stream Raxaul document media returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get(f"/api/v1/screenings/media/{checkpoint_screenings['raxaul_id']}/doc", headers=headers)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_delhi_officer_denied_raxaul_pdf_report(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to download Raxaul PDF report returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get(f"/api/v1/reports/{checkpoint_screenings['raxaul_id']}/pdf", headers=headers)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_delhi_officer_denied_raxaul_audit_trail(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to query Raxaul audit trail returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get(f"/api/v1/audit/{checkpoint_screenings['raxaul_id']}", headers=headers)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_delhi_officer_denied_raxaul_case_status_update(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to modify Raxaul case status returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    payload = {"status": "CLEARED", "officer_notes": "Unauthorized status tampering"}
    res = client.put(f"/api/v1/cases/{checkpoint_screenings['raxaul_id']}/status", headers=headers, json=payload)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_delhi_officer_denied_raxaul_blockchain_anchor(delhi_officer_token, checkpoint_screenings):
    """Delhi officer attempting to anchor Raxaul screening returns HTTP 403 Forbidden."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.post(f"/api/v1/blockchain/{checkpoint_screenings['raxaul_id']}/anchor", headers=headers)
    assert res.status_code == 403
    assert "belongs to checkpoint" in res.json()["detail"]


def test_t04_supervisor_cross_checkpoint_access(supervisor_token, checkpoint_screenings):
    """Supervisors possess legitimate operational visibility across all checkpoints (returns 200)."""
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    res1 = client.get(f"/api/v1/screenings/{checkpoint_screenings['delhi_id']}", headers=headers)
    assert res1.status_code == 200

    res2 = client.get(f"/api/v1/screenings/{checkpoint_screenings['raxaul_id']}", headers=headers)
    assert res2.status_code == 200


def test_t04_station_isolation_logs_access_denied_audit(delhi_officer_token, checkpoint_screenings, db_session):
    """Verifies that an unauthorized cross-station access attempt logs an ACCESS_DENIED audit ledger entry."""
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    client.get(f"/api/v1/screenings/{checkpoint_screenings['raxaul_id']}", headers=headers)

    denied_event = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.screening_id == checkpoint_screenings["raxaul_id"],
            AuditEvent.event_type == "ACCESS_DENIED"
        )
        .first()
    )
    assert denied_event is not None
    assert denied_event.event_type == "ACCESS_DENIED"


# ==============================================================================
# T-05: Malicious File Upload & Polyglot Defense
# ==============================================================================

def test_t05_upload_zero_bytes_rejected(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    files = {"document_file": ("test.jpg", b"", "image/jpeg")}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data={"document_type": "PASSPORT"})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_t05_upload_fake_mime_polyglot_rejected(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    fake_bytes = b"<html><script>alert('XSS')</script></html>"
    files = {"document_file": ("passport.jpg", fake_bytes, "image/jpeg")}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data={"document_type": "PASSPORT"})
    assert res.status_code == 400
    assert "header does not match" in res.json()["detail"].lower() or "polyglot" in res.json()["detail"].lower()


def test_t05_upload_corrupt_image_bytes_rejected(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    corrupt_bytes = b"\xFF\xD8\xFF" + b"\x00\x11\x22\x33" * 50
    files = {"document_file": ("corrupt.jpg", corrupt_bytes, "image/jpeg")}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data={"document_type": "PASSPORT"})
    assert res.status_code == 400
    assert "corrupted" in res.json()["detail"].lower() or "decoded" in res.json()["detail"].lower()


def test_t05_upload_oversized_file_rejected(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    big_file = b"\xFF\xD8\xFF" + b"\x00" * (15 * 1024 * 1024)
    files = {"document_file": ("huge.jpg", big_file, "image/jpeg")}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data={"document_type": "PASSPORT"})
    assert res.status_code in [400, 413]


def test_t05_upload_decompression_bomb_rejected():
    """Decompression bomb protection: image exceeding MAX_IMAGE_DIMENSION is rejected."""
    bomb_img = Image.new("RGB", (6000, 6000), (255, 255, 255))
    bio = io.BytesIO()
    bomb_img.save(bio, format="JPEG")
    bomb_bytes = bio.getvalue()

    with pytest.raises(Exception) as exc_info:
        validate_uploaded_image_bytes(bomb_bytes, "bomb.jpg")
    assert "permitted processing dimensions" in str(exc_info.value).lower() or "exceeds" in str(exc_info.value).lower()


def test_t05_upload_disallowed_extension_rejected():
    with pytest.raises(Exception) as exc_info:
        validate_uploaded_image_bytes(b"\xFF\xD8\xFFvalid", "evil.sh")
    assert "invalid file extension" in str(exc_info.value).lower()


# ==============================================================================
# T-06: Directory & Path Traversal Safeguards
# ==============================================================================

def test_t06_path_traversal_filename_sanitized():
    safe_name = sanitize_filename("../../../../../etc/passwd")
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert ".." not in safe_name
    assert "passwd" in safe_name


def test_t06_media_path_traversal_prevented(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get("/api/v1/screenings/media/..%2F..%2Fetc/doc", headers=headers)
    assert res.status_code in [400, 403, 404]


# ==============================================================================
# T-07: Denial of Service & In-Memory Rate Limiting
# ==============================================================================

def test_t07_rate_limiter_blocks_excessive_login_attempts():
    limiter.reset()
    for _ in range(settings.LOGIN_RATE_LIMIT):
        client.post("/api/v1/auth/login", json={"username": "officer", "password": "wrongpassword"})

    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "wrongpassword"})
    assert res.status_code == 429
    assert "too many" in res.json()["detail"].lower()
    limiter.reset()


# ==============================================================================
# T-08: SQL Injection / Input Validation Defenses
# ==============================================================================

def test_t08_sql_injection_in_screening_id_handled(delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    sqli_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE screenings; --",
        "1 UNION SELECT null, null, null--",
        "admin'--"
    ]
    for sqli in sqli_payloads:
        res = client.get(f"/api/v1/screenings/{sqli}", headers=headers)
        assert res.status_code in [400, 404]


# ==============================================================================
# T-09: XSS / Template Injection / PDF ReportLab Escaping
# ==============================================================================

def test_t09_xss_and_xml_in_pdf_report_sanitized():
    test_payload = {
        "id": "CASE-XSS-SEC-01",
        "created_at": "2026-09-19T23:50:00Z",
        "operator_name": "<script>alert('XSS')</script> & Officer 'Special' <Tag>",
        "operator_badge": "SSB-<123>&456",
        "checkpoint_id": "CP-DEL-AIR",
        "checkpoint_name": "Delhi & Indira Gandhi <Airport>",
        "document_type": "PASSPORT",
        "masked_document_id": "Z12****<script>",
        "status": "MANUAL_REVIEW_REQUIRED",
        "risk_score": 75.0,
        "risk_band": "HIGH",
        "recommendation": "ESCALATE <immediately>",
        "extracted_fields": [
            {
                "field_name": "Full Name <xml>",
                "visual_value": "JOHN & DOE <JR>",
                "mrz_value": "JOHN<<DOE<JR",
                "confidence": 0.95,
                "match_status": "MATCH"
            }
        ],
        "tamper_summary": {
            "composite_tamper_score": 0.85,
            "signals": {
                "ela": {"anomaly_score": 0.85},
                "noise_residual": {"anomaly_score": 0.12},
                "copy_move": {"anomaly_score": 0.05}
            }
        },
        "face_result": None,
        "risk_reasons": [
            {
                "category": "TAMPERING",
                "severity": "CRITICAL",
                "summary": "Photo manipulation detected with <unauthorized> overlay & script.",
                "action": "Investigate"
            }
        ],
        "audit_trail": [{"event_hash": "a" * 64}]
    }

    out_pdf = os.path.join(settings.REPORT_DIR, "test_xss_sanitized.pdf")
    ReportGenerator.generate_pdf(test_payload, out_pdf)
    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 1000
    try:
        os.remove(out_pdf)
    except Exception:
        pass


# ==============================================================================
# T-10: Password Cracking & Credential Protection
# ==============================================================================

def test_t10_bcrypt_work_factor_12():
    password = "SuperSecretPassword123"
    hashed = get_password_hash(password)
    assert hashed.startswith("$2b$12$") or hashed.startswith("$2a$12$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_t10_timing_safe_error_messages():
    res1 = client.post("/api/v1/auth/login", json={"username": "nonexistent_user", "password": "anypassword"})
    res2 = client.post("/api/v1/auth/login", json={"username": "officer", "password": "wrongpassword"})
    
    assert res1.status_code == 401
    assert res2.status_code == 401
    assert res1.json()["detail"] == res2.json()["detail"]


def test_t10_no_password_or_hash_in_responses(delhi_officer_token):
    login_res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "officer123"})
    assert "password" not in login_res.json()
    assert "hashed_password" not in login_res.json()

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {delhi_officer_token}"})
    assert "password" not in me_res.json()
    assert "hashed_password" not in me_res.json()


# ==============================================================================
# T-11: Cross-Origin Resource Sharing (CORS) Non-Wildcard Integrity
# ==============================================================================

def test_t11_cors_disallows_wildcard_with_credentials():
    cors_list = settings.cors_origins_list
    assert "*" not in cors_list
    assert any("localhost" in origin or "127.0.0.1" in origin for origin in cors_list)


# ==============================================================================
# T-12: Sensitive Data Exposure & PII Masking
# ==============================================================================

def test_t12_pii_masking_utilities():
    assert mask_document_number("Z1234567") == "Z12***67"
    assert mask_document_number("A12") == "****"
    assert mask_full_name("ARJUN SHARMA") == "A***N S****A"
    assert mask_date_of_birth("1992-08-24") == "1992-**-**"


def test_t12_zero_pii_in_fabric_anchor_payload():
    """Validates that Fabric privacy validator accepts clean payloads and strictly rejects PII."""
    clean_payload = {
        "screening_id": "SCREEN-TEST-01",
        "document_hash": "a" * 64,
        "result_hash": "b" * 64,
        "checkpoint_id": "CP-DEL-AIR",
        "risk_band": "LOW"
    }
    is_valid, err = FabricAnchorService.validate_no_pii_in_payload(clean_payload)
    assert is_valid is True
    assert err is None

    # Payload with passenger PII key must be rejected
    pii_payload = {
        "screening_id": "SCREEN-TEST-01",
        "document_hash": "a" * 64,
        "full_name": "JOHN DOE"
    }
    is_valid, err = FabricAnchorService.validate_no_pii_in_payload(pii_payload)
    assert is_valid is False
    assert "PII leakage detected" in err


# ==============================================================================
# T-13: Cryptographic Audit Trail Tampering & Security Auditing
# ==============================================================================

def test_t13_audit_trail_tamper_detection(db_session):
    test_sid = f"AUDIT-TEST-{int(time.time() * 1000)}"
    AuditService.record_event(db_session, test_sid, "DOC_UPLOAD", {"file": "doc.jpg"})
    AuditService.record_event(db_session, test_sid, "OCR_DONE", {"fields": 10})
    AuditService.record_event(db_session, test_sid, "RISK_EVAL", {"score": 20.0})

    res_intact = AuditService.verify_audit_chain(db_session, test_sid)
    assert res_intact["is_valid"] is True
    assert res_intact["total_events"] == 3

    # Tamper with middle event's payload hash (retroactive evidence manipulation)
    events = db_session.query(AuditEvent).filter(AuditEvent.screening_id == test_sid).order_by(AuditEvent.id.asc()).all()
    events[1].payload_hash = "e" * 64
    db_session.commit()

    res_tampered = AuditService.verify_audit_chain(db_session, test_sid)
    assert res_tampered["is_valid"] is False
    assert "tampered_at_event_id" in res_tampered
    assert res_tampered["tampered_at_event_id"] == events[1].id


def test_t13_login_failure_event_recorded(db_session):
    """Verifies that a bad login attempt appends a LOGIN_FAILURE event to the audit ledger."""
    bad_username = f"attacker_{int(time.time() * 1000)}"
    client.post("/api/v1/auth/login", json={"username": bad_username, "password": "bad"})

    ev = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.screening_id == f"AUTH-{bad_username[:32]}",
            AuditEvent.event_type == "LOGIN_FAILURE"
        )
        .first()
    )
    assert ev is not None
    assert ev.actor == "SYSTEM:AUTH_GATEWAY"


def test_t13_watchlist_change_event_recorded(supervisor_token, db_session):
    """Verifies that adding a watchlist record appends a WATCHLIST_CHANGE event to the audit ledger."""
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    doc_id = f"WL-AUDIT-{int(time.time() * 1000)}"
    client.post("/api/v1/watchlist", headers=headers, json={
        "document_id": doc_id,
        "full_name": "AUDIT LOG ENTRY",
        "reason": "Test audit event recording"
    })

    ev = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.screening_id == f"WATCHLIST-{doc_id}",
            AuditEvent.event_type == "WATCHLIST_CHANGE"
        )
        .first()
    )
    assert ev is not None
    assert ev.actor.startswith("SUPERVISOR:")


# ==============================================================================
# T-14: Blockchain Anchor Forgery & Local Discrepancy Detection
# ==============================================================================

def test_t14_blockchain_verification_detects_discrepancy(db_session):
    """Validates that Fabric anchor verification detects discrepancies between stored anchor and local state."""
    test_sid = f"BC-VERIFY-{int(time.time() * 1000)}"
    sc = Screening(
        id=test_sid,
        checkpoint_id="CP-DEL-AIR",
        document_type="PASSPORT",
        masked_document_id="Z11****22",
        status="CLEARED",
        risk_score=15.0,
        risk_band="LOW",
        recommendation="CLEAR",
        operator_id=1
    )
    db_session.add(sc)
    db_session.commit()

    anchor = FabricAnchorService.create_anchor(
        db=db_session,
        screening_id=test_sid,
        doc_bytes=b"\xFF\xD8\xFF" + b"\x00" * 100,
        risk_band="LOW",
        checkpoint_id="CP-DEL-AIR",
        actor="SSB-4092"
    )
    assert anchor["status"] in ["VERIFIED", "ANCHORED", "UNAVAILABLE"]

    # Alter the local result hash on the anchor record (simulating ledger/local discrepancy)
    anchor_rec = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == test_sid).first()
    anchor_rec.result_hash = "0" * 64
    db_session.commit()

    # Re-verify -> Discrepancy must be flagged
    verify_res = FabricAnchorService.verify_anchor(db=db_session, screening_id=test_sid, actor="SSB-4092")
    assert verify_res["is_verified"] is False
    assert verify_res["result_hash_matches"] is False


# ==============================================================================
# T-15: Information Disclosure & Traceback Suppression
# ==============================================================================

def test_t15_security_headers_present():
    """Validates that defense-in-depth security headers are attached to API responses."""
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in res.headers.get("Referrer-Policy", "")
    assert "camera" in res.headers.get("Permissions-Policy", "")


def test_t15_static_storage_mount_closed():
    """Validates that /storage static files are not exposed to the public web."""
    res = client.get("/storage/doc_123.jpg")
    assert res.status_code == 404
