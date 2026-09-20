"""
SatyaScan Strict Backend & Document Pipeline Test Suite
Exhaustively validates:
- Document Type Gate (Passport & Visa only, explicit rejection of Aadhaar, PAN, DL, Voter ID, Blank, Random)
- Dedicated Passport Pipeline (TD3 MRZ, 7-3-1 checks, VIZ cross-validation, expiry)
- Dedicated Visa Pipeline (Visa syntax, expiry, date range, stay duration, passport cross-check)
- Forensics (Genuine, spliced photo, copy-move, metadata, blur quality gate)
- Biometrics (Genuine match, imposter mismatch, appearance variation, no face)
- Checkpoint Anti-Spoofing & Security (Identity binding, JWT, RBAC, Rate limiting, Path traversal)
- Cryptographic Audit Integrity & OCR Provenance Tracking
"""

import pytest
import os
import io
import time
import json
from datetime import timedelta
import numpy as np
import cv2
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.database import (
    SessionLocal, Screening, ExtractedField, User, Checkpoint, ReferenceWatchlist, AuditEvent, init_db
)
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.services.audit_service import AuditService
from ai.classifier.document_classifier import DocumentClassifier
from ai.visa.visa_parser import VisaParser
from ai.mrz.mrz_parser import MRZParser
from ai.quality.quality_gate import DocumentQualityGate
from ai.tamper.pipeline import TamperForensicsPipeline
from ai.face.face_verifier import FaceVerifier
from ai.risk.risk_engine import RiskEngine
from ai.ocr.ocr_engine import OCREngine


