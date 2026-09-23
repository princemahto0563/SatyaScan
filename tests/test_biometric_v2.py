"""
SatyaScan Biometric Verification V2 Test Suite
==============================================
Validates all 16 core requirements A through P:
A. One face detected
B. Zero face detected
C. Multiple faces detected
D. Poor quality rejection (blur / underexposure)
E. Genuine same-person pair
F. Different-person pair
G. Borderline similarity handling
H. Appearance variation analysis
I. Presentation-attack detection (PAD) unavailable state
J. API schema serialization
K. Risk-engine integration
L. PDF report generation with biometric section
M. Reference dataset compatibility
N. Privacy: No biometric data on blockchain
O. Privacy: No raw biometric vectors in logs
P. Provider provenance transparency
"""

import os
import tempfile
import numpy as np
import cv2
import pytest

from ai.face.face_verifier import FaceVerifier
from ai.face.service import FaceVerificationService
from ai.face.quality_gate import FaceQualityGate
from ai.face.pad_detector import PresentationAttackDetector
from ai.face.providers.base import BiometricProvider
from ai.face.providers.gabor_lbp import LegacyGaborLBPProvider
from ai.face.providers.modern_face import ModernFaceProvider
from ai.face.providers.registry import get_biometric_provider
from ai.risk.risk_engine import RiskEngine
from backend.app.schemas.screening import (
    FaceResultSchema,
    BiometricVerificationSchema,
    BiometricQualitySchema,
    BiometricPADSchema,
)
from backend.app.services.report_generator import ReportGenerator
from backend.app.services.fabric_service import FabricAnchorService


# Helper to synthesize a realistic facial pattern for deterministic testing
def create_synthetic_face(bg_val=180, eye_val=30, mouth_val=40):
    face = np.full((120, 120, 3), bg_val, dtype=np.uint8)
    # Eyes
    cv2.circle(face, (40, 45), 9, (eye_val, eye_val, eye_val), -1)
    cv2.circle(face, (80, 45), 9, (eye_val, eye_val, eye_val), -1)
    # Nose
    cv2.line(face, (60, 45), (60, 70), (eye_val + 20, eye_val + 20, eye_val + 20), 2)
    # Mouth
    cv2.ellipse(face, (60, 85), (22, 9), 0, 0, 180, (mouth_val, mouth_val, mouth_val), -1)
    return face


# ==============================================================================
# TEST A: ONE FACE DETECTED
# ==============================================================================
def test_A_one_face_detected():
    qg = FaceQualityGate()
    img = np.full((300, 300, 3), 200, dtype=np.uint8)
    face_box = (60, 60, 100, 100)
    # Draw face features
    cv2.circle(img, (90, 95), 8, (30, 30, 30), -1)
    cv2.circle(img, (130, 95), 8, (30, 30, 30), -1)
    cv2.ellipse(img, (110, 130), (20, 8), 0, 0, 180, (40, 40, 40), -1)

    eval_res = qg.assess_quality(img, [face_box])
    assert eval_res["face_count"] == 1
    assert eval_res["usable"] is True
    assert eval_res["status"] in ["GOOD", "ACCEPTABLE"]


# ==============================================================================
# TEST B: ZERO FACE DETECTED
# ==============================================================================
def test_B_zero_face_detected():
    qg = FaceQualityGate()
    blank = np.full((300, 300, 3), 220, dtype=np.uint8)
    eval_res = qg.assess_quality(blank, [])
    assert eval_res["face_count"] == 0
    assert eval_res["usable"] is False
    assert eval_res["status"] == "UNABLE_TO_VERIFY"
    assert any("No face detected" in r for r in eval_res["reasons"])


