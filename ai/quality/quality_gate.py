"""
SatyaScan Document Quality Gate
Evaluates document images for blur, glare, contrast, brightness, and resolution
before processing downstream OCR and forensic modules.
"""

from typing import Dict, Any, List
import cv2
import numpy as np


class DocumentQualityGate:
    """
    Standard pre-screening quality gate for border travel documents.
    Prevents garbage-in, garbage-out downstream by catching blurred,
    glare-compromised, or low-resolution captures early.
    """

    BLUR_THRESHOLD = 50.0            # Laplacian variance threshold
    MIN_WIDTH = 640                  # Minimum acceptable width in pixels
    MIN_HEIGHT = 480                 # Minimum acceptable height in pixels
    GLARE_MAX_RATIO = 0.12           # Max 12% pixels with near-max saturation (>250)
    MIN_CONTRAST = 18.0              # Standard deviation of grayscale intensity
    MIN_BRIGHTNESS = 25.0            # Mean grayscale intensity minimum
    MAX_BRIGHTNESS = 245.0           # Mean grayscale intensity maximum

    def __init__(self):
        self.version = "1.1.0"

    def assess_image(self, image_input: Any) -> Dict[str, Any]:
        """
        Assess image quality from a file path or a numpy array (BGR).
        Returns structured dictionary with quality verdict, scores, and reasons.
        """
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
            if img is None:
                return {
                    "verdict": "REJECTED",
                    "status": "UNREADABLE_FILE",
                    "overall_score": 0.0,
                    "reasons": ["Unable to decode image file."],
                    "metrics": {}
                }
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            return {
                "verdict": "REJECTED",
                "status": "INVALID_INPUT",
                "overall_score": 0.0,
                "reasons": ["Unsupported image input type."],
                "metrics": {}
            }

        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # 1. Blur evaluation using Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())

        # 2. Glare evaluation (percentage of clipped bright pixels > 250)
        glare_pixels = np.count_nonzero(gray >= 250)
        total_pixels = gray.size
        glare_ratio = float(glare_pixels / max(total_pixels, 1))

        # 3. Contrast evaluation (standard deviation of gray values)
        contrast_score = float(np.std(gray))

        # 4. Brightness evaluation (mean gray value)
        brightness_score = float(np.mean(gray))

        # 5. Resolution adequacy
        resolution_adequate = (width >= self.MIN_WIDTH and height >= self.MIN_HEIGHT)

        # Collect failure reasons
        reasons: List[str] = []
        is_acceptable = True

        if blur_score < self.BLUR_THRESHOLD:
            reasons.append(f"Excessive motion or optical blur detected (sharpness: {blur_score:.1f}, min required: {self.BLUR_THRESHOLD:.1f}).")
            is_acceptable = False

        if glare_ratio > self.GLARE_MAX_RATIO:
            reasons.append(f"Severe specular glare or reflection detected ({glare_ratio * 100:.1f}% clipped pixels).")
            is_acceptable = False

        if contrast_score < self.MIN_CONTRAST:
            reasons.append(f"Low image contrast ({contrast_score:.1f}, min required: {self.MIN_CONTRAST:.1f}).")
            is_acceptable = False

        if brightness_score < self.MIN_BRIGHTNESS:
            reasons.append(f"Image is underexposed/too dark (brightness: {brightness_score:.1f}).")
            is_acceptable = False
        elif brightness_score > self.MAX_BRIGHTNESS:
            reasons.append(f"Image is overexposed/washed out (brightness: {brightness_score:.1f}).")
            is_acceptable = False

        if not resolution_adequate:
            reasons.append(f"Image resolution too low ({width}x{height}, required: at least {self.MIN_WIDTH}x{self.MIN_HEIGHT}).")
            is_acceptable = False

        # Composite quality score (0.0 to 100.0)
        # Normalize sharpness (up to 300) -> 35 pts
        norm_sharpness = min(blur_score / 300.0, 1.0) * 35.0
        # Normalize glare -> 25 pts
        norm_glare = max(0.0, 1.0 - (glare_ratio / self.GLARE_MAX_RATIO)) * 25.0
        # Normalize contrast -> 20 pts
        norm_contrast = min(contrast_score / 60.0, 1.0) * 20.0
        # Normalize brightness -> 20 pts
        brightness_dev = abs(brightness_score - 128.0) / 128.0
        norm_brightness = max(0.0, 1.0 - brightness_dev) * 20.0

        overall_score = round(float(norm_sharpness + norm_glare + norm_contrast + norm_brightness), 1)

        verdict = "GOOD" if is_acceptable and overall_score >= 50.0 else "NEEDS_BETTER_IMAGE"
        status_message = "Image quality is suitable for automated screening." if verdict == "GOOD" else "Unable to reliably verify — please upload a clearer image."

        return {
            "verdict": verdict,
            "status_message": status_message,
            "overall_score": overall_score,
            "is_acceptable": is_acceptable,
            "reasons": reasons,
            "metrics": {
                "blur_score": round(blur_score, 2),
                "glare_percentage": round(glare_ratio * 100, 2),
                "contrast_score": round(contrast_score, 2),
                "brightness_score": round(brightness_score, 2),
                "resolution": {"width": width, "height": height},
                "resolution_adequate": resolution_adequate
            },
            "gate_version": self.version
        }
