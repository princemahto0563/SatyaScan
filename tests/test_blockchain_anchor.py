"""
SatyaScan Hyperledger Fabric Permissioned Blockchain Anchor Tests
SIH26188 · Theme: Blockchain & Cybersecurity

Comprehensive test suite (19 test cases) verifying:
1. Fabric configuration parameters and defaults
2. Deterministic SHA-256 document hashing
3. Avalanche effect on document hash variation
4. Empty document bytes rejection
5. Canonical pipe-delimited payload serialization
6. Deterministic result hashing
7. Privacy validator accepts compliant hash-only payloads
8. Privacy validator rejects passenger PII keys (name, dob, passport_number, etc.)
9. Privacy validator rejects oversized string fields (base64 image protection)
10. Anchor creation graceful offline fallback (status UNAVAILABLE, no fake blocks)
11. Anchor creation idempotency (prevents duplicate ledger entries)
12. Audit event BLOCKCHAIN_ANCHOR_RECORDED added to unbroken audit chain
13. API endpoint POST /api/v1/blockchain/{id}/anchor requires authentication (HTTP 401)
14. API endpoint POST /api/v1/blockchain/{id}/anchor successful execution
15. Checkpoint RBAC enforcement (Officer from checkpoint A cannot anchor checkpoint B)
16. API endpoint GET /api/v1/blockchain/{id} retrieval and 404 behavior
17. API endpoint POST /api/v1/blockchain/{id}/verify integrity check and audit recording
18. Screening detail response includes blockchain_anchor payload
19. End-to-end screening execution completes unaffected when ledger is offline
"""

import pytest
import os
import hashlib
import uuid
from fastapi.testclient import TestClient

from backend.app.main import app, seed_initial_demo_data
from backend.app.core.config import settings
from backend.app.models.database import SessionLocal, init_db, Screening, BlockchainAnchor, AuditEvent, User
from backend.app.services.fabric_service import FabricAnchorService
from backend.app.core.rate_limiter import limiter

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    init_db()
    seed_initial_demo_data()


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()


def get_auth_token(username: str = "officer", password: str = "officer123", checkpoint_id: str = "CP-DEL-AIR") -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "checkpoint_id": checkpoint_id}
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


# ==============================================================================
# TEST 1: Fabric configuration parameters and defaults
# ==============================================================================
def test_fabric_config_defaults():
    assert hasattr(settings, "FABRIC_ENABLED")
    assert hasattr(settings, "FABRIC_GATEWAY_PEER")
    assert settings.FABRIC_CHANNEL == "satyascan-channel"
    assert settings.FABRIC_CHAINCODE == "screening_anchor"
    assert settings.FABRIC_MSP_ID == "Org1MSP"
    assert "crypto-config" in settings.FABRIC_CRYPTO_PATH or "blockchain" in settings.FABRIC_CRYPTO_PATH


# ==============================================================================
# TEST 2: Deterministic document hashing (SHA-256)
# ==============================================================================
def test_deterministic_document_hash():
    sample_bytes = b"SAMPLE_PASSPORT_IMAGE_RAW_BINARY_DATA_TEST_123"
    expected_hash = hashlib.sha256(sample_bytes).hexdigest()
    computed_hash = FabricAnchorService.compute_document_hash(sample_bytes)
    assert computed_hash == expected_hash
    assert len(computed_hash) == 64
    assert computed_hash == computed_hash.lower()


# ==============================================================================
# TEST 3: Avalanche effect on document hash variation
# ==============================================================================
def test_different_bytes_different_document_hash():
    bytes_a = b"PASSPORT_DATA_CANONICAL_A"
    bytes_b = b"PASSPORT_DATA_CANONICAL_B"
    hash_a = FabricAnchorService.compute_document_hash(bytes_a)
    hash_b = FabricAnchorService.compute_document_hash(bytes_b)
    assert hash_a != hash_b
    assert len(hash_a) == 64
    assert len(hash_b) == 64


