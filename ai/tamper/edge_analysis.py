"""
SatyaScan Edge & Boundary Splicing Analysis
Analyzes gradient discontinuities and edge consistency around portrait windows
and document text zones to detect synthetic insertion or digital cutout artifacts.
"""

from typing import Dict, Any
import cv2
import numpy as np


class EdgeDiscontinuityAnalyzer:
    """
    Evaluates boundary transition sharpness and gradient gradients.
    Pasted/spliced elements typically have unnaturally steep or blurred edge gradients
    relative to natural document paper grain and guilloche patterns.
    """

    def __init__(self):
        self.version = "EdgeAnalysis-v1.0"

    def analyze(self, image_input: Any) -> Dict[str, Any]:
        """
        Calculates Sobel gradients, Canny edge densities, and border gradient jumps.
        """
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            return {"error": "Invalid image input"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape[:2]

        # 1. Compute Sobel gradients in X and Y
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(sobelx**2 + sobely**2)

        # 2. Analyze portrait window sub-region (typically left 10%-45% width, 20%-70% height in TD3 passports)
        px1, py1 = int(w * 0.08), int(h * 0.15)
        px2, py2 = int(w * 0.45), int(h * 0.75)
        portrait_zone = gradient_mag[py1:py2, px1:px2]

        # 3. Analyze boundary strip of the portrait window (outer 15 pixels)
        # Splicing shows an abrupt jump in gradient magnitude along the cutout seam
        boundary_mask = np.zeros_like(gray, dtype=np.uint8)
        cv2.rectangle(boundary_mask, (px1, py1), (px2, py2), 255, thickness=12)

        boundary_gradients = gradient_mag[boundary_mask > 0]
        mean_boundary_grad = float(np.mean(boundary_gradients)) if len(boundary_gradients) > 0 else 0.0
        doc_mean_grad = float(np.mean(gradient_mag)) if gradient_mag.size > 0 else 1.0

        boundary_jump_ratio = mean_boundary_grad / max(doc_mean_grad, 0.1)

        # Anomaly score based on seam gradient jump
        raw_score = (boundary_jump_ratio - 1.8) * 35.0
        anomaly_score = round(min(max(float(raw_score), 0.0), 100.0), 1)

        observation = (
            f"Mean document gradient: {doc_mean_grad:.2f}. "
            f"Portrait boundary gradient: {mean_boundary_grad:.2f} (jump ratio: {boundary_jump_ratio:.2f})."
        )

        interpretation = (
            "Abrupt edge gradient jump detected around portrait boundary. Possible photo replacement or digital insertion seam."
            if anomaly_score >= 45.0 else
            "Edge gradient transitions are consistent with authentic printing and document paper texture."
        )

        return {
            "technique": "Edge & Boundary Analysis",
            "anomaly_score": anomaly_score,
            "document_mean_gradient": round(doc_mean_grad, 2),
            "boundary_mean_gradient": round(mean_boundary_grad, 2),
            "boundary_jump_ratio": round(boundary_jump_ratio, 2),
            "observation": observation,
            "interpretation": interpretation,
            "recommendation": "Inspect portrait border under magnification for digital seams." if anomaly_score >= 45.0 else "Normal boundary baseline."
        }