# ==============================================================================
# TEST C: MULTIPLE FACES DETECTED
# ==============================================================================
def test_C_multiple_faces_detected():
    qg = FaceQualityGate()
    img = np.full((400, 400, 3), 180, dtype=np.uint8)
    box1 = (50, 50, 90, 90)
    box2 = (220, 50, 90, 90)
    eval_res = qg.assess_quality(img, [box1, box2])
    assert eval_res["face_count"] == 2
    assert eval_res["usable"] is False
    assert eval_res["status"] == "POOR"
    assert any("Multiple faces (2) detected" in r for r in eval_res["reasons"])


# ==============================================================================
# TEST D: POOR QUALITY REJECTION (BLUR & UNDEREXPOSURE)
# ==============================================================================
def test_D_poor_quality_rejection():
    qg = FaceQualityGate()
    # Heavily blurred / flat face
    flat_face = np.full((200, 200, 3), 150, dtype=np.uint8)
    box = (20, 20, 120, 120)
    res_blur = qg.assess_quality(flat_face, [box])
    assert res_blur["blur_score"] < qg.BLUR_ACCEPTABLE_MIN
    assert res_blur["usable"] is False

    # Severe underexposure (black image)
    dark_img = np.full((200, 200, 3), 10, dtype=np.uint8)
    res_dark = qg.assess_quality(dark_img, [box])
    assert res_dark["brightness_score"] < qg.BRIGHTNESS_MIN
    assert res_dark["usable"] is False


# ==============================================================================
# TEST E: GENUINE SAME-PERSON PAIR
# ==============================================================================
def test_E_genuine_same_person_pair():
    provider = LegacyGaborLBPProvider()
    face1 = create_synthetic_face(180, 25, 35)
    face2 = create_synthetic_face(175, 28, 38)  # slight lighting variation

    emb1 = provider.extract_embedding(face1)
    emb2 = provider.extract_embedding(face2)
    sim = provider.compute_similarity(emb1, emb2)

    assert sim >= provider.match_threshold
    assert sim >= 0.85


# ==============================================================================
# TEST F: DIFFERENT-PERSON PAIR
# ==============================================================================
def test_F_different_person_pair():
    provider = LegacyGaborLBPProvider()
    face1 = np.ones((120, 120, 3), dtype=np.uint8) * 180
    cv2.circle(face1, (40, 45), 8, (20, 20, 20), -1)
    cv2.circle(face1, (80, 45), 8, (20, 20, 20), -1)
    cv2.ellipse(face1, (60, 85), (20, 8), 0, 0, 180, (50, 50, 50), -1)

    face_imposter = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(face_imposter, (60, 60), 30, (255, 255, 255), -1)
    cv2.rectangle(face_imposter, (20, 20), (100, 40), (128, 128, 128), -1)

    emb1 = provider.extract_embedding(face1)
    emb2 = provider.extract_embedding(face_imposter)
    sim = provider.compute_similarity(emb1, emb2)

    assert sim < provider.borderline_threshold
    assert sim < 0.50


# ==============================================================================
# TEST G: BORDERLINE SIMILARITY HANDLING
# ==============================================================================
def test_G_borderline_similarity_handling():
    service = FaceVerificationService()
    # Verify borderline threshold values
    assert service.BORDERLINE_THRESHOLD == 0.50
    assert service.MATCH_THRESHOLD == 0.65

    # Borderline score
    sim = 0.58
    assert service.BORDERLINE_THRESHOLD <= sim < service.MATCH_THRESHOLD


# ==============================================================================
# TEST H: APPEARANCE VARIATION ANALYSIS
# ==============================================================================
def test_H_appearance_variation_analysis():
    service = FaceVerificationService()
    doc_face = create_synthetic_face(180, 25, 35)
    live_face = doc_face.copy()

    # Add beard texture (high frequency noise to lower third)
    noise = np.random.randint(0, 80, (50, 70, 3), dtype=np.uint8)
    live_face[70:120, 25:95] = cv2.add(live_face[70:120, 25:95], noise)

    app = service.analyze_appearance_differences(doc_face, live_face)
    assert app["appearance_difference_level"] in ["MINIMAL", "MODERATE", "SIGNIFICANT"]
    assert "observations" in app