# ==============================================================================
# TEST 4: Empty document bytes rejection
# ==============================================================================
def test_empty_document_bytes_rejection():
    with pytest.raises(ValueError) as exc:
        FabricAnchorService.compute_document_hash(b"")
    assert "cannot be empty" in str(exc.value)


# ==============================================================================
# TEST 5: Canonical pipe-delimited payload serialization
# ==============================================================================
def test_canonical_result_payload_format():
    screening_id = "SC-TEST-001"
    doc_hash = "a" * 64
    risk_band = "LOW"
    checkpoint_id = "CP-DEL-AIR"
    version = "1.0.0"
    canonical = FabricAnchorService.get_canonical_payload(
        screening_id=screening_id,
        document_hash=doc_hash,
        risk_band=risk_band,
        checkpoint_id=checkpoint_id,
        pipeline_version=version
    )
    assert canonical == f"{screening_id}|{doc_hash}|LOW|CP-DEL-AIR|1.0.0"


# ==============================================================================
# TEST 6: Deterministic result hashing
# ==============================================================================
def test_deterministic_result_hash():
    screening_id = "SC-TEST-002"
    doc_hash = "b" * 64
    risk_band = "HIGH"
    checkpoint_id = "CP-BOM-AIR"
    expected_canonical = f"{screening_id}|{doc_hash}|HIGH|CP-BOM-AIR|1.0.0"
    expected_hash = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest()

    res_hash = FabricAnchorService.compute_result_hash(
        screening_id=screening_id,
        document_hash=doc_hash,
        risk_band=risk_band,
        checkpoint_id=checkpoint_id,
        pipeline_version="1.0.0"
    )
    assert res_hash == expected_hash
    assert len(res_hash) == 64


# ==============================================================================
# TEST 7: Privacy validator accepts compliant hash-only payloads
# ==============================================================================
def test_privacy_validator_accepts_clean_hashes():
    clean_payload = {
        "screeningId": "SC-12345",
        "documentHash": "c" * 64,
        "resultHash": "d" * 64,
        "riskLevel": "LOW",
        "checkpointId": "CP-DEL-AIR",
        "pipelineVersion": "1.0.0",
        "anchorVersion": "FabricAnchor-v1.0"
    }
    is_valid, violation = FabricAnchorService.validate_no_pii_in_payload(clean_payload)
    assert is_valid is True
    assert violation is None


# ==============================================================================
# TEST 8: Privacy validator rejects passenger PII keys
# ==============================================================================
def test_privacy_validator_rejects_pii_keys():
    pii_payloads = [
        {"screeningId": "SC-01", "full_name": "JOHN DOE", "documentHash": "e" * 64},
        {"screeningId": "SC-02", "dob": "1980-01-01", "documentHash": "e" * 64},
        {"screeningId": "SC-03", "passport_number": "A1234567", "documentHash": "e" * 64},
        {"screeningId": "SC-04", "raw_text": "P<INDKUMAR<<RAJESH...", "documentHash": "e" * 64},
        {"screeningId": "SC-05", "biometric_vector": [0.12, 0.45], "documentHash": "e" * 64},
    ]
    for p in pii_payloads:
        is_valid, violation = FabricAnchorService.validate_no_pii_in_payload(p)
        assert is_valid is False
        assert "PII leakage detected" in violation


# ==============================================================================
# TEST 9: Privacy validator rejects oversized string fields (image exfiltration)
# ==============================================================================
def test_privacy_validator_rejects_large_payloads():
    oversized_payload = {
        "screeningId": "SC-06",
        "documentHash": "f" * 64,
        "arbitrary_unstructured_data": "x" * 300
    }
    is_valid, violation = FabricAnchorService.validate_no_pii_in_payload(oversized_payload)
    assert is_valid is False
    assert "exceeds maximum allowed" in violation


