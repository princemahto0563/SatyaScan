"""
SatyaScan Backend API & Audit Chain Integration Tests
Tests FastAPI endpoints, JWT auth, file upload security,
tamper-evident SHA-256 hash chaining, and PDF report creation.
"""

import pytest
import os
import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app, seed_initial_demo_data
from backend.app.models.database import SessionLocal, init_db, Screening, AuditEvent
from backend.app.services.audit_service import AuditService
from backend.app.services.report_generator import ReportGenerator

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()
    seed_initial_demo_data()


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "SatyaScan" in data["service"]


def test_auth_login_and_me():
    # Login with default seeded officer
    login_res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "officer123"})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["role"] == "OFFICER"

    # Access /auth/me with bearer token
    token = token_data["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "officer"


def test_file_upload_security_rejects_empty_and_fake_mime():
    # Attempt upload with zero bytes
    res = client.post(
        "/api/v1/screenings",
        files={"document_file": ("test.jpg", b"", "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()

    # Attempt upload with malicious text disguised as jpg (invalid magic header)
    res_fake = client.post(
        "/api/v1/screenings",
        files={"document_file": ("malicious.jpg", b"SELECT * FROM users;", "image/jpeg")},
        data={"document_type": "PASSPORT"}
    )
    assert res_fake.status_code == 400
    assert "header" in res_fake.json()["detail"].lower() or "format" in res_fake.json()["detail"].lower()


def test_screening_pipeline_execution():
    doc_path = "data/genuine/case01_genuine_arjun.jpg"
    assert os.path.exists(doc_path), "Synthetic test document missing"

    with open(doc_path, "rb") as f_doc:
        res = client.post(
            "/api/v1/screenings",
            files={"document_file": ("passport.jpg", f_doc.read(), "image/jpeg")},
            data={"document_type": "PASSPORT"}
        )

    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["id"].startswith("SAT-2026-")
    assert "risk_score" in data
    assert "risk_band" in data
    assert "quality_assessment" in data
    assert "audit_trail" in data
    assert len(data["audit_trail"]) >= 4

    screening_id = data["id"]

    # Verify audit chain endpoint
    audit_res = client.post(f"/api/v1/audit/{screening_id}/verify")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["is_valid"] is True
    assert audit_data["total_events"] >= 4


def test_audit_chain_detects_retroactive_tampering():
    import uuid
    db = SessionLocal()
    try:
        # Create a test screening with 3 chained audit events using a unique ID
        test_id = f"SAT-TEST-TAMPER-{uuid.uuid4().hex[:8]}"
        ev1 = AuditService.record_event(db, test_id, "UPLOAD", {"val": 1})
        ev2 = AuditService.record_event(db, test_id, "OCR", {"val": 2})
        ev3 = AuditService.record_event(db, test_id, "RISK", {"val": 3})

        # Chain must be valid initially
        check1 = AuditService.verify_audit_chain(db, test_id)
        assert check1["is_valid"] is True

        # Now simulate a database breach: attacker modifies payload of event 2
        ev2.payload_hash = "deadbeef" * 8
        db.commit()

        # Audit verification MUST catch this tampering!
        check2 = AuditService.verify_audit_chain(db, test_id)
        assert check2["is_valid"] is False
        assert "mismatch" in check2["status_message"].lower() or "discontinuity" in check2["status_message"].lower()
    finally:
        db.close()


def test_reportlab_pdf_generation():
    test_payload = {
        "id": "SAT-2026-TESTPDF",
        "created_at": "2026-09-13T12:00:00Z",
        "document_type": "PASSPORT",
        "masked_document_id": "Z12****67",
        "risk_band": "LOW",
        "risk_score": 12.5,
        "recommendation": "Routine Clearance Permitted",
        "extracted_fields": [
            {"field_name": "passport_number", "visual_value": "Z1234567", "mrz_value": "Z1234567", "confidence": 0.98, "match_status": "MATCH"}
        ],
        "tamper_summary": {"composite_tamper_score": 15.0},
        "audit_trail": [{"event_hash": "a" * 64}]
    }
    out_pdf = "/tmp/test_report.pdf"
    ReportGenerator.generate_pdf(test_payload, out_pdf)

    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 1000  # Non-empty valid PDF
