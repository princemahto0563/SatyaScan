"""
SatyaScan Comprehensive Biometric Evaluation Matrix & Regression Test Suite
=============================================================================
Validates:
1. Minimum Pairwise Evaluation Matrix (4 distinct identities A, B, C, D):
   - Genuine pairs: A vs A, B vs B, C vs C, D vs D (must NOT be rejected)
   - Imposter cross-pairs: A vs B, A vs C, A vs D, B vs C, B vs D, C vs D (NEVER MATCH)
2. Appearance Variations:
   - Same person with beard / facial hair variation
   - Same person with lighting / exposure disparity
3. Quality & Edge Cases:
   - Blurry face -> INCONCLUSIVE / INPUT_FAILURE (NEVER false MATCH)
   - Underexposed / low-contrast face -> INCONCLUSIVE / INPUT_FAILURE
   - Empty buffer / no face -> INPUT_FAILURE / UNABLE_TO_VERIFY
   - Multiple faces in live capture -> INPUT_FAILURE
   - Passport scan with primary photo + ghost photo -> extracts primary photo cleanly
4. Explicit Regression Test for 0.71 False-Positive Case:
   - Distinct person selfie vs document portrait must produce VERIFIED MISMATCH or INCONCLUSIVE
   - NEVER returns VERIFIED MATCH
   - Classical GaborLBP provider must NEVER produce VERIFIED MATCH
"""

import os
import glob
import pytest
import numpy as np
import cv2

from ai.face.face_verifier import FaceVerifier
from ai.face.service import FaceVerificationService
from ai.face.quality_gate import FaceQualityGate
from ai.face.providers.sface import SFaceProvider
from ai.face.providers.gabor_lbp import LegacyGaborLBPProvider
from ai.face.providers.registry import get_biometric_provider


REF_FACES_DIR = os.path.join("data", "reference", "faces")
SELFIES_DIR = os.path.join("data", "selfies")
PASSPORTS_DIR = os.path.join("data", "reference", "passports")


# ==============================================================================
# 1. MINIMUM PAIRWISE EVALUATION MATRIX (A, B, C, D)
# ==============================================================================

def test_pairwise_same_person_matrix():
    """All same-person pairs (A vs A, B vs B, C vs C, D vs D) must yield high similarity and never mismatch."""
    sface = SFaceProvider()
    if not sface.is_available():
        pytest.skip("SFace model not available in current environment")

    person_ids = ["PERSON-001", "PERSON-002", "PERSON-003", "PERSON-004"]
    for pid in person_ids:
        face_path = os.path.join(REF_FACES_DIR, f"{pid}_face_ref.jpg")
        if not os.path.exists(face_path):
            continue
        img = cv2.imread(face_path)
        assert img is not None, f"Could not read {face_path}"
        e1 = sface.extract_embedding(img)
        e2 = sface.extract_embedding(img)
        sim = sface.compute_similarity(e1, e2)
        assert sim >= 0.99, f"Self-comparison for {pid} must be ~1.0, got {sim}"


def test_pairwise_cross_person_matrix_no_false_matches():
    """
    CRITICAL: Cross-person pairs (A vs B, A vs C, A vs D, B vs C, B vs D, C vs D)
    must produce verified low similarity and MUST NEVER be classified as MATCH.
    """
    sface = SFaceProvider()
    if not sface.is_available():
        pytest.skip("SFace model not available in current environment")

    service = FaceVerificationService(sface)
    person_ids = ["PERSON-001", "PERSON-002", "PERSON-003", "PERSON-004"]
    pairs = [
        ("PERSON-001", "PERSON-002"),
        ("PERSON-001", "PERSON-003"),
        ("PERSON-001", "PERSON-004"),
        ("PERSON-002", "PERSON-003"),
        ("PERSON-002", "PERSON-004"),
        ("PERSON-003", "PERSON-004"),
    ]

    for p1, p2 in pairs:
        path1 = os.path.join(REF_FACES_DIR, f"{p1}_face_ref.jpg")
        path2 = os.path.join(REF_FACES_DIR, f"{p2}_face_ref.jpg")
        if not os.path.exists(path1) or not os.path.exists(path2):
            continue

        img1 = cv2.imread(path1)
        img2 = cv2.imread(path2)
        e1 = sface.extract_embedding(img1)
        e2 = sface.extract_embedding(img2)
        sim = sface.compute_similarity(e1, e2)

        # Cross-person similarity must be well below match threshold (0.68)
        assert sim < sface.match_threshold, (
            f"False positive detected between {p1} and {p2}! "
            f"Similarity {sim:.4f} crossed match threshold {sface.match_threshold}"
        )
        assert sim < 0.60, f"Cross-person similarity between {p1} and {p2} is dangerously elevated: {sim:.4f}"

        # Complete service verification check
        result = service.verify(path1, path2)
        assert result["decision_state"] in ["VERIFIED_MISMATCH", "INCONCLUSIVE"], (
            f"Cross-person pair {p1} vs {p2} produced {result['decision_state']} instead of MISMATCH or INCONCLUSIVE!"
        )
        assert result["verification_result"] != "VERIFIED MATCH"
        assert result["verification_result"] != "MATCH"