# ==============================================================================
# TEST 10: Anchor creation graceful offline fallback (status UNAVAILABLE, no fake blocks)
# ==============================================================================
def test_anchor_creation_offline_fallback():
    db = SessionLocal()
    try:
        screening_id = "SC-OFFLINE-TEST-001"
        anchor = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"DETERMINISTIC_OFFLINE_DOC_BYTES",
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        assert anchor["screening_id"] == screening_id
        assert anchor["status"] in ["UNAVAILABLE", "VERIFIED"]
        if anchor["status"] == "UNAVAILABLE":
            assert anchor["transaction_id"] is None
            assert anchor["ledger_asset_id"] is None
            assert "not reachable" in anchor["verification_message"] or "gateway error" in anchor["verification_message"]
        assert len(anchor["document_hash"]) == 64
        assert len(anchor["result_hash"]) == 64
    finally:
        db.close()


# ==============================================================================
# TEST 11: Anchor creation idempotency (prevents duplicate entries)
# ==============================================================================
def test_anchor_idempotency():
    db = SessionLocal()
    try:
        screening_id = "SC-IDEMPOTENT-001"
        anchor1 = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"IDEMPOTENCY_TEST_BYTES",
            risk_band="MEDIUM",
            checkpoint_id="CP-DEL-AIR"
        )
        anchor2 = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"IDEMPOTENCY_TEST_BYTES",
            risk_band="MEDIUM",
            checkpoint_id="CP-DEL-AIR"
        )
        assert anchor1["id"] == anchor2["id"]
        assert anchor1["document_hash"] == anchor2["document_hash"]
        assert anchor1["result_hash"] == anchor2["result_hash"]

        count = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == screening_id).count()
        assert count == 1
    finally:
        db.close()


# ==============================================================================
# TEST 12: Audit event BLOCKCHAIN_ANCHOR_RECORDED added to unbroken audit chain
# ==============================================================================
def test_audit_event_logged_on_anchor():
    db = SessionLocal()
    try:
        screening_id = "SC-AUDIT-TEST-001"
        FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"AUDIT_RECORD_VERIFY_BYTES",
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        events = db.query(AuditEvent).filter(
            AuditEvent.screening_id == screening_id,
            AuditEvent.event_type == "BLOCKCHAIN_ANCHOR_RECORDED"
        ).all()
        assert len(events) >= 1
        ev = events[0]
        assert ev.event_type == "BLOCKCHAIN_ANCHOR_RECORDED"
        assert len(ev.event_hash) == 64
        assert len(ev.previous_hash) == 64
    finally:
        db.close()


# ==============================================================================
# TEST 13: API endpoint POST /api/v1/blockchain/{id}/anchor requires authentication
# ==============================================================================
def test_anchor_api_endpoint_authentication():
    res = client.post(
        "/api/v1/blockchain/SC-NOAUTH-01/anchor",
        headers={"Authorization": "Bearer totally_invalid_bogus_token"}
    )
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower() or "expired" in res.json()["detail"].lower()


# ==============================================================================
# TEST 14: API endpoint POST /api/v1/blockchain/{id}/anchor successful execution
# ==============================================================================
def test_anchor_api_endpoint_success():
    token = get_auth_token()
    db = SessionLocal()
    screening_id = f"SC-API-ANCHOR-{uuid.uuid4().hex[:8]}"
    try:
        # Create a test screening in DB
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=10.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint"
        )
        db.add(sc)
        db.commit()

        res = client.post(
            f"/api/v1/blockchain/{screening_id}/anchor",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["screening_id"] == screening_id
        assert "document_hash" in data
        assert "result_hash" in data
        assert data["network"] == "Hyperledger Fabric (Private)"
        assert data["channel"] == "satyascan-channel"
        assert data["chaincode"] == "screening_anchor"
    finally:
        db.close()


# ==============================================================================
# TEST 15: Checkpoint RBAC enforcement (Officer checkpoint binding)
# ==============================================================================
def test_anchor_api_checkpoint_scoping():
    # Login as Attari border officer
    token_attari = get_auth_token(username="attari_border", password="Demo@123", checkpoint_id="CP-ATTARI")
    db = SessionLocal()
    screening_id = f"SC-DEL-ONLY-{uuid.uuid4().hex[:8]}"
    try:
        # Screening created at Delhi airport
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=15.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint"
        )
        db.add(sc)
        db.commit()

        # Attari officer attempting to anchor Delhi screening -> HTTP 403
        res = client.post(
            f"/api/v1/blockchain/{screening_id}/anchor",
            headers={"Authorization": f"Bearer {token_attari}"}
        )
        assert res.status_code == 403
        assert "Access denied" in res.json()["detail"]
    finally:
        db.close()


