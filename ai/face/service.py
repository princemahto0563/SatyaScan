"""
SatyaScan Face Verification & Biometric Subsystem V2
===================================================
Coordinates the full biometric pipeline:
DOCUMENT PHOTO -> FACE QUALITY -> BIOMETRIC EXTRACTION
  ↓
LIVE/PRESENTED FACE -> FACE QUALITY -> PRESENTATION ATTACK CHECK (PAD)
  ↓
1:1 VERIFICATION (Provider Adapter) -> MATCH / MISMATCH / UNABLE_TO_VERIFY
  ↓
APPEARANCE VARIATION ANALYSIS -> RISK ENGINE FUSION

STANDARDS & ETHICAL DISCLOSURES:
- Biometric verification serves solely as one supporting evidence signal.
  It NEVER independently makes the final legal clearance decision.
- Current active provider: LegacyGaborLBPProvider (512-D Gabor-LBP wavelets).
- Presentation Attack Detection (PAD): Transparently marked NOT_AVAILABLE in this prototype.
"""

from typing import Dict, Any, Optional, Tuple, List
import os
import cv2
import numpy as np

from ai.face.quality_gate import FaceQualityGate
from ai.face.pad_detector import PresentationAttackDetector
from ai.face.providers.base import BiometricProvider
from ai.face.providers.registry import get_biometric_provider