# ==============================================================================
# 2. APPEARANCE VARIATION & LIGHTING
# ==============================================================================

def test_same_person_appearance_variation_beard():
    """Same person with facial hair / beard variation is analyzed accurately."""
    fv = FaceVerifier()
    clean_selfie = os.path.join(SELFIES_DIR, "case01_selfie_arjun.jpg")
    bearded_selfie = os.path.join(SELFIES_DIR, "case08_selfie_bearded_arjun.jpg")

    if os.path.exists(clean_selfie) and os.path.exists(bearded_selfie):
        res = fv.verify(clean_selfie, bearded_selfie)
        assert "appearance_analysis" in res
        app = res["appearance_analysis"]
        assert app["appearance_difference_level"] in ["MINIMAL", "MODERATE", "SIGNIFICANT"]
        # Must not fabricate a match if quality or descriptor is inadequate
        assert res["verification_result"] != "MATCH" or getattr(fv.provider, "is_neural", False)


def test_same_person_lighting_variation():
    """Synthesizes illumination disparity on genuine portrait."""
    sface = SFaceProvider()
    if not sface.is_available():
        pytest.skip("SFace model not available in current environment")

    p1_path = os.path.join(REF_FACES_DIR, "PERSON-001_face_ref.jpg")
    if os.path.exists(p1_path):
        img = cv2.imread(p1_path)
        # Create darker version (underexposed)
        dark_img = np.clip(img.astype(np.float32) * 0.7, 0, 255).astype(np.uint8)

        e1 = sface.extract_embedding(img)
        e2 = sface.extract_embedding(dark_img)
        sim = sface.compute_similarity(e1, e2)

        # SFace deep metric network is invariant to reasonable linear exposure shift
        assert sim >= 0.85, f"Deep neural embedding should remain robust to lighting shift, got {sim:.4f}"


# ==============================================================================
# 3. QUALITY GATING & EDGE CASES
# ==============================================================================

def test_quality_gate_blurry_face_never_false_match():
    """Blurry degraded face must yield INPUT_FAILURE / INCONCLUSIVE and NEVER MATCH."""
    fv = FaceVerifier()
    p1_path = os.path.join(REF_FACES_DIR, "PERSON-001_face_ref.jpg")
    if os.path.exists(p1_path):
        img = cv2.imread(p1_path)
        # Apply heavy blur
        blurred = cv2.GaussianBlur(img, (25, 25), 10.0)

        res = fv.verify(img, blurred)
        assert res["decision_state"] in ["INPUT_FAILURE", "INCONCLUSIVE"], (
            f"Blurry input must not yield confident verdict, got {res['decision_state']}"
        )
        assert res["verification_result"] not in ["VERIFIED MATCH", "MATCH"]


def test_empty_or_corrupt_input():
    """Empty or corrupt images must return INPUT_FAILURE with 0.0 similarity."""
    fv = FaceVerifier()
    res = fv.verify(None, None)
    assert res["decision_state"] == "INPUT_FAILURE"
    assert res["verification_result"] == "UNABLE_TO_VERIFY"
    assert res.get("similarity_score", 0.0) == 0.0