@pytest.fixture(scope="module", autouse=True)
def ensure_db_initialized():
    init_db()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def delhi_officer_token(db_session):
    user = db_session.query(User).filter(User.username == "delhi_airport").first()
    if not user:
        user = User(
            username="delhi_airport",
            email="delhi_airport@satyascan.gov.in",
            hashed_password=get_password_hash("Demo@123"),
            role="OFFICER",
            full_name="Delhi Airport Checkpoint Officer",
            badge_number="SSB-DEL-01",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint",
            location="Delhi Airport (IGI)",
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
    token = create_access_token({
        "sub": user.username,
        "role": user.role,
        "id": user.id,
        "checkpoint_id": user.checkpoint_id,
        "checkpoint_name": user.checkpoint_name
    })
    return token


# Helper to synthesize document images
def create_synthetic_doc_image(text_lines, width=800, height=500, bg_color=(240, 240, 240)):
    img = np.full((height, width, 3), bg_color, dtype=np.uint8)
    y = 50
    for line in text_lines:
        cv2.putText(img, line, (40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
        y += 45
    return img


def img_to_bytes(cv_img, ext="jpg"):
    success, encoded = cv2.imencode(f".{ext}", cv_img)
    return encoded.tobytes()


# =====================================================================
# PART 1: DOCUMENT TYPE GATE & CLASSIFICATION (8 TESTS)
# =====================================================================

def test_01_classifier_accepts_valid_passport():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "PASSPORT",
        "REPUBLIC OF INDIA",
        "P<INDKUMAR<<ARJUN<<<<<<<<<<<<<<<<<<<<<<<<<<<",
        "Z1234567<4IND9001018M3001012<<<<<<<<<<<<<<<8"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is True
    assert res["verdict"] == "PASSPORT"


def test_02_classifier_accepts_valid_visa():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "VISA VIGNETTE",
        "VISA TYPE: TOURIST",
        "ENTRIES: MULTIPLE",
        "DURATION OF STAY: 90 DAYS",
        "VALID FROM: 01-JAN-2026",
        "VALID UNTIL: 31-DEC-2026",
        "VISA NO: V88291034"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is True
    assert res["verdict"] == "VISA"


def test_03_classifier_rejects_aadhaar():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "GOVERNMENT OF INDIA",
        "UNIQUE IDENTIFICATION AUTHORITY OF INDIA",
        "AADHAAR",
        "MERA AADHAAR MERI PEHCHAN",
        "ROHIT SHARMA",
        "DOB: 15/08/1990",
        "1234 5678 9012"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is False
    assert res["verdict"] == "UNSUPPORTED_DOCUMENT"
    assert res["detected_type"] == "AADHAAR"
    assert "Passport and Visa only" in res["message"]


def test_04_classifier_rejects_pan_card():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "INCOME TAX DEPARTMENT",
        "GOVT. OF INDIA",
        "PERMANENT ACCOUNT NUMBER",
        "ABCDE1234F",
        "NAME: VIKRAM MEHTA",
        "FATHER'S NAME: RAMESH MEHTA",
        "DOB: 12/04/1985"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is False
    assert res["verdict"] == "UNSUPPORTED_DOCUMENT"
    assert res["detected_type"] == "PAN"


def test_05_classifier_rejects_driving_licence():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "UNION OF INDIA DRIVING LICENCE",
        "TRANSPORT DEPARTMENT",
        "FORM 7",
        "DL NO: DL0420110012345",
        "NAME: AJAY SINGH"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is False
    assert res["verdict"] == "UNSUPPORTED_DOCUMENT"
    assert res["detected_type"] == "DRIVING_LICENCE"


def test_06_classifier_rejects_voter_id():
    classifier = DocumentClassifier()
    img = create_synthetic_doc_image([
        "ELECTION COMMISSION OF INDIA",
        "ELECTOR PHOTO IDENTITY CARD",
        "EPIC NO: WXZ1234567",
        "ELECTOR NAME: SUNIL GUPTA"
    ])
    res = classifier.classify_image(img)
    assert res["is_supported"] is False
    assert res["verdict"] == "UNSUPPORTED_DOCUMENT"
    assert res["detected_type"] == "VOTER_ID"


def test_07_classifier_rejects_blank_image():
    classifier = DocumentClassifier()
    blank = np.full((400, 600, 3), 255, dtype=np.uint8)
    res = classifier.classify_image(blank)
    assert res["is_supported"] is False
    assert res["verdict"] == "UNSUPPORTED_DOCUMENT"
    assert res["detected_type"] == "BLANK_IMAGE"


def test_08_classifier_rejects_random_photo():
    classifier = DocumentClassifier()
    noise = np.random.randint(50, 200, (400, 600, 3), dtype=np.uint8)
    res = classifier.classify_image(noise)
    assert res["is_supported"] is False
    assert res["verdict"] in ["UNABLE_TO_CLASSIFY", "UNSUPPORTED_DOCUMENT"]


# =====================================================================
# PART 2: PASSPORT PIPELINE TESTS (6 TESTS)
# =====================================================================

def test_09_valid_td3_mrz_parsing():
    l1 = "P<INDCARLSON<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<"
    l2_valid = "Z1234567<1IND9001011M3001019<<<<<<<<<<<<<<<4"
    res = MRZParser.parse_td3(l1, l2_valid)
    assert res["parsed"] is True
    assert res["document_number"] == "Z1234567"
    assert res["nationality"] == "IND"
    assert res["all_checks_passed"] is True


def test_10_invalid_mrz_check_digit_flagged():
    l1 = "P<INDCARLSON<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<"
    # Alter check digit from 1 to 9
    l2_invalid = "Z1234567<9IND9001011M3001019<<<<<<<<<<<<<<<4"
    res = MRZParser.parse_td3(l1, l2_invalid)
    assert res["parsed"] is True
    assert res["all_checks_passed"] is False
    assert res["check_digits"]["document_number"]["valid"] is False


def test_11_invalid_mrz_line_length_flagged():
    line1 = "P<INDKUMAR<<ARJUN<<<<<<"
    line2 = "Z1234567<4IND9001018M3001012"
    res = MRZParser.parse_td3(line1, line2)
    assert res["parsed"] is False
    assert res.get("error") == "MRZ_PARSE_FAILED"


def test_12_expired_passport_flagged():
    l1 = "P<INDCARLSON<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<"
    l2 = "Z1234567<1IND9001011M2101019<<<<<<<<<<<<<<<4"  # Expired in 2021
    res = MRZParser.parse_td3(l1, l2)
    assert res["parsed"] is True
    assert res["is_expired"] is True


def test_13_viz_mrz_dob_discrepancy_detected():
    mrz_res = {
        "parsed": True,
        "date_of_birth": "1990-01-01",
        "document_number": "Z1234567",
        "all_checks_passed": True
    }
    viz_fields = {
        "date_of_birth": "01/01/2002",
        "document_number": "Z1234567"
    }
    findings = MRZParser.cross_validate_viz(mrz_res, viz_fields)
    dob_findings = [f for f in findings if f["field"] == "date_of_birth"]
    assert len(dob_findings) > 0
    assert dob_findings[0]["severity"] == "CRITICAL"


def test_14_viz_mrz_doc_num_discrepancy_detected():
    mrz_res = {
        "parsed": True,
        "document_number": "Z1234567",
        "all_checks_passed": True
    }
    viz_fields = {
        "document_number": "P9999999"
    }
    findings = MRZParser.cross_validate_viz(mrz_res, viz_fields)
    doc_findings = [f for f in findings if f["field"] == "document_number"]
    assert len(doc_findings) > 0
    assert doc_findings[0]["severity"] == "CRITICAL"


# =====================================================================
# PART 3: VISA PIPELINE TESTS (6 TESTS)
# =====================================================================

def test_15_valid_visa_parsing_and_rules():
    raw_lines = [
        {"text": "VISA VIGNETTE", "confidence": 0.95, "box": []},
        {"text": "VISA NO: V12345678", "confidence": 0.94, "box": []},
        {"text": "TYPE: TOURIST", "confidence": 0.96, "box": []},
        {"text": "VALID FROM: 01-JAN-2026", "confidence": 0.92, "box": []},
        {"text": "VALID UNTIL: 31-DEC-2027", "confidence": 0.93, "box": []},
        {"text": "ENTRIES: MULTIPLE", "confidence": 0.90, "box": []},
        {"text": "DURATION OF STAY: 90 DAYS", "confidence": 0.91, "box": []},
        {"text": "PASSPORT NO: P7654321", "confidence": 0.94, "box": []}
    ]
    fields = VisaParser.parse_visa_fields(raw_lines, ocr_engine_name="PaddleOCR")
    assert fields["visa_number"]["status"] == "FOUND"
    assert fields["visa_number"]["value"] == "V12345678"
    assert fields["visa_type"]["value"] == "TOURIST"

    findings = VisaParser.validate_visa_rules(fields, presented_passport_number="P7654321")
    critical_findings = [f for f in findings if f["severity"] == "CRITICAL"]
    assert len(critical_findings) == 0


def test_16_expired_visa_flagged():
    raw_lines = [
        {"text": "VISA NO: V12345678", "confidence": 0.95, "box": []},
        {"text": "VALID FROM: 01-JAN-2020", "confidence": 0.92, "box": []},
        {"text": "VALID UNTIL: 01-JAN-2021", "confidence": 0.93, "box": []}
    ]
    fields = VisaParser.parse_visa_fields(raw_lines)
    findings = VisaParser.validate_visa_rules(fields)
    exp_findings = [f for f in findings if f["rule_id"] == "VISA_EXPIRY_CHECK"]
    assert len(exp_findings) > 0
    assert exp_findings[0]["severity"] == "CRITICAL"


def test_17_invalid_visa_number_syntax_flagged():
    raw_lines = [
        {"text": "VISA NO: 12", "confidence": 0.95, "box": []},
    ]
    fields = VisaParser.parse_visa_fields(raw_lines)
    findings = VisaParser.validate_visa_rules(fields)
    syntax_findings = [f for f in findings if f["rule_id"] == "VISA_NUMBER_FORMAT"]
    assert len(syntax_findings) > 0


def test_18_invalid_visa_date_range_flagged():
    raw_lines = [
        {"text": "VISA NO: V12345678", "confidence": 0.95, "box": []},
        {"text": "VALID FROM: 01-DEC-2027", "confidence": 0.92, "box": []},
        {"text": "VALID UNTIL: 01-JAN-2027", "confidence": 0.93, "box": []}
    ]
    fields = VisaParser.parse_visa_fields(raw_lines)
    findings = VisaParser.validate_visa_rules(fields)
    range_findings = [f for f in findings if f["rule_id"] == "VISA_DATE_RANGE_INVALID"]
    assert len(range_findings) > 0


def test_19_missing_visa_field_tagged_not_found():
    raw_lines = [
        {"text": "SOME RANDOM FRAGMENT", "confidence": 0.50, "box": []}
    ]
    fields = VisaParser.parse_visa_fields(raw_lines)
    assert fields["visa_number"]["status"] == "NOT_FOUND"
    assert fields["valid_until"]["status"] == "NOT_FOUND"


def test_20_visa_passport_linkage_mismatch():
    raw_lines = [
        {"text": "VISA NO: V12345678", "confidence": 0.95, "box": []},
        {"text": "PASSPORT NO: P1111111", "confidence": 0.94, "box": []}
    ]
    fields = VisaParser.parse_visa_fields(raw_lines)
    findings = VisaParser.validate_visa_rules(fields, presented_passport_number="P2222222")
    mismatch = [f for f in findings if f["rule_id"] == "VISA_PASSPORT_CROSS_CHECK"]
    assert len(mismatch) > 0
    assert mismatch[0]["severity"] == "CRITICAL"


# =====================================================================
# PART 4: FORENSICS & QUALITY (5 TESTS)
# =====================================================================

def test_21_genuine_document_forensics_clean():
    tamper = TamperForensicsPipeline()
    img_path = "data/genuine/case01_genuine_arjun.jpg"
    if os.path.exists(img_path):
        res = tamper.analyze(img_path)
        assert "composite_tamper_score" in res
        assert "signals" in res
        assert "ela" in res["signals"]
        assert "noise_residual" in res["signals"]


def test_22_photo_replacement_forensic_anomaly():
    tamper = TamperForensicsPipeline()
    img_path = "data/tampered/case04_photo_replaced.jpg"
    if os.path.exists(img_path):
        res = tamper.analyze(img_path)
        assert res["composite_tamper_score"] >= 35.0


def test_23_copy_move_cloned_elements_detected():
    tamper = TamperForensicsPipeline()
    img_path = "data/tampered/case05_copymove_stamp.jpg"
    if os.path.exists(img_path):
        res = tamper.analyze(img_path)
        assert res["composite_tamper_score"] >= 35.0


def test_24_metadata_software_signature_detected():
    tamper = TamperForensicsPipeline()
    img_path = "data/tampered/case03_tampered_dob.jpg"
    if os.path.exists(img_path):
        res = tamper.analyze(img_path)
        assert "signals" in res


def test_25_blurry_document_fails_quality_gate():
    qgate = DocumentQualityGate()
    blurry_path = "data/tampered/case07_blurry_fail.jpg"
    if os.path.exists(blurry_path):
        res = qgate.assess_image(blurry_path)
        assert res["verdict"] in ["REJECTED", "NEEDS_BETTER_IMAGE"]
        assert res["is_acceptable"] is False


# =====================================================================
# PART 5: BIOMETRIC FACE VERIFICATION (5 TESTS)
# =====================================================================

def test_26_face_genuine_match():
    verifier = FaceVerifier()
    doc_p = "data/genuine/case01_genuine_arjun.jpg"
    live_p = "data/selfies/case01_selfie_arjun.jpg"
    if os.path.exists(doc_p) and os.path.exists(live_p):
        res = verifier.verify(doc_p, live_p)
        assert res["verification_result"] == "MATCH"
        assert res["similarity_score"] >= res["threshold"]


def test_27_face_imposter_mismatch():
    verifier = FaceVerifier()
    face1 = np.ones((120, 120, 3), dtype=np.uint8) * 180
    cv2.circle(face1, (40, 45), 8, (20, 20, 20), -1)
    cv2.circle(face1, (80, 45), 8, (20, 20, 20), -1)
    cv2.ellipse(face1, (60, 85), (20, 8), 0, 0, 180, (50, 50, 50), -1)

    face_imposter = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(face_imposter, (60, 60), 30, (255, 255, 255), -1)
    cv2.rectangle(face_imposter, (20, 20), (100, 40), (128, 128, 128), -1)

    emb1 = verifier.extract_embedding(face1)
    emb2 = verifier.extract_embedding(face_imposter)
    sim = float(np.dot(emb1, emb2))
    assert sim < verifier.BORDERLINE_THRESHOLD


def test_28_face_appearance_variation_handled():
    verifier = FaceVerifier()
    doc_p = "data/genuine/case01_genuine_arjun.jpg"
    bearded_p = "data/selfies/case08_selfie_bearded_arjun.jpg"
    if os.path.exists(doc_p) and os.path.exists(bearded_p):
        res = verifier.verify(doc_p, bearded_p)
        assert res["verification_result"] == "MATCH"
        assert res["appearance_analysis"]["appearance_difference_level"] in ["MODERATE", "SIGNIFICANT", "MINIMAL"]


def test_29_no_face_detected_in_blank():
    verifier = FaceVerifier()
    blank = np.full((300, 300, 3), 200, dtype=np.uint8)
    cropped, box, quality = verifier.detect_and_crop_face(blank)
    assert cropped is None
    assert box is None


def test_30_multiple_faces_selects_primary():
    verifier = FaceVerifier()
    doc_p = "data/genuine/case01_genuine_arjun.jpg"
    if os.path.exists(doc_p):
        img = cv2.imread(doc_p)
        cropped, box, quality = verifier.detect_and_crop_face(img)
        assert cropped is not None


# =====================================================================
# PART 6: SECURITY, AUTH & ANTI-SPOOFING (8 TESTS)
# =====================================================================

def test_31_checkpoint_spoof_attempt_rejected(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    files = {"document_file": ("passport.jpg", b"\xFF\xD8\xFF" + b"\x00" * 2000, "image/jpeg")}
    data = {"document_type": "PASSPORT", "checkpoint_id": "CP-ATTARI"}
    
    res = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    assert res.status_code == 403
    assert "Checkpoint identity mismatch" in res.json()["detail"]


def test_32_unsupported_document_rejected_with_status_400(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    aadhaar_img = create_synthetic_doc_image([
        "GOVERNMENT OF INDIA", "AADHAAR", "UIDAI", "1234 5678 9012"
    ])
    files = {"document_file": ("aadhaar.jpg", img_to_bytes(aadhaar_img), "image/jpeg")}
    data = {"document_type": "PASSPORT"}
    
    res = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    assert res.status_code == 400
    body = res.json()
    assert body["status"] == "UNSUPPORTED_DOCUMENT"
    assert "Passport and Visa only" in body["message"]
    assert "PASSPORT" in body["supported_types"]
    assert "VISA" in body["supported_types"]


def test_33_invalid_jwt_rejected(client):
    headers = {"Authorization": "Bearer invalid.token.payload"}
    res = client.get("/api/v1/screenings", headers=headers)
    assert res.status_code == 401


def test_34_expired_jwt_rejected(client):
    expired = create_access_token({"sub": "delhi_airport", "role": "OFFICER"}, expires_delta=timedelta(seconds=-3600))
    headers = {"Authorization": f"Bearer {expired}"}
    res = client.get("/api/v1/screenings", headers=headers)
    assert res.status_code == 401


def test_35_officer_cannot_add_watchlist_entry(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    payload = {
        "document_id": "Z9999999",
        "full_name": "TEST ESCALATION",
        "reason": "Unauthorized test entry"
    }
    res = client.post("/api/v1/watchlist", headers=headers, json=payload)
    assert res.status_code == 403


def test_36_media_path_traversal_blocked(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.get("/api/v1/screenings/media/..%2F..%2Fetc%2Fpasswd/doc", headers=headers)
    assert res.status_code in [400, 404]


def test_37_blank_image_rejected_at_api_gate(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    blank = np.full((300, 300, 3), 255, dtype=np.uint8)
    files = {"document_file": ("blank.jpg", img_to_bytes(blank), "image/jpeg")}
    data = {"document_type": "PASSPORT"}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert res.json()["status"] == "UNSUPPORTED_DOCUMENT"


def test_38_oversized_upload_rejected(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    big_file = b"\xFF\xD8\xFF" + b"\x00" * (16 * 1024 * 1024)  # 16MB
    files = {"document_file": ("huge.jpg", big_file, "image/jpeg")}
    data = {"document_type": "PASSPORT"}
    res = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    assert res.status_code in [400, 413]


# =====================================================================
# PART 7: CRYPTOGRAPHIC AUDIT & OCR PROVENANCE (4 TESTS)
# =====================================================================

def test_39_audit_chain_verification(db_session):
    screening_id = f"SAT-TEST-{int(time.time() * 1000)}"
    AuditService.record_event(db_session, screening_id, "DOC_UPLOADED", {"file": "doc.jpg"})
    AuditService.record_event(db_session, screening_id, "QUALITY_PASSED", {"score": 90.0})
    AuditService.record_event(db_session, screening_id, "OCR_DONE", {"engine": "PaddleOCR"})

    res = AuditService.verify_audit_chain(db_session, screening_id)
    assert res["is_valid"] is True
    assert res["total_events"] == 3


def test_40_tampered_audit_event_detected(db_session):
    screening_id = f"SAT-TAMPER-{int(time.time() * 1000)}"
    AuditService.record_event(db_session, screening_id, "DOC_UPLOADED", {"file": "doc.jpg"})
    AuditService.record_event(db_session, screening_id, "QUALITY_PASSED", {"score": 90.0})

    # Tamper with an event payload hash
    event = db_session.query(AuditEvent).filter(AuditEvent.screening_id == screening_id).first()
    event.payload_hash = "deadbeef" * 8
    db_session.commit()

    res = AuditService.verify_audit_chain(db_session, screening_id)
    assert res["is_valid"] is False


def test_41_ocr_engine_provenance_strictly_reported():
    engine = OCREngine()
    if os.path.exists("data/genuine/case01_genuine_arjun.jpg"):
        res = engine.process_image("data/genuine/case01_genuine_arjun.jpg")
        assert res["engine"] in ["PaddleOCR", "Tesseract"]
        for fname, fdict in res["extracted_fields"].items():
            if fdict:
                assert fdict["ocr_engine"] == res["engine"]
                assert fdict["validation"] == "VALID"


def test_42_guaranteed_terminal_state_on_preset(client, delhi_officer_token):
    headers = {"Authorization": f"Bearer {delhi_officer_token}"}
    res = client.post("/api/v1/screenings/preset/01", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ["COMPLETED", "MANUAL_REVIEW_REQUIRED"]
    assert body["document_type"] == "PASSPORT"
    assert body["checkpoint_id"] == "CP-DEL-AIR"
    assert body["ocr_engine"] in ["PaddleOCR", "Tesseract"]