class FaceVerificationService:
    """
    Central biometric verification service for SatyaScan.
    Employs quality gating, modular providers, appearance variation analysis,
    and standardized biometric result packaging.
    """

    MATCH_THRESHOLD = 0.65
    BORDERLINE_THRESHOLD = 0.50

    def __init__(self, provider: Optional[BiometricProvider] = None):
        self.quality_gate = FaceQualityGate()
        self.pad_detector = PresentationAttackDetector(enabled=False)
        self.provider = provider or get_biometric_provider("gabor_lbp")
        self.version = self.provider.version

        # Load OpenCV Haar cascade for face and eye detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        eye_cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

    def detect_all_faces(self, img_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detects all candidate faces in an image returning list of (x, y, w, h)."""
        if img_bgr is None or img_bgr.size == 0:
            return []
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=3, minSize=(40, 40)
        )
        if len(faces) > 0:
            return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

        # TD3 portrait zone fallback for wide passport scans
        ih, iw = img_bgr.shape[:2]
        if iw > ih and iw >= 600:
            px1, py1 = int(iw * 0.04), int(ih * 0.16)
            pw, ph = int(iw * 0.24), int(ih * 0.40)
            crop_zone = gray[py1:py1+ph, px1:px1+pw]
            if crop_zone.size > 0 and np.std(crop_zone) > 15.0 and cv2.Laplacian(crop_zone, cv2.CV_64F).var() > 20.0:
                return [(px1, py1, pw, ph)]
        elif ih >= 150 and iw >= 120:
            crop_zone = gray[int(ih * 0.1):int(ih * 0.9), int(iw * 0.1):int(iw * 0.9)]
            if crop_zone.size > 0 and np.std(crop_zone) > 15.0 and cv2.Laplacian(crop_zone, cv2.CV_64F).var() > 20.0:
                return [(int(iw * 0.1), int(ih * 0.1), int(iw * 0.8), int(ih * 0.8))]

        return []

    def detect_and_crop_face(
        self, img_bgr: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[List[int]], Dict[str, Any]]:
        """
        Detects primary face, crops region, and evaluates quality gate metrics.
        Returns: (cropped_face, [x, y, w, h], quality_dict).
        Maintains complete backward compatibility with existing tests.
        """
        if img_bgr is None or img_bgr.size == 0:
            return None, None, {"detected": False, "reason": "Empty image buffer"}

        faces = self.detect_all_faces(img_bgr)
        quality_eval = self.quality_gate.assess_quality(img_bgr, faces)

        if len(faces) == 0 or not quality_eval.get("usable"):
            reason = "; ".join(quality_eval.get("reasons", ["No face detected"]))
            quality_dict = {
                "detected": len(faces) > 0,
                "reason": reason,
                "quality_adequate": False,
                "sharpness": quality_eval.get("blur_score", 0.0),
                "brightness": quality_eval.get("brightness_score", 0.0),
                "contrast": quality_eval.get("contrast_score", 0.0),
                "status": quality_eval.get("status", "UNABLE_TO_VERIFY"),
                "reasons": quality_eval.get("reasons", []),
                "face_count": len(faces)
            }
            if len(faces) == 0:
                return None, None, quality_dict

        # Select largest face
        faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces_sorted[0]

        ih, iw = img_bgr.shape[:2]
        pad_x = int(w * 0.1)
        pad_y = int(h * 0.1)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(iw, x + w + pad_x)
        y2 = min(ih, y + h + pad_y)

        cropped = img_bgr[y1:y2, x1:x2]

        quality_dict = {
            "detected": True,
            "face_width": int(w),
            "face_height": int(h),
            "sharpness": quality_eval.get("blur_score", 0.0),
            "brightness": quality_eval.get("brightness_score", 0.0),
            "contrast": quality_eval.get("contrast_score", 0.0),
            "quality_adequate": quality_eval.get("usable", True),
            "status": quality_eval.get("status", "GOOD"),
            "reasons": quality_eval.get("reasons", []),
            "face_count": len(faces)
        }

        return cropped, [int(x), int(y), int(w), int(h)], quality_dict

    def extract_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        """Delegates feature extraction to active BiometricProvider."""
        return self.provider.extract_embedding(face_bgr)

    def analyze_appearance_differences(
        self, doc_face_bgr: np.ndarray, live_face_bgr: np.ndarray
    ) -> Dict[str, Any]:
        """
        Analyzes visible appearance variations:
        - Facial hair texture (jawline/chin)
        - Spectacle frame edge density (eye region)
        - Illumination/exposure disparity
        """
        f1 = cv2.resize(doc_face_bgr, (120, 120))
        f2 = cv2.resize(live_face_bgr, (120, 120))

        g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)

        # 1. Lower-third face texture (jawline/chin for facial hair)
        lower1 = g1[70:120, 25:95]
        lower2 = g2[70:120, 25:95]
        lap1 = cv2.Laplacian(lower1, cv2.CV_64F).var()
        lap2 = cv2.Laplacian(lower2, cv2.CV_64F).var()

        hair_diff = abs(lap2 - lap1)
        facial_hair_change = hair_diff > 45.0
        beard_in_selfie = lap2 > lap1 + 40.0

        # 2. Upper eye-region edge density (eyewear/glasses)
        eye1 = g1[30:65, 20:100]
        eye2 = g2[30:65, 20:100]
        edges1 = cv2.Canny(eye1, 60, 130)
        edges2 = cv2.Canny(eye2, 60, 130)
        eye_density1 = np.count_nonzero(edges1) / float(edges1.size)
        eye_density2 = np.count_nonzero(edges2) / float(edges2.size)
        eyewear_diff = abs(eye_density2 - eye_density1) > 0.08

        # 3. Illumination disparity
        lum1 = float(np.mean(g1))
        lum2 = float(np.mean(g2))
        lighting_diff = abs(lum1 - lum2) > 35.0

        observations: List[str] = []
        if facial_hair_change:
            if beard_in_selfie:
                observations.append("Visible facial hair present in current live image (clean-shaven or lighter in document photo).")
            else:
                observations.append("Facial hair density difference detected.")
        if eyewear_diff:
            observations.append("Potential eyewear / spectacle frames detected in one of the images.")
        if lighting_diff:
            observations.append(f"Significant lighting disparity (doc luminance: {lum1:.0f}, selfie: {lum2:.0f}).")

        diff_count = len(observations)
        if diff_count == 0:
            diff_level = "MINIMAL"
        elif diff_count == 1:
            diff_level = "MODERATE"
        else:
            diff_level = "SIGNIFICANT"

        return {
            "appearance_difference_level": diff_level,
            "observations": observations,
            "details": {
                "facial_hair_variance_diff": round(hair_diff, 1),
                "eyewear_disparity": eyewear_diff,
                "lighting_delta": round(abs(lum1 - lum2), 1)
            }
        }

    def verify(self, doc_image_path: str, live_image_path: str) -> Dict[str, Any]:
        """
        Full Biometric V2 verification pipeline:
        Doc Face -> Quality -> Live Face -> Quality -> PAD -> 1:1 Embedding Match -> Risk Synthesis.
        """
        if not os.path.exists(doc_image_path):
            return {"error": "Document image not found", "verification_result": "UNABLE_TO_VERIFY"}
        if not os.path.exists(live_image_path):
            return {"error": "Live selfie image not found", "verification_result": "UNABLE_TO_VERIFY"}

        doc_img = cv2.imread(doc_image_path)
        live_img = cv2.imread(live_image_path)

        # 1. Quality Gate on Document Portrait
        doc_face, doc_box, doc_quality = self.detect_and_crop_face(doc_img)
        if not doc_quality.get("detected") or doc_face is None:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "reason": "Unable to locate a distinct face in document photograph.",
                "doc_face_quality": doc_quality,
                "provider": self.version,
                "disclaimer": "Document image does not contain a usable facial portrait."
            }

        # 2. Quality Gate on Live Capture
        live_faces = self.detect_all_faces(live_img)
        live_quality_eval = self.quality_gate.assess_quality(live_img, live_faces)

        if len(live_faces) == 0:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "reason": "Unable to locate face in live selfie. Ensure face is centered and illuminated.",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality_eval,
                "provider": self.version
            }

        if len(live_faces) > 1:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "reason": f"Multiple faces ({len(live_faces)}) detected in live capture. Exactly one person must be presented.",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality_eval,
                "provider": self.version
            }

        live_face, live_box, live_quality = self.detect_and_crop_face(live_img)
        if not live_quality.get("quality_adequate") or live_face is None:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "reason": "Current live selfie quality is insufficient (low sharpness or resolution).",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality,
                "provider": self.version
            }

        # 3. Presentation Attack Detection (PAD)
        pad_result = self.pad_detector.detect(live_img, live_box)

        # 4. Feature Extraction via active provider
        emb_doc = self.extract_embedding(doc_face)
        emb_live = self.extract_embedding(live_face)

        # 5. Cosine Similarity Calculation
        cosine_sim = self.provider.compute_similarity(emb_doc, emb_live)

        # 6. Appearance Variation Analysis
        appearance = self.analyze_appearance_differences(doc_face, live_face)

        # 7. Verification Decision
        match_thresh = self.provider.match_threshold
        borderline_thresh = self.provider.borderline_threshold

        if cosine_sim >= match_thresh:
            verdict = "MATCH"
            confidence = "HIGH" if cosine_sim >= 0.75 else "MODERATE"
            if appearance["appearance_difference_level"] != "MINIMAL":
                recommendation = (
                    f"Biometric similarity ({cosine_sim:.2f}) confirms identity match. "
                    f"Visible appearance variation ({appearance['appearance_difference_level']}) is consistent with natural changes (e.g. facial hair or lighting)."
                )
            else:
                recommendation = f"Biometric embedding similarity ({cosine_sim:.2f}) confirms strong identity correspondence."
        elif cosine_sim >= borderline_thresh:
            verdict = "BORDERLINE"
            confidence = "LOW"
            recommendation = (
                f"Biometric similarity ({cosine_sim:.2f}) falls in the review band. "
                "Secondary visual inspection or retake recommended."
            )
        else:
            verdict = "MISMATCH"
            confidence = "HIGH"
            recommendation = (
                f"Biometric similarity ({cosine_sim:.2f}) is below the minimum verification threshold. "
                "Potential identity impersonation. Secondary officer review required."
            )

        # Structured Biometric V2 Payload
        biometric_v2 = {
            "status": verdict,
            "provider": self.version,
            "similarity": cosine_sim,
            "threshold": match_thresh,
            "quality": {
                "status": live_quality.get("status", "GOOD"),
                "reasons": live_quality.get("reasons", []),
                "face_count": len(live_faces),
                "sharpness": live_quality.get("sharpness"),
                "brightness": live_quality.get("brightness"),
                "contrast": live_quality.get("contrast")
            },
            "presentation_attack": {
                "status": pad_result.get("status", "NOT_AVAILABLE"),
                "reason": pad_result.get("reason", "Presentation-attack detection is not enabled in this prototype.")
            },
            "appearance_variation": appearance["appearance_difference_level"],
            "explanation": recommendation,
            "disclaimer": "Biometric similarity is a model-derived metric, not a certified identity probability."
        }

        # Return full payload with backward compatibility
        return {
            "model_version": self.version,
            "provider": self.version,
            "metric": "Cosine Similarity",
            "similarity_score": cosine_sim,
            "threshold": match_thresh,
            "borderline_threshold": borderline_thresh,
            "verification_result": verdict,
            "confidence": confidence,
            "recommendation": recommendation,
            "appearance_analysis": appearance,
            "doc_face_box": doc_box,
            "live_face_box": live_box,
            "doc_quality": doc_quality,
            "live_quality": live_quality,
            "embedding_dim": self.provider.embedding_dim,
            "presentation_attack": pad_result,
            "biometric_verification": biometric_v2,
            "disclaimer": "Similarity score is a model-derived metric. It is not a calibrated probability that two images belong to the same person."
        }
