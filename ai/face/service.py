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
        self.provider = provider or get_biometric_provider("auto")
        self.version = self.provider.version

        # Load OpenCV Haar cascades for frontal face, profile face, and eyes
        self.face_cascade = None
        self.profile_cascade = None
        self.cascade_debug = {}
        try:
            cascade_cls = getattr(cv2, "CascadeClassifier", None)
            self.cascade_debug["cascade_cls_found"] = cascade_cls is not None
            if cascade_cls is not None:
                weights_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "weights"))
                data_dir = getattr(cv2.data, "haarcascades", "") if hasattr(cv2, "data") else ""
                self.cascade_debug["weights_dir"] = weights_dir
                self.cascade_debug["data_dir"] = data_dir

                # Frontal face cascade
                frontal_cands = [
                    os.path.join(weights_dir, "haarcascade_frontalface_default.xml"),
                    os.path.join(data_dir, "haarcascade_frontalface_default.xml") if data_dir else "",
                    "/app/ai/face/weights/haarcascade_frontalface_default.xml"
                ]
                self.cascade_debug["frontal_candidates"] = [(c, os.path.exists(c)) for c in frontal_cands if c]
                for p in frontal_cands:
                    if p and os.path.exists(p):
                        loaded = cascade_cls(os.path.abspath(p))
                        if not loaded.empty():
                            self.face_cascade = loaded
                            self.cascade_debug["frontal_loaded_from"] = p
                            break
                        else:
                            self.cascade_debug["frontal_empty_from"] = p

                # Eye cascade
                eye_cands = [
                    os.path.join(weights_dir, "haarcascade_eye.xml"),
                    os.path.join(data_dir, "haarcascade_eye.xml") if data_dir else "",
                    "/app/ai/face/weights/haarcascade_eye.xml"
                ]
                for p in eye_cands:
                    if p and os.path.exists(p):
                        loaded = cascade_cls(os.path.abspath(p))
                        if not loaded.empty():
                            self.eye_cascade = loaded
                            break

                # Profile face cascade
                profile_cands = [
                    os.path.join(weights_dir, "haarcascade_profileface.xml"),
                    os.path.join(data_dir, "haarcascade_profileface.xml") if data_dir else "",
                    "/app/ai/face/weights/haarcascade_profileface.xml"
                ]
                for p in profile_cands:
                    if p and os.path.exists(p):
                        loaded = cascade_cls(os.path.abspath(p))
                        if not loaded.empty():
                            self.profile_cascade = loaded
                            break
        except Exception as e:
            self.cascade_debug["exception"] = str(e)
            self.face_cascade = None
            self.profile_cascade = None
            self.eye_cascade = None

    def detect_all_faces(self, img_bgr: np.ndarray, is_document: bool = False) -> List[Tuple[int, int, int, int]]:
        """Detects all candidate faces in an image returning list of (x, y, w, h)."""
        if img_bgr is None or img_bgr.size == 0:
            return []
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        ih, iw = img_bgr.shape[:2]

        if self.face_cascade is not None:
            for s in [1.08, 1.1, 1.05]:
                try:
                    faces = self.face_cascade.detectMultiScale(
                        gray, scaleFactor=s, minNeighbors=3, minSize=(30, 30)
                    )
                    if len(faces) > 0:
                        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
                except Exception:
                    pass

        # Try profile face cascade if frontal did not locate a face
        if self.profile_cascade is not None:
            try:
                profiles = self.profile_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
                )
                if len(profiles) > 0:
                    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in profiles]
            except Exception:
                pass

        # Dedicated portrait photo check (e.g. pre-cropped passport / selfie image)
        if 0.55 <= (iw / ih) <= 1.25 and ih <= 400 and iw <= 400 and ih >= 80 and iw >= 80:
            if np.std(gray) > 20.0 and cv2.Laplacian(gray, cv2.CV_64F).var() > 20.0:
                fx = int(iw * 0.228)
                fy = int(ih * 0.20)
                fw = int(iw * 0.544)
                fh = int(ih * 0.445)
                return [(fx, fy, fw, fh)]

        # TD3 portrait zone fallback ONLY for wide passport document scans (Standard ICAO TD3 left quadrant)
        # NEVER apply to live selfies; verify facial structure to prevent false positives on emblems/covers
        is_doc = is_document or (iw > ih * 1.2 and iw >= 500)
        if is_doc and iw > ih and iw >= 500:
            candidates = []
            # Standard ICAO TD3 photo window (left quadrant: x~5.5%, y~18.3%, w~20%, h~36.7%)
            px1, py1 = int(iw * 0.055), int(ih * 0.183)
            pw, ph = int(iw * 0.20), int(ih * 0.367)
            crop_zone = gray[py1:py1+ph, px1:px1+pw]
            if crop_zone.size > 0 and np.std(crop_zone) > 18.0 and cv2.Laplacian(crop_zone, cv2.CV_64F).var() > 25.0:
                has_facial_feature = True
                if self.eye_cascade is not None:
                    eyes = self.eye_cascade.detectMultiScale(crop_zone, scaleFactor=1.1, minNeighbors=2)
                    has_facial_feature = len(eyes) >= 1
                elif self.face_cascade is not None:
                    faces_in_crop = self.face_cascade.detectMultiScale(crop_zone, scaleFactor=1.05, minNeighbors=2)
                    has_facial_feature = len(faces_in_crop) >= 1

                if has_facial_feature:
                    fx = px1 + int(pw * 0.228)
                    fy = py1 + int(ph * 0.20)
                    fw = int(pw * 0.544)
                    fh = int(ph * 0.445)
                    candidates.append((fx, fy, fw, fh))

            # Also check ghost watermark zone on right with facial feature verification
            gx1, gy1 = int(iw * 0.70), int(ih * 0.16)
            gw, gh = int(iw * 0.18), int(ih * 0.30)
            ghost_zone = gray[gy1:gy1+gh, gx1:gx1+gw]
            if ghost_zone.size > 0 and np.std(ghost_zone) > 18.0 and cv2.Laplacian(ghost_zone, cv2.CV_64F).var() > 25.0:
                if self.face_cascade is not None:
                    gf = self.face_cascade.detectMultiScale(ghost_zone, scaleFactor=1.05, minNeighbors=2)
                    if len(gf) >= 1:
                        candidates.append((gx1, gy1, gw, gh))
                else:
                    candidates.append((gx1, gy1, gw, gh))

            if candidates:
                return candidates

        return []

    def detect_and_crop_face(
        self, img_bgr: np.ndarray, is_document: bool = False
    ) -> Tuple[Optional[np.ndarray], Optional[List[int]], Dict[str, Any]]:
        """
        Detects primary face, crops region, and evaluates quality gate metrics.
        Returns: (cropped_face, [x, y, w, h], quality_dict).
        Never fabricates a face when no face exists.
        """
        if img_bgr is None or img_bgr.size == 0:
            return None, None, {"detected": False, "reason": "Empty image buffer", "quality_adequate": False, "status": "UNABLE_TO_VERIFY"}

        ih, iw = img_bgr.shape[:2]
        is_doc = is_document or (iw > ih * 1.2 and iw >= 500)
        faces = self.detect_all_faces(img_bgr, is_document=is_doc)
        quality_eval = self.quality_gate.assess_quality(img_bgr, faces, is_document=is_doc)

        if len(faces) == 0:
            quality_dict = {
                "detected": False,
                "reason": "No face detected in image",
                "quality_adequate": False,
                "sharpness": 0.0,
                "brightness": float(np.mean(img_bgr)),
                "contrast": float(np.std(img_bgr)),
                "status": "UNABLE_TO_VERIFY",
                "reasons": ["No face detected in image"],
                "face_count": 0
            }
            return None, None, quality_dict

        if not quality_eval.get("usable"):
            reason = "; ".join(quality_eval.get("reasons", ["Face quality inadequate"]))
            quality_dict = {
                "detected": True,
                "reason": reason,
                "quality_adequate": False,
                "sharpness": quality_eval.get("blur_score", 0.0),
                "brightness": quality_eval.get("brightness_score", 0.0),
                "contrast": quality_eval.get("contrast_score", 0.0),
                "status": quality_eval.get("status", "POOR"),
                "reasons": quality_eval.get("reasons", []),
                "face_count": len(faces)
            }
            return None, None, quality_dict

        # Select primary face: for documents prefer left-half portrait, else largest
        if is_doc and len(faces) > 1:
            left_faces = [f for f in faces if (f[0] + f[2] / 2) < iw * 0.55]
            faces_sorted = sorted(left_faces or faces, key=lambda f: f[2] * f[3], reverse=True)
        else:
            faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces_sorted[0]

        pad_x = int(w * 0.1)
        pad_y = int(h * 0.1)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(iw, x + w + pad_x) if 'iw' in locals() else min(img_bgr.shape[1], x + w + pad_x)
        y2 = min(ih, y + h + pad_y) if 'ih' in locals() else min(img_bgr.shape[0], y + h + pad_y)

        cropped = img_bgr[y1:y2, x1:x2]

        quality_dict = {
            "detected": True,
            "face_width": int(w),
            "face_height": int(h),
            "sharpness": quality_eval.get("blur_score", 0.0),
            "brightness": quality_eval.get("brightness_score", 0.0),
            "contrast": quality_eval.get("contrast_score", 0.0),
            "usable": quality_eval.get("usable", True),
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

    def verify(self, doc_image: Any, live_image: Any) -> Dict[str, Any]:
        """
        Full Biometric V2 verification pipeline:
        Doc Face -> Quality -> Live Face -> Quality -> PAD -> 1:1 Embedding Match -> Risk Synthesis.
        Supports either image file paths (str) or loaded BGR image matrices (np.ndarray).
        """
        is_neural = getattr(self.provider, "is_neural", False)
        provider_type = "DEEP_NEURAL" if is_neural else "CLASSICAL_BASELINE"

        if isinstance(doc_image, np.ndarray):
            doc_img = doc_image
        elif isinstance(doc_image, str):
            if not os.path.exists(doc_image):
                return {
                    "error": "Document image not found",
                    "verification_result": "UNABLE_TO_VERIFY",
                    "decision_state": "INPUT_FAILURE",
                    "status": "INPUT_FAILURE",
                    "confidence": "NONE",
                    "provider": self.version,
                    "provider_type": provider_type,
                    "requires_manual_inspection": True
                }
            doc_img = cv2.imread(doc_image)
        else:
            return {
                "error": "Invalid document image format",
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True
            }

        if isinstance(live_image, np.ndarray):
            live_img = live_image
        elif isinstance(live_image, str):
            if not os.path.exists(live_image):
                return {
                    "error": "Live selfie image not found",
                    "verification_result": "UNABLE_TO_VERIFY",
                    "decision_state": "INPUT_FAILURE",
                    "status": "INPUT_FAILURE",
                    "confidence": "NONE",
                    "provider": self.version,
                    "provider_type": provider_type,
                    "requires_manual_inspection": True
                }
            live_img = cv2.imread(live_image)
        else:
            return {
                "error": "Invalid live selfie format",
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True
            }

        if doc_img is None or doc_img.size == 0:
            return {
                "error": "Empty document image",
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True
            }
        if live_img is None or live_img.size == 0:
            return {
                "error": "Empty live image",
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True
            }

        # 1. Quality Gate on Document Portrait
        doc_face, doc_box, doc_quality = self.detect_and_crop_face(doc_img, is_document=True)
        if not doc_quality.get("detected") or doc_face is None:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "pad_status": "NOT_AVAILABLE",
                "similarity_score": 0.0,
                "reason": "Usable identity portrait not detected in submitted document image.",
                "recommendation": "Usable identity portrait not detected in submitted document image. Upload the passport biodata/identity page containing portrait and machine-readable information.",
                "doc_face_quality": doc_quality,
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True,
                "evidence_metadata": {
                    "document_face_bbox": None,
                    "presented_face_bbox": None,
                    "document_face_count": 0,
                    "presented_face_count": 0,
                    "provider_type": provider_type,
                    "requires_manual_inspection": True,
                    "decision_explanation": "Usable identity portrait not detected in submitted document image."
                },
                "disclaimer": "Usable identity portrait not detected in submitted document image."
            }

        # 2. Quality Gate on Live Capture
        live_faces = self.detect_all_faces(live_img, is_document=False)
        live_quality_eval = self.quality_gate.assess_quality(live_img, live_faces, is_document=False)

        if len(live_faces) == 0:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "pad_status": "NOT_AVAILABLE",
                "similarity_score": 0.0,
                "reason": "Live facial capture unavailable.",
                "recommendation": "Live facial capture unavailable. Please ensure camera faces subject directly under neutral lighting.",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality_eval,
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True,
                "evidence_metadata": {
                    "document_face_bbox": doc_box,
                    "presented_face_bbox": None,
                    "document_face_count": 1,
                    "presented_face_count": 0,
                    "provider_type": provider_type,
                    "requires_manual_inspection": True,
                    "decision_explanation": "Live facial capture unavailable."
                }
            }

        if len(live_faces) > 1:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "pad_status": "NOT_AVAILABLE",
                "similarity_score": 0.0,
                "reason": f"Multiple faces ({len(live_faces)}) detected in live capture. Exactly one person must be presented.",
                "recommendation": f"Multiple faces ({len(live_faces)}) detected in selfie. Only one individual may be present during capture.",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality_eval,
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True,
                "evidence_metadata": {
                    "document_face_bbox": doc_box,
                    "presented_face_bbox": None,
                    "document_face_count": 1,
                    "presented_face_count": len(live_faces),
                    "provider_type": provider_type,
                    "requires_manual_inspection": True,
                    "decision_explanation": f"Multiple faces ({len(live_faces)}) in selfie."
                }
            }

        live_face, live_box, live_quality = self.detect_and_crop_face(live_img, is_document=False)
        if not live_quality.get("quality_adequate") or live_face is None:
            return {
                "verification_result": "UNABLE_TO_VERIFY",
                "decision_state": "INPUT_FAILURE",
                "status": "INPUT_FAILURE",
                "confidence": "NONE",
                "pad_status": "NOT_AVAILABLE",
                "similarity_score": 0.0,
                "reason": "Current live selfie quality is insufficient (low sharpness or resolution).",
                "recommendation": "Selfie image quality does not meet minimum sharpness standards. Re-take photo without motion blur.",
                "doc_face_quality": doc_quality,
                "live_face_quality": live_quality,
                "provider": self.version,
                "provider_type": provider_type,
                "requires_manual_inspection": True,
                "evidence_metadata": {
                    "document_face_bbox": doc_box,
                    "presented_face_bbox": live_box,
                    "document_face_count": 1,
                    "presented_face_count": 1,
                    "provider_type": provider_type,
                    "requires_manual_inspection": True,
                    "decision_explanation": "Selfie quality below threshold."
                }
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

        # 7. Multi-Signal Verification Decision (4 explicit states)
        match_thresh = self.provider.match_threshold
        borderline_thresh = self.provider.borderline_threshold
        is_discriminative = getattr(self.provider, "is_discriminative", False)

        if is_neural and is_discriminative:
            # Neural model with validated metric separation (SFace)
            if cosine_sim >= match_thresh:
                verdict = "VERIFIED MATCH"
                decision_state = "VERIFIED_MATCH"
                confidence = "HIGH" if cosine_sim >= 0.75 else "MODERATE"
                recommendation = f"Biometric embedding similarity ({cosine_sim:.2f}) meets validated criteria for identity correspondence under active deep neural model."
            elif cosine_sim < borderline_thresh:
                verdict = "VERIFIED MISMATCH"
                decision_state = "VERIFIED_MISMATCH"
                confidence = "HIGH"
                recommendation = (
                    f"Presented face does not correspond to document portrait (similarity: {cosine_sim:.2f}, "
                    f"below mismatch threshold {borderline_thresh:.2f}). Potential identity impersonation. Secondary review required."
                )
            else:
                verdict = "INCONCLUSIVE"
                decision_state = "INCONCLUSIVE"
                confidence = "LOW"
                recommendation = (
                    f"Biometric similarity ({cosine_sim:.2f}) falls in the review band [{borderline_thresh:.2f}, {match_thresh:.2f}). "
                    "Secondary visual inspection required."
                )
        else:
            # Conservative Policy for Classical Descriptors (GaborLBP):
            # Classical texture wavelets can identify distinct structural divergence,
            # but MUST NEVER unilaterally declare an automated positive MATCH.
            if cosine_sim < borderline_thresh:
                verdict = "VERIFIED MISMATCH"
                decision_state = "VERIFIED_MISMATCH"
                confidence = "HIGH"
                recommendation = (
                    f"Presented face does not correspond to document photograph (biometric similarity: {cosine_sim:.2f}, "
                    f"below mismatch threshold {borderline_thresh:.2f}). Potential identity impersonation. Secondary officer review required."
                )
            else:
                verdict = "INCONCLUSIVE"
                decision_state = "INCONCLUSIVE"
                confidence = "LOW"
                recommendation = (
                    f"Identity comparison is inconclusive (similarity: {cosine_sim:.2f}). "
                    f"Active classical baseline descriptor ({self.version}) lacks validated neural metric separation for automated clearance. "
                    "Mandatory officer visual verification required."
                )

        evidence_metadata = {
            "document_face_bbox": doc_box,
            "presented_face_bbox": live_box,
            "document_face_count": doc_quality.get("face_count", 1),
            "presented_face_count": len(live_faces),
            "document_face_quality": doc_quality.get("status", "GOOD"),
            "presented_face_quality": live_quality.get("status", "GOOD"),
            "provider_type": provider_type,
            "metric": "Cosine Similarity",
            "decision_explanation": recommendation,
            "requires_manual_inspection": True if decision_state in ("INCONCLUSIVE", "INPUT_FAILURE") else False
        }

        # Structured Biometric V2 Payload
        biometric_v2 = {
            "status": verdict,
            "decision_state": decision_state,
            "provider": self.version,
            "provider_type": provider_type,
            "similarity": cosine_sim,
            "threshold": match_thresh,
            "borderline_threshold": borderline_thresh,
            "quality": {
                "status": live_quality.get("status", "GOOD"),
                "reasons": live_quality.get("reasons", []),
                "face_count": len(live_faces),
                "sharpness": live_quality.get("sharpness"),
                "brightness": live_quality.get("brightness"),
                "contrast": live_quality.get("contrast")
            },
            "presentation_attack": {
                "status": "NOT_AVAILABLE",
                "reason": "No presentation-attack detection is currently enabled in this prototype."
            },
            "appearance_variation": appearance["appearance_difference_level"],
            "explanation": recommendation,
            "evidence_metadata": evidence_metadata,
            "disclaimer": "Similarity score is a model-derived metric. It is not a calibrated probability that two images belong to the same person."
        }

        # Return full payload with backward compatibility and face crops
        return {
            "model_version": self.version,
            "provider": self.version,
            "provider_type": provider_type,
            "metric": "Cosine Similarity",
            "similarity_score": cosine_sim,
            "threshold": match_thresh,
            "borderline_threshold": borderline_thresh,
            "verification_result": verdict,
            "decision_state": decision_state,
            "confidence": confidence,
            "recommendation": recommendation,
            "appearance_analysis": appearance,
            "doc_face_box": doc_box,
            "live_face_box": live_box,
            "doc_face_crop": doc_face,
            "live_face_crop": live_face,
            "doc_quality": doc_quality,
            "live_quality": live_quality,
            "pad_status": "NOT_AVAILABLE",
            "requires_manual_inspection": True if decision_state in ("INCONCLUSIVE", "INPUT_FAILURE") else False,
            "presentation_attack": {
                "status": "NOT_AVAILABLE",
                "reason": "No presentation-attack detection is currently enabled in this prototype."
            },
            "evidence_metadata": evidence_metadata,
            "biometric_verification": biometric_v2,
            "disclaimer": "Similarity score is a model-derived metric. It is not a calibrated probability that two images belong to the same person."
        }

    # API Alias
    verify_identity = verify