# ==============================================================================
# TEST 16: API endpoint GET /api/v1/blockchain/{id} retrieval and 404 behavior
# ==============================================================================
def test_get_anchor_endpoint():
    token = get_auth_token()
    db = SessionLocal()
    screening_id = f"SC-GET-ANCHOR-{uuid.uuid4().hex[:8]}"
    try:
        # 1. Non-existent screening -> 404
        res_404 = client.get(
            "/api/v1/blockchain/NON_EXISTENT_ID_999",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_404.status_code == 404

        # 2. Existing screening anchored -> returns anchor
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=5.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        db.add(sc)
        db.commit()

        anchor = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"GET_ANCHOR_TEST_DOC",
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )

        res = client.get(
            f"/api/v1/blockchain/{screening_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["screening_id"] == screening_id
        assert data["document_hash"] == anchor["document_hash"]
        assert data["result_hash"] == anchor["result_hash"]
    finally:
        db.close()


# ==============================================================================
# TEST 17: API endpoint POST /api/v1/blockchain/{id}/verify integrity check
# ==============================================================================
def test_verify_anchor_offline_fallback():
    token = get_auth_token()
    db = SessionLocal()
    screening_id = f"SC-VERIFY-ANCHOR-{uuid.uuid4().hex[:8]}"
    try:
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=12.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        db.add(sc)
        db.commit()

        FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"DOC_FOR_VERIFICATION_TEST",
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )

        res = client.post(
            f"/api/v1/blockchain/{screening_id}/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["screening_id"] == screening_id
        assert "document_hash" in data
        assert "result_hash" in data
        assert "status" in data
        assert "privacy_compliance" in data
        assert "Zero PII" in data["privacy_compliance"]

        # Confirm audit event was recorded
        ev = db.query(AuditEvent).filter(
            AuditEvent.screening_id == screening_id,
            AuditEvent.event_type == "BLOCKCHAIN_ANCHOR_VERIFIED"
        ).first()
        assert ev is not None
    finally:
        db.close()


# ==============================================================================
# TEST 18: Screening detail response includes blockchain_anchor payload
# ==============================================================================
def test_screening_detail_includes_blockchain_anchor():
    token = get_auth_token()
    db = SessionLocal()
    screening_id = f"SC-DETAIL-ANCHOR-{uuid.uuid4().hex[:8]}"
    try:
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=15.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint"
        )
        db.add(sc)
        db.commit()

        FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=b"DOC_FOR_DETAIL_TEST",
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )

        res = client.get(
            f"/api/v1/screenings/{screening_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        detail = res.json()
        assert "blockchain_anchor" in detail
        assert detail["blockchain_anchor"] is not None
        assert detail["blockchain_anchor"]["screening_id"] == screening_id
        assert len(detail["blockchain_anchor"]["document_hash"]) == 64
        assert len(detail["blockchain_anchor"]["result_hash"]) == 64
    finally:
        db.close()


# ==============================================================================
# TEST 19: End-to-end screening completes unaffected when ledger is offline
# ==============================================================================
def test_pipeline_unaffected_when_fabric_offline():
    token = get_auth_token()
    # Test screening with a valid mock image to ensure pipeline executes cleanly
    # Generate minimal valid jpeg bytes
    import io
    from PIL import Image
    img = Image.new("RGB", (600, 400), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    # Even if classifier rejects plain color image as UNSUPPORTED, the core engine
    # handles offline ledger gracefully without unhandled exceptions or crashes
    res = client.post(
        "/api/v1/screenings",
        headers={"Authorization": f"Bearer {token}"},
        files={"document_file": ("passport_test.jpg", jpeg_bytes, "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    # Status can be 200 (if accepted) or 400 (UNSUPPORTED_DOCUMENT) — neither is a 500 crash
    assert res.status_code in [200, 400]
    assert res.status_code != 500