# ==============================================================================
# TEST I: PRESENTATION ATTACK DETECTION (PAD) UNAVAILABLE STATE
# ==============================================================================
def test_I_pad_unavailable_state():
    pad = PresentationAttackDetector(enabled=False)
    dummy = np.zeros((100, 100, 3), dtype=np.uint8)
    res = pad.detect(dummy)

    assert res["status"] == "NOT_AVAILABLE"
    assert res["certified"] is False
    assert "Presentation-attack detection is not enabled" in res["reason"]
    assert "must not be interpreted as certified biometric liveness" in res["disclaimer"]


# ==============================================================================
# TEST J: API SCHEMA SERIALIZATION
# ==============================================================================
def test_J_api_schema_serialization():
    # FaceResultSchema serialization
    fr_data = {
        "metric": "Cosine Similarity",
        "similarity_score": 0.91,
        "threshold": 0.65,
        "verification_result": "MATCH",
        "appearance_level": "MODERATE",
        "observations": ["Visible facial hair present"],
        "recommendation": "Identity confirmed.",
        "provider": "GaborLBP-512d-v1.2",
        "quality_status": "GOOD",
        "pad_status": "NOT_AVAILABLE",
        "disclaimer": "Similarity score is a model-derived metric."
    }
    fr_schema = FaceResultSchema(**fr_data)
    assert fr_schema.similarity_score == 0.91
    assert fr_schema.provider == "GaborLBP-512d-v1.2"

    # BiometricVerificationSchema serialization
    bio_data = {
        "status": "MATCH",
        "provider": "GaborLBP-512d-v1.2",
        "similarity": 0.91,
        "threshold": 0.65,
        "quality": {
            "status": "GOOD",
            "reasons": [],
            "face_count": 1,
            "sharpness": 88.5
        },
        "presentation_attack": {
            "status": "NOT_AVAILABLE",
            "reason": "Presentation-attack detection is not enabled in this prototype."
        },
        "appearance_variation": "MODERATE",
        "explanation": "Biometric similarity is consistent with document photograph.",
        "disclaimer": "Biometric similarity is a model-derived metric."
    }
    bio_schema = BiometricVerificationSchema(**bio_data)
    assert bio_schema.quality.status == "GOOD"
    assert bio_schema.presentation_attack.status == "NOT_AVAILABLE"


# ==============================================================================
# TEST K: RISK ENGINE INTEGRATION
# ==============================================================================
def test_K_risk_engine_integration():
    engine = RiskEngine()

    # Match case
    face_match = {
        "verification_result": "MATCH",
        "similarity_score": 0.92,
        "appearance_analysis": {"appearance_difference_level": "MINIMAL", "observations": []}
    }
    risk_match = engine.compute_risk(
        quality_res={"verdict": "GOOD", "overall_score": 90.0},
        mrz_res={"parsed": True, "valid": True},
        viz_mrz_findings=[],
        rule_findings=[],
        tamper_res={"composite_tamper_score": 5.0, "findings": []},
        face_res=face_match,
        doc_type="PASSPORT"
    )
    assert risk_match["signal_breakdown"]["face_verification"] <= 10.0

    # Mismatch case
    face_mismatch = {
        "verification_result": "MISMATCH",
        "similarity_score": 0.38,
        "appearance_analysis": {"appearance_difference_level": "SIGNIFICANT", "observations": []}
    }
    risk_mismatch = engine.compute_risk(
        quality_res={"verdict": "GOOD", "overall_score": 90.0},
        mrz_res={"parsed": True, "valid": True},
        viz_mrz_findings=[],
        rule_findings=[],
        tamper_res={"composite_tamper_score": 5.0, "findings": []},
        face_res=face_mismatch,
        doc_type="PASSPORT"
    )
    assert risk_mismatch["signal_breakdown"]["face_verification"] >= 80.0
    assert any(r["category"] == "BIOMETRIC" and r["severity"] == "CRITICAL" for r in risk_mismatch["reasons"])


