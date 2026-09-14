"""
SatyaScan Unit & Integration Tests: AI / CV Modules
Validates Quality Gate, ICAO 7-3-1 MRZ Checksum Math, VIZ-MRZ Cross-Checks,
ELA Heatmaps, Face Verification, FAISS Duplicate Search, and Risk Engine.
"""

import pytest
import numpy as np
import cv2

from ai.quality.quality_gate import DocumentQualityGate
from ai.mrz.mrz_parser import MRZParser
from ai.tamper.ela import ELAEngine
from ai.tamper.noise_residual import NoiseResidualEngine
from ai.tamper.copy_move import CopyMoveDetector
from ai.face.face_verifier import FaceVerifier
from ai.duplicate.indexer import MultiIdentityIndexer
from ai.risk.risk_engine import RiskEngine


def test_quality_gate_detects_severe_blur():
    qg = DocumentQualityGate()
    # Create sharp image
    sharp = np.zeros((600, 800, 3), dtype=np.uint8)
    cv2.putText(sharp, "PASSPORT REPUBLIC OF INDIA", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
    cv2.rectangle(sharp, (100, 100), (700, 500), (200, 200, 200), 2)
    res_sharp = qg.assess_image(sharp)

    # Create heavily blurred image
    blurred = cv2.GaussianBlur(sharp, (51, 51), 0)
    res_blurred = qg.assess_image(blurred)

    assert res_blurred["metrics"]["blur_score"] < res_sharp["metrics"]["blur_score"]
    assert res_blurred["verdict"] == "NEEDS_BETTER_IMAGE"
    assert any("blur" in r.lower() for r in res_blurred["reasons"])


def test_mrz_7_3_1_checksum_algorithm():
    # Known ICAO standard test cases
    # 1. Document number 'L898902C3' -> expected check digit 6
    doc_num = "L898902C3"
    assert MRZParser.calculate_check_digit(doc_num) == "6"

    # 2. Date of birth '740812' -> expected check digit 2
    dob = "740812"
    assert MRZParser.calculate_check_digit(dob) == "2"

    # 3. Expiry date '120415' -> expected check digit 9
    exp = "120415"
    assert MRZParser.calculate_check_digit(exp) == "9"


def test_mrz_full_td3_parsing_and_tamper_detection():
    # Valid TD3 sample
    l1 = "P<INDCARLSON<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<"
    # Z1234567< check digit is 1, 900101 is 1, 300101 is 9, composite is 4
    l2_valid = "Z1234567<1IND9001011M3001019<<<<<<<<<<<<<<<4"
    res_valid = MRZParser.parse_td3(l1, l2_valid)

    assert res_valid["parsed"] is True
    assert res_valid["all_checks_passed"] is True
    assert res_valid["surname"] == "CARLSON"
    assert res_valid["given_names"] == "JOHN"
    assert res_valid["document_number"] == "Z1234567"

    # Alter a single digit in DOB (tampered from 900101 to 900102) without updating check digit
    l2_tampered = "Z1234567<1IND9001021M3001019<<<<<<<<<<<<<<<4"
    res_tampered = MRZParser.parse_td3(l1, l2_tampered)

    assert res_tampered["parsed"] is True
    assert res_tampered["all_checks_passed"] is False
    assert res_tampered["check_digits"]["date_of_birth"]["valid"] is False


def test_viz_mrz_cross_check_flags_dob_manipulation():
    mrz_data = {
        "parsed": True,
        "document_number": "Z1234567",
        "date_of_birth": "1990-01-01",
        "date_of_expiry": "2030-01-01",
        "full_name": "JOHN CARLSON"
    }
    # Visual fields have manipulated DOB (2002-01-01)
    viz_fields = {
        "document_number": "Z1234567",
        "date_of_birth": "01/01/2002",
        "date_of_expiry": "01/01/2030",
        "full_name": "JOHN CARLSON"
    }

    findings = MRZParser.cross_validate_viz(mrz_data, viz_fields)
    dob_findings = [f for f in findings if f["field"] == "date_of_birth"]

    assert len(dob_findings) == 1
    assert dob_findings[0]["severity"] == "CRITICAL"
    assert "differs from MRZ" in dob_findings[0]["message"]


def test_ela_forensic_engine():
    ela = ELAEngine()
    # Uniform synthetic canvas
    img = np.ones((400, 600, 3), dtype=np.uint8) * 220
    # Add a localized high-contrast patch simulating spliced foreign text
    img[100:160, 200:350] = np.random.randint(0, 255, (60, 150, 3), dtype=np.uint8)

    res = ela.analyze(img)
    assert "anomaly_score" in res
    assert "suspicious_regions" in res
    assert res["technique"] == "Error Level Analysis (ELA)"


def test_face_verification_and_appearance_variation():
    verifier = FaceVerifier()
    # Create two identical test crops
    face1 = np.ones((120, 120, 3), dtype=np.uint8) * 180
    cv2.circle(face1, (40, 45), 8, (20, 20, 20), -1)
    cv2.circle(face1, (80, 45), 8, (20, 20, 20), -1)
    cv2.ellipse(face1, (60, 85), (20, 8), 0, 0, 180, (50, 50, 50), -1)

    # Face 2 is same person with beard added in lower third
    face2 = face1.copy()
    cv2.ellipse(face2, (60, 90), (35, 25), 0, 0, 180, (20, 20, 20), -1)

    emb1 = verifier.extract_embedding(face1)
    emb2 = verifier.extract_embedding(face2)

    cosine_sim = float(np.dot(emb1, emb2))
    assert cosine_sim > 0.60  # Still high biometric similarity

    app_diff = verifier.analyze_appearance_differences(face1, face2)
    assert app_diff["appearance_difference_level"] in ["MODERATE", "SIGNIFICANT"]
    assert any("facial hair" in o.lower() for o in app_diff["observations"])


def test_faiss_multi_identity_duplicate_search():
    indexer = MultiIdentityIndexer(embedding_dim=512)
    rng = np.random.RandomState(42)

    # Add identity A
    emb_a = rng.randn(512).astype(np.float32)
    emb_a /= np.linalg.norm(emb_a)
    indexer.add_identity("DEMO-001", "ARJUN SHARMA", emb_a)

    # Add identity B with distinct embedding
    emb_b = rng.randn(512).astype(np.float32)
    emb_b /= np.linalg.norm(emb_b)
    indexer.add_identity("DEMO-002", "PRIYA PATEL", emb_b)

    # Query with face identical to Identity A, but presenting under a new document ID 'DEMO-999'
    res = indexer.search_duplicate(query_embedding=emb_a, current_doc_id="DEMO-999")

    assert res["duplicate_detected"] is True
    assert res["primary_alert"]["matched_document_id"] == "DEMO-001"
    assert res["primary_alert"]["matched_name"] == "ARJUN SHARMA"
    assert res["primary_alert"]["similarity"] >= 0.99


def test_risk_engine_calibrated_scoring():
    engine = RiskEngine()

    # Clean low-risk inputs
    q_good = {"verdict": "GOOD", "overall_score": 90.0}
    mrz_good = {
        "parsed": True,
        "all_checks_passed": True,
        "check_digits": {
            "document_number": {"valid": True},
            "date_of_birth": {"valid": True},
            "date_of_expiry": {"valid": True},
            "composite": {"valid": True}
        }
    }
    tamper_clean = {"composite_tamper_score": 10.0, "findings": []}
    face_match = {"verification_result": "MATCH", "similarity_score": 0.88, "appearance_analysis": {"appearance_difference_level": "MINIMAL"}}

    low_risk = engine.compute_risk(
        quality_res=q_good,
        mrz_res=mrz_good,
        viz_mrz_findings=[],
        rule_findings=[],
        tamper_res=tamper_clean,
        face_res=face_match
    )
    assert low_risk["risk_band"] == "LOW"
    assert low_risk["risk_score"] < 30.0

    # Tampered high-risk inputs (critical MRZ mismatch + ELA anomaly + Face mismatch)
    viz_mismatch = [{
        "field": "date_of_birth",
        "severity": "CRITICAL",
        "message": "Visual DOB does not match MRZ DOB."
    }]
    tamper_high = {
        "composite_tamper_score": 75.0,
        "findings": [{"technique": "ELA", "severity": "HIGH", "score": 75.0, "summary": "Compression Anomaly"}]
    }
    face_mismatch = {"verification_result": "MISMATCH", "similarity_score": 0.32}

    high_risk = engine.compute_risk(
        quality_res=q_good,
        mrz_res=mrz_good,
        viz_mrz_findings=viz_mismatch,
        rule_findings=[],
        tamper_res=tamper_high,
        face_res=face_mismatch
    )
    assert high_risk["risk_band"] in ["HIGH", "CRITICAL"]
    assert high_risk["risk_score"] >= 60.0
    assert len(high_risk["reasons"]) >= 2
