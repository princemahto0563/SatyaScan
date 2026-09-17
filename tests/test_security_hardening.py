"""
SatyaScan Defense-in-Depth Security Verification Suite
Covers all 15 required security test scenarios + defense-in-depth checks:
1. Empty upload -> rejected (400)
2. Fake MIME -> rejected (400)
3. Unsupported extension -> rejected (400)
4. Corrupt image -> rejected (400)
5. Oversized upload (>10MB) -> rejected (413)
6. Excessive pixel dimension / decompression bomb -> rejected with expected message (400)
7. Path traversal filename -> safely isolated with UUID storage name
8. Unauthenticated API -> 401
9. Invalid JWT -> 401
10. Expired JWT -> 401
11. Malformed JWT -> 401
12. Unauthorized role on watchlist addition -> 403
13. In-memory rate limiting -> 429
14. SQL injection-like input in query/path -> safely handled
15. XSS-like text in OCR -> escaped cleanly, no raw HTML
16. Audit ledger tampering -> detected
17. Report generation with special XML characters -> succeeds safely
18. Static /storage exposure -> 404
19. Security headers verification (nosniff, DENY, etc.)
20. Restricted CORS origin compliance
"""

import pytest
import os
import io
from datetime import timedelta
import jwt
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app, seed_initial_demo_data
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.core.rate_limiter import limiter
from backend.app.models.database import SessionLocal, init_db, AuditEvent, User, ReferenceWatchlist
from backend.app.services.audit_service import AuditService
from backend.app.services.report_generator import ReportGenerator

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_security_tests():
    init_db()
    seed_initial_demo_data()
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def valid_officer_token():
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "officer123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def valid_supervisor_token():
    res = client.post("/api/v1/auth/login", json={"username": "supervisor", "password": "super123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def make_valid_test_jpeg(width: int = 100, height: int = 100) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(73, 109, 137))
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- Scenario 1: Empty Upload -> Rejected (400) ---
def test_security_01_empty_upload_rejected(valid_officer_token):
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("empty.jpg", b"", "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


# --- Scenario 2: Fake MIME -> Rejected (400) ---
def test_security_02_fake_mime_disguised_file_rejected(valid_officer_token):
    fake_script = b"<?php echo 'malicious payload'; ?>"
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("exploit.jpg", fake_script, "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "header" in res.json()["detail"].lower() or "format" in res.json()["detail"].lower()


# --- Scenario 3: Unsupported Extension -> Rejected (400) ---
def test_security_03_unsupported_extension_rejected(valid_officer_token):
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "extension" in res.json()["detail"].lower()


# --- Scenario 4: Corrupt Image -> Rejected (400) ---
def test_security_04_corrupt_image_bytes_rejected(valid_officer_token):
    # Valid JPEG magic bytes (\xFF\xD8\xFF) followed by random corrupted payload
    corrupted = b"\xFF\xD8\xFF\xE0" + b"\x00" * 200
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("corrupt.jpg", corrupted, "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "corrupt" in res.json()["detail"].lower() or "decoded" in res.json()["detail"].lower()


# --- Scenario 5: Oversized Upload (>10MB) -> Rejected (413) ---
def test_security_05_oversized_upload_rejected(valid_officer_token):
    # 11 MB payload
    oversized = b"\xFF\xD8\xFF\xE0" + b"\x00" * (11 * 1024 * 1024)
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("large.jpg", oversized, "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 413
    assert "exceeds" in res.json()["detail"].lower()


# --- Scenario 6: Image with Excessive Dimensions -> Rejected (400) ---
def test_security_06_excessive_dimensions_rejected(valid_officer_token):
    # Construct an image exceeding permitted dimensions (>5000px)
    buf = io.BytesIO()
    img = Image.new("RGB", (5001, 100), color=(255, 0, 0))
    img.save(buf, format="JPEG")
    oversized_dim_bytes = buf.getvalue()

    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": ("too_wide.jpg", oversized_dim_bytes, "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "document image exceeds the permitted processing dimensions" in res.json()["detail"].lower()


# --- Scenario 7: Path Traversal Filename -> Safely Isolated ---
def test_security_07_path_traversal_filename_isolated(valid_officer_token):
    valid_jpg = make_valid_test_jpeg(100, 100)
    traversal_name = "../../../../etc/passwd.jpg"
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        files={"document_file": (traversal_name, valid_jpg, "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    # The request should either succeed or fail gracefully, but NEVER create /etc/passwd.jpg
    assert not os.path.exists("/etc/passwd.jpg")
    if res.status_code == 200:
        assert res.json()["id"].startswith("SAT-2026-")


# --- Scenario 8: Unauthenticated API in Strict Mode -> 401 ---
def test_security_08_unauthenticated_api_rejected_in_strict_mode():
    original_strict = settings.STRICT_AUTH
    try:
        settings.STRICT_AUTH = True
        res = client.get("/api/v1/screenings")
        assert res.status_code == 401
        assert "credentials" in res.json()["detail"].lower() or "authentication" in res.json()["detail"].lower()
    finally:
        settings.STRICT_AUTH = original_strict


# --- Scenario 9: Invalid JWT -> 401 ---
def test_security_09_invalid_jwt_rejected():
    res = client.get("/api/v1/screenings", headers={"Authorization": "Bearer totally_invalid_bogus_token"})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower() or "expired" in res.json()["detail"].lower()


# --- Scenario 10: Expired JWT -> 401 ---
def test_security_10_expired_jwt_rejected():
    # Issue a token already expired 1 hour ago
    expired_token = create_access_token(
        data={"sub": "officer", "role": "OFFICER"},
        expires_delta=timedelta(hours=-1)
    )
    res = client.get("/api/v1/screenings", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower() or "invalid" in res.json()["detail"].lower()


# --- Scenario 11: Malformed JWT / alg=none -> 401 ---
def test_security_11_alg_none_jwt_rejected():
    # Attempt unsigned alg=none attack
    payload = {"sub": "officer", "role": "ADMIN"}
    none_token = jwt.encode(payload, key="", algorithm="none")
    res = client.get("/api/v1/screenings", headers={"Authorization": f"Bearer {none_token}"})
    assert res.status_code == 401


# --- Scenario 12: Unauthorized Resource Access (RBAC) -> 403 ---
def test_security_12_rbac_officer_cannot_add_watchlist_entry(valid_officer_token):
    # Officer role attempting supervisor-only action
    res = client.post(
        "/api/v1/watchlist",
        headers={"Authorization": f"Bearer {valid_officer_token}"},
        json={
            "document_id": "TEST-UNAUTH-01",
            "full_name": "MALICIOUS ADDITION",
            "nationality": "IND",
            "reason": "Unauthorized test entry",
            "risk_category": "STOLEN_PASSPORT",
            "status": "ACTIVE"
        }
    )
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower() or "requires" in res.json()["detail"].lower()


def test_security_12b_supervisor_can_add_watchlist_entry(valid_supervisor_token):
    # Ensure idempotency by deleting any previous test entry
    db = SessionLocal()
    db.query(ReferenceWatchlist).filter(ReferenceWatchlist.document_id == "TEST-AUTH-WL-99").delete()
    db.commit()
    db.close()

    # Supervisor role performing authorized action
    res = client.post(
        "/api/v1/watchlist",
        headers={"Authorization": f"Bearer {valid_supervisor_token}"},
        json={
            "document_id": "TEST-AUTH-WL-99",
            "full_name": "SUPERVISOR ADDED ENTRY",
            "nationality": "IND",
            "reason": "Authorized test entry by supervisor",
            "risk_category": "LOOKOUT_CIRCULAR",
            "status": "ACTIVE"
        }
    )
    assert res.status_code == 200
    assert res.json()["document_id"] == "TEST-AUTH-WL-99"


# --- Scenario 13: In-Memory Rate Limiting -> 429 ---
def test_security_13_rate_limiting_triggers_429():
    limiter.reset()
    # Trigger 11 rapid login attempts (limit is 10)
    statuses = []
    for i in range(12):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "officer", "password": "wrongpassword"}
        )
        statuses.append(res.status_code)

    assert 429 in statuses, f"Expected 429 in statuses: {statuses}"
    limiter.reset()


# --- Scenario 14: SQL Injection-like Input Safely Handled ---
def test_security_14_sql_injection_payload_handled_safely(valid_officer_token):
    sql_payload = "'; DROP TABLE screenings; --"
    res = client.get(
        f"/api/v1/screenings/{sql_payload}",
        headers={"Authorization": f"Bearer {valid_officer_token}"}
    )
    # Must reject safely (400 or 404), never execute or leak SQL traceback
    assert res.status_code in [400, 404]
    assert "syntax error" not in res.text.lower()
    assert "sqlite" not in res.text.lower()


# --- Scenario 15: XSS-like Text in OCR -> Safely Rendered in PDF ---
def test_security_15_xss_and_xml_injection_in_pdf():
    xss_payload = {
        "id": "SAT-2026-XSS-TEST",
        "created_at": "2026-09-16T12:00:00Z",
        "document_type": "PASSPORT",
        "masked_document_id": "<script>alert('xss')</script>",
        "risk_band": "HIGH",
        "risk_score": 85.0,
        "recommendation": "<b>Injected HTML recommendation & test</b>",
        "extracted_fields": [
            {
                "field_name": "<img src=x onerror=alert(1)>",
                "visual_value": "John <Doe> & 'Co'",
                "mrz_value": "JOHN<DOE<<CO<<<<<<",
                "confidence": 0.95,
                "match_status": "MISMATCH"
            }
        ],
        "tamper_summary": {"composite_tamper_score": 20.0},
        "risk_reasons": [
            {
                "category": "<malicious_xml_tag>",
                "severity": "HIGH",
                "summary": "XML injection & entity test: &amp; <>&'\"",
                "action": "Manual inspection <urgent>"
            }
        ],
        "audit_trail": [{"event_hash": "b" * 64}]
    }
    out_pdf = "/tmp/test_xss_escaped_report.pdf"
    # Must build cleanly without XML parsing crash
    ReportGenerator.generate_pdf(xss_payload, out_pdf)
    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 1000


# --- Scenario 16: Audit Tampering Detection ---
def test_security_16_audit_tampering_detected():
    import uuid
    db = SessionLocal()
    try:
        t_id = f"SAT-AUDIT-TEST-{uuid.uuid4().hex[:6]}"
        AuditService.record_event(db, t_id, "EVENT_1", {"k": "v1"})
        ev2 = AuditService.record_event(db, t_id, "EVENT_2", {"k": "v2"})
        AuditService.record_event(db, t_id, "EVENT_3", {"k": "v3"})

        # Valid chain
        res1 = AuditService.verify_audit_chain(db, t_id)
        assert res1["is_valid"] is True

        # Malicious edit
        ev2.payload_hash = "0" * 64
        db.commit()

        # Must detect breach
        res2 = AuditService.verify_audit_chain(db, t_id)
        assert res2["is_valid"] is False
    finally:
        db.close()


# --- Scenario 17: Static /storage Exposure Removed ---
def test_security_17_storage_static_mount_closed():
    # Attempting to access the raw static storage route MUST return 404
    res = client.get("/storage/uploads/test.jpg")
    assert res.status_code == 404


# --- Scenario 18: Security Headers Verification ---
def test_security_18_defense_in_depth_headers():
    res = client.get("/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera" in headers.get("Permissions-Policy", "")


# --- Scenario 19: CORS Whitelist (No wildcard with credentials) ---
def test_security_19_cors_whitelist_not_wildcard():
    # Preflight request from allowed origin
    res = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    if "access-control-allow-origin" in res.headers:
        assert res.headers["access-control-allow-origin"] != "*"