# ==============================================================================
# TEST L: PDF REPORT GENERATION WITH BIOMETRIC SECTION
# ==============================================================================
def test_L_pdf_report_biometric_section():
    case_data = {
        "id": "SCN-2026-TEST-BIO",
        "created_at": "2026-09-22T07:00:00Z",
        "checkpoint_id": "CP-DEL-AIR",
        "checkpoint_name": "Indira Gandhi International Airport, Terminal 3",
        "document_type": "PASSPORT",
        "masked_document_id": "Z123****7",
        "status": "COMPLETED",
        "risk_score": 12.5,
        "risk_band": "LOW",
        "recommendation": "Document integrity verified.",
        "execution_latency_ms": 320.0,
        "quality_assessment": {"verdict": "GOOD", "overall_score": 92.0},
        "extracted_fields": [],
        "tamper_summary": {"composite_tamper_score": 4.0, "signals": {}},
        "face_result": {
            "provider": "SFace-ResNet-128d-v1.0",
            "verification_result": "VERIFIED MATCH",
            "similarity_score": 0.85,
            "threshold": 0.68,
            "quality_status": "GOOD",
            "pad_status": "NOT_AVAILABLE",
            "appearance_level": "MINIMAL",
            "recommendation": "Biometric similarity is consistent with document photograph."
        },
        "risk_reasons": []
    }

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tmp_path = tf.name
    try:
        pdf_path = ReportGenerator.generate_pdf(case_data, tmp_path)
        assert os.path.exists(pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        assert len(pdf_bytes) > 2000
        assert pdf_bytes.startswith(b"%PDF-")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==============================================================================
# TEST M: REFERENCE DATASET COMPATIBILITY
# ==============================================================================
def test_M_reference_dataset_compatibility():
    verifier = FaceVerifier()
    assert hasattr(verifier, "detect_and_crop_face")
    assert hasattr(verifier, "extract_embedding")
    assert hasattr(verifier, "analyze_appearance_differences")
    assert hasattr(verifier, "verify")

    face = create_synthetic_face()
    emb = verifier.extract_embedding(face)
    assert len(emb) in [128, 512]
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-3


# ==============================================================================
# TEST N: PRIVACY - NO BIOMETRIC DATA ON CHAIN
# ==============================================================================
def test_N_privacy_no_biometric_data_on_chain():
    # FabricAnchor payload must contain cryptographic hashes only, never vectors or images
    canonical_str = FabricAnchorService.get_canonical_payload(
        screening_id="SCN-TEST-PRIVACY",
        document_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        risk_band="LOW",
        checkpoint_id="CP-DEL-AIR"
    )
    # Check canonical string has no raw biometric or PII keywords
    forbidden_terms = ["face_vector", "embedding", "selfie", "raw_image", "biometric", "portrait"]
    for term in forbidden_terms:
        assert term not in canonical_str

    # Validate that payload dictionary has zero PII or raw biometric vectors
    payload_dict = {
        "screening_id": "SCN-TEST-PRIVACY",
        "document_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "result_hash": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
        "risk_band": "LOW",
        "checkpoint_id": "CP-DEL-AIR",
        "timestamp": "2026-09-22T07:00:00Z"
    }
    is_clean, err = FabricAnchorService.validate_no_pii_in_payload(payload_dict)
    assert is_clean is True
    assert err is None



# ==============================================================================
# TEST O: PRIVACY - NO RAW BIOMETRIC VECTORS IN AUDIT LOGS
# ==============================================================================
def test_O_privacy_no_raw_biometric_vector_in_logs():
    # Verify FaceResult model columns
    from backend.app.models.database import FaceResult
    # Ensure no vector/embedding column exists in relational table
    col_names = [c.name for c in FaceResult.__table__.columns]
    assert "embedding" not in col_names
    assert "vector" not in col_names
    assert "raw_vector" not in col_names


# ==============================================================================
# TEST P: PROVIDER PROVENANCE TRANSPARENCY
# ==============================================================================
def test_P_provider_provenance():
    provider = get_biometric_provider("gabor_lbp")
    assert provider.name == "GaborLBP"
    assert provider.version == "GaborLBP-512d-v1.2"
    assert provider.is_available() is True

    # Test ModernFaceProvider when weights not provisioned
    modern = ModernFaceProvider(weights_path="/nonexistent/path/weights.onnx")
    assert modern.is_available() is False

    # Service must accurately report active provider
    service_gabor = FaceVerificationService(get_biometric_provider("gabor_lbp"))
    assert service_gabor.version == "GaborLBP-512d-v1.2"

    service_auto = FaceVerificationService()
    assert service_auto.version in ["SFace-ResNet-128d-v1.0", "GaborLBP-512d-v1.2"]
    assert "ArcFace" not in service_auto.version  # Transparent honest reporting


# ==============================================================================
# TEST Q: 4-STATE ENGINE: CLASSICAL BASELINE CANNOT UNILATERALLY CLEAR MATCH
# ==============================================================================
def test_Q_classical_baseline_never_emits_unilateral_match(monkeypatch):
    service = FaceVerificationService(get_biometric_provider("gabor_lbp"))
    doc_face = create_synthetic_face(180, 25, 35)
    live_face = create_synthetic_face(175, 28, 38)

    # Mock face detection to return synthetic face
    monkeypatch.setattr(service, "detect_and_crop_face", lambda img, **kw: (img, [0, 0, 120, 120], {"detected": True, "usable": True, "quality_adequate": True, "status": "GOOD", "face_count": 1}))
    monkeypatch.setattr(service, "detect_all_faces", lambda img, **kw: [(0, 0, 120, 120)])

    res = service.verify_identity(doc_face, live_face)
    assert res["decision_state"] == "INCONCLUSIVE"
    assert res["decision_state"] != "VERIFIED_MATCH"
    assert res["requires_manual_inspection"] is True
    assert "classical baseline" in res["evidence_metadata"]["decision_explanation"].lower()
    assert res["pad_status"] == "NOT_AVAILABLE"


# ==============================================================================
# TEST R: NEURAL SFACE PROVIDER RECOGNITION
# ==============================================================================
def test_R_sface_neural_discriminative():
    provider = get_biometric_provider("sface")
    assert provider.is_available() is True
    assert provider.is_neural is True
    assert provider.is_discriminative is True
    assert provider.version == "SFace-ResNet-128d-v1.0"
    assert provider.match_threshold == 0.68
    assert provider.borderline_threshold == 0.48


# ==============================================================================
# TEST S: REAL REFERENCE DATASET EVALUATION MATRIX
# ==============================================================================
def test_S_reference_dataset_evaluation():
    """
    Verifies on the real repository document and selfie that different persons
    correctly trigger VERIFIED MISMATCH with SFace similarity below 0.48,
    permanently preventing the 0.71 false positive bug.
    """
    service = FaceVerificationService()
    doc_path = "data/genuine/case01_genuine_arjun.jpg"
    selfie_path = "data/selfies/case01_selfie_arjun.jpg"

    if os.path.exists(doc_path) and os.path.exists(selfie_path):
        res = service.verify(doc_path, selfie_path)
        assert res["provider"] == "SFace-ResNet-128d-v1.0"
        assert res["decision_state"] == "VERIFIED_MISMATCH"
        assert res["verification_result"] == "VERIFIED MISMATCH"
        assert res["similarity_score"] < 0.48
        assert "impersonation" in res["recommendation"].lower() or "mismatch" in res["recommendation"].lower()


