"""
SatyaScan Biometric Quality Gate
================================
Performs objective facial image quality assessment prior to biometric comparison.
Evaluates:
- Face detection presence
- Single vs multiple face presence
- Minimum face resolution / bounding box dimensions
- Image sharpness / blur (Laplacian variance)
- Exposure / illumination balance (mean gray intensity)
- Contrast dynamics (standard deviation)
- Relative face-to-image area ratio

Returns standardized quality states:
GOOD, ACCEPTABLE, POOR, UNABLE_TO_VERIFY with clear, objective reasons.
"""

from typing import Dict, Any, Optional, List, Tuple
import cv2
import numpy as np


class FaceQualityGate:
    """
    Evaluates documentary portrait and live webcam facial image quality.
    Ensures biometric verification only operates on usable facial evidence.
    """

    # Quality Thresholds
    MIN_FACE_WIDTH = 50
    MIN_FACE_HEIGHT = 50
    OPTIMAL_FACE_WIDTH = 80
    OPTIMAL_FACE_HEIGHT = 80

    BLUR_ACCEPTABLE_MIN = 25.0
    BLUR_GOOD_MIN = 60.0

    BRIGHTNESS_MIN = 35.0
    BRIGHTNESS_MAX = 225.0
    BRIGHTNESS_OPTIMAL_MIN = 60.0
    BRIGHTNESS_OPTIMAL_MAX = 200.0

    CONTRAST_MIN = 18.0
    CONTRAST_GOOD_MIN = 30.0

    def assess_quality(
        self,
        img_bgr: np.ndarray,
        detected_faces: List[Tuple[int, int, int, int]],
        is_document: bool = False
    ) -> Dict[str, Any]:
        """
        Assesses facial quality on image and detected face coordinates.
        detected_faces: list of [x, y, w, h] boxes.
        is_document: True if evaluating a travel document scan (passports frequently have
        a primary photo on the left and a secondary ghost/hologram portrait on the right).
        """
        if img_bgr is None or img_bgr.size == 0:
            return {
                "status": "UNABLE_TO_VERIFY",
                "usable": False,
                "face_count": 0,
                "blur_score": 0.0,
                "brightness_score": 0.0,
                "contrast_score": 0.0,
                "face_size_ratio": 0.0,
                "reasons": ["Image buffer is empty or corrupt."]
            }

        ih, iw = img_bgr.shape[:2]
        is_doc = is_document or (iw > ih * 1.2 and iw >= 500)
        face_count = len(detected_faces)
        reasons: List[str] = []

        if face_count == 0:
            return {
                "status": "UNABLE_TO_VERIFY",
                "usable": False,
                "face_count": 0,
                "blur_score": 0.0,
                "brightness_score": 0.0,
                "contrast_score": 0.0,
                "face_size_ratio": 0.0,
                "reasons": ["No face detected in submitted image."]
            }

        if face_count > 1:
            if is_doc:
                # Travel documents often contain a primary portrait and a ghost/hologram portrait
                reasons.append(f"Multiple facial regions ({face_count}) located in document (primary portrait and secondary/ghost watermark).")
            else:
                reasons.append(f"Multiple faces ({face_count}) detected in frame. Exactly one face must be presented.")

        # Primary face: for documents, prefer faces in the left half if available, or largest
        if is_doc and face_count > 1:
            # Standard ICAO TD3 primary photo is situated in the left half (x < iw * 0.55)
            left_faces = [f for f in detected_faces if (f[0] + f[2] / 2) < iw * 0.55]
            if left_faces:
                primary_face = max(left_faces, key=lambda f: f[2] * f[3])
            else:
                primary_face = max(detected_faces, key=lambda f: f[2] * f[3])
        else:
            primary_face = max(detected_faces, key=lambda f: f[2] * f[3])

        x, y, w, h = primary_face
        ih, iw = img_bgr.shape[:2]

        face_crop = img_bgr[max(0, y):min(ih, y + h), max(0, x):min(iw, x + w)]
        if face_crop.size == 0:
            return {
                "status": "UNABLE_TO_VERIFY",
                "usable": False,
                "face_count": face_count,
                "blur_score": 0.0,
                "brightness_score": 0.0,
                "contrast_score": 0.0,
                "face_size_ratio": 0.0,
                "reasons": ["Face bounding box yields an empty crop."]
            }

        gray_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

        # 1. Sharpness / Blur (Laplacian variance)
        blur_score = round(float(cv2.Laplacian(gray_crop, cv2.CV_64F).var()), 1)

        # 2. Brightness / Illumination (Mean pixel intensity)
        brightness_score = round(float(np.mean(gray_crop)), 1)

        # 3. Contrast (Standard deviation of intensity)
        contrast_score = round(float(np.std(gray_crop)), 1)

        # 4. Face size ratio relative to entire frame
        face_area = float(w * h)
        total_area = float(iw * ih)
        face_size_ratio = round(face_area / total_area if total_area > 0 else 0.0, 4)

        # Check conditions
        is_poor = False
        is_acceptable = False

        if face_count > 1 and not is_doc:
            is_poor = True

        if w < self.MIN_FACE_WIDTH or h < self.MIN_FACE_HEIGHT:
            is_poor = True
            reasons.append(f"Face resolution too small ({w}x{h} px; minimum is {self.MIN_FACE_WIDTH}x{self.MIN_FACE_HEIGHT} px).")
        elif w < self.OPTIMAL_FACE_WIDTH or h < self.OPTIMAL_FACE_HEIGHT:
            is_acceptable = True
            reasons.append(f"Face resolution is marginal ({w}x{h} px).")

        if blur_score < self.BLUR_ACCEPTABLE_MIN:
            is_poor = True
            reasons.append(f"Image blur detected (sharpness: {blur_score}; minimum acceptable is {self.BLUR_ACCEPTABLE_MIN}).")
        elif blur_score < self.BLUR_GOOD_MIN:
            is_acceptable = True
            reasons.append(f"Slight motion or optical blur observed (sharpness: {blur_score}).")

        if brightness_score < self.BRIGHTNESS_MIN:
            is_poor = True
            reasons.append(f"Underexposed photograph (luminance: {brightness_score}; minimum is {self.BRIGHTNESS_MIN}).")
        elif brightness_score > self.BRIGHTNESS_MAX:
            is_poor = True
            reasons.append(f"Overexposed photograph (luminance: {brightness_score}; maximum is {self.BRIGHTNESS_MAX}).")
        elif brightness_score < self.BRIGHTNESS_OPTIMAL_MIN or brightness_score > self.BRIGHTNESS_OPTIMAL_MAX:
            is_acceptable = True
            reasons.append(f"Non-optimal lighting conditions (luminance: {brightness_score}).")

        if contrast_score < self.CONTRAST_MIN:
            is_poor = True
            reasons.append(f"Very low contrast dynamics (contrast std: {contrast_score}).")
        elif contrast_score < self.CONTRAST_GOOD_MIN:
            is_acceptable = True

        # Final quality status
        if is_poor:
            status = "POOR"
            usable = False
        elif is_acceptable:
            status = "ACCEPTABLE"
            usable = True
        else:
            status = "GOOD"
            usable = True

        return {
            "status": status,
            "usable": usable,
            "face_count": face_count,
            "face_dimensions": [int(w), int(h)],
            "blur_score": blur_score,
            "brightness_score": brightness_score,
            "contrast_score": contrast_score,
            "face_size_ratio": face_size_ratio,
            "reasons": reasons
        }