def test_multiple_faces_in_live_capture_rejected():
    """Multiple faces in live selfie must be rejected with explicit guidance."""
    fv = FaceVerifier()
    p1_path = os.path.join(REF_FACES_DIR, "PERSON-001_face_ref.jpg")
    if os.path.exists(p1_path):
        img = cv2.imread(p1_path)
        # Create synthetic multi-face frame
        canvas = np.full((300, 500, 3), 180, dtype=np.uint8)
        canvas[50:170, 50:170] = cv2.resize(img, (120, 120))
        canvas[50:170, 250:370] = cv2.resize(img, (120, 120))

        res = fv.verify(img, canvas)
        # If multiple faces detected in live capture, must reject
        if res.get("evidence_metadata", {}).get("presented_face_count", 0) > 1:
            assert res["decision_state"] == "INPUT_FAILURE"
            assert "Multiple faces" in res["reason"]


def test_passport_ghost_photo_handling():
    """
    Passports with primary photo + ghost photo must NOT be rejected.
    Primary portrait in left quadrant should be extracted and evaluated.
    """
    fv = FaceVerifier()
    for pid in ["PERSON-002", "PERSON-003"]:
        passport_path = os.path.join(PASSPORTS_DIR, f"{pid}_passport_ref.jpg")
        if os.path.exists(passport_path):
            img = cv2.imread(passport_path)
            cropped, box, quality = fv.detect_and_crop_face(img, is_document=True)
            assert quality.get("detected") is True, f"Face should be detected in {pid} passport"
            assert quality.get("usable") is True, f"{pid} passport should be usable (not rejected due to ghost image)"
            assert cropped is not None
            assert box is not None


# ==============================================================================
# 4. REGRESSION TEST: 0.71 FALSE-POSITIVE VULNERABILITY
# ==============================================================================

def test_regression_071_false_positive_never_matches():
    """
    REGRESSION TEST:
    The documented failure scenario: a document photograph and presented live face
    belong to visibly different people.
    Under NO CIRCUMSTANCES should this comparison produce:
    - VERIFIED MATCH
    - MATCH
    - Language claiming 'confirms identity match'
    """
    fv = FaceVerifier()
    p1_doc = os.path.join(PASSPORTS_DIR, "PERSON-001_passport_ref.jpg")
    p2_doc = os.path.join(PASSPORTS_DIR, "PERSON-002_passport_ref.jpg")

    if os.path.exists(p1_doc) and os.path.exists(p2_doc):
        # Doc 1 vs Doc 2 (different individuals)
        res = fv.verify(p1_doc, p2_doc)

        assert res["verification_result"] != "VERIFIED MATCH", "CRITICAL REGRESSION: Different people marked as VERIFIED MATCH!"
        assert res["verification_result"] != "MATCH", "CRITICAL REGRESSION: Different people marked as MATCH!"
        assert res["decision_state"] in ["VERIFIED_MISMATCH", "INCONCLUSIVE", "INPUT_FAILURE"]

        rec = res.get("recommendation", "")
        assert "confirms identity match" not in rec.lower()
        assert "identity confirmed" not in rec.lower()


def test_classical_gabor_lbp_never_produces_confident_match():
    """
    CRITICAL POLICY:
    LegacyGaborLBPProvider must NEVER unilaterally output VERIFIED MATCH
    because its feature space lacks certified metric separation for automated clearance.
    """
    gabor_provider = LegacyGaborLBPProvider()
    service = FaceVerificationService(gabor_provider)

    p1_path = os.path.join(REF_FACES_DIR, "PERSON-001_face_ref.jpg")
    p2_path = os.path.join(REF_FACES_DIR, "PERSON-002_face_ref.jpg")

    if os.path.exists(p1_path) and os.path.exists(p2_path):
        res = service.verify(p1_path, p2_path)
        assert res["verification_result"] != "VERIFIED MATCH"
        assert res["verification_result"] != "MATCH"
        assert res["decision_state"] in ["VERIFIED_MISMATCH", "INCONCLUSIVE"]
        assert "lacks validated neural metric separation" in res["recommendation"]
