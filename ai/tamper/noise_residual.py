"""
SatyaScan Sensor Noise Residual Analysis
Analyzes local high-frequency sensor noise variance to detect digital splicing,
inpainting, or content replacement.
"""

from typing import Dict, Any, List
import cv2
import numpy as np


class NoiseResidualEngine:
    """
    High-pass noise residual forensic analyzer.
    Authentic camera captures exhibit uniform Photo Response Non-Uniformity (PRNU)
    and Gaussian sensor noise. Spliced foreign elements disrupt this local distribution.
    """

    def __init__(self, grid_rows: int = 4, grid_cols: int = 4):
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.version = "NoiseResidual-v1.0"

    def analyze(self, image_input: Any) -> Dict[str, Any]:
        """
        Executes noise residual extraction and patch-based variance analysis.
        """
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            return {"error": "Invalid image input"}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # 1. Extract high-frequency residual via median filter subtraction
        denoised = cv2.medianBlur(gray, 3)
        residual = cv2.absdiff(gray, denoised).astype(np.float32)

        # 2. Divide into grid patches and evaluate local noise variance
        patch_h = h // self.grid_rows
        patch_w = w // self.grid_cols
        patch_variances: List[float] = []
        grid_data: List[Dict[str, Any]] = []

        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                y1 = r * patch_h
                y2 = (r + 1) * patch_h if r < self.grid_rows - 1 else h
                x1 = c * patch_w
                x2 = (c + 1) * patch_w if c < self.grid_cols - 1 else w

                patch = residual[y1:y2, x1:x2]
                var = float(np.var(patch))
                patch_variances.append(var)
                grid_data.append({
                    "row": r,
                    "col": c,
                    "bounds": [x1, y1, x2 - x1, y2 - y1],
                    "noise_variance": round(var, 3)
                })

        # 3. Calculate statistical deviation across patches
        median_var = float(np.median(patch_variances)) if patch_variances else 1.0
        max_var = float(np.max(patch_variances)) if patch_variances else 1.0
        min_var = float(np.min(patch_variances)) if patch_variances else 1.0
        std_var = float(np.std(patch_variances)) if patch_variances else 0.0

        ratio = (max_var / max(median_var, 0.01))
        # Anomaly score based on variance spread
        anomaly_score = round(min(max((ratio - 1.5) * 20.0 + (std_var * 3.0), 0.0), 100.0), 1)

        anomalous_patches = [
            p for p in grid_data
            if p["noise_variance"] > (median_var + 2.0 * std_var) or p["noise_variance"] < (median_var - 1.8 * std_var)
        ]

        observation = (
            f"Evaluated {len(grid_data)} spatial patches. Median noise variance: {median_var:.2f}, "
            f"Max variance: {max_var:.2f} (ratio {ratio:.2f}). Identified {len(anomalous_patches)} outlier patches."
        )

        interpretation = (
            "Localized noise residual disparity detected. Certain document regions exhibit inconsistent noise characteristics."
            if anomaly_score >= 45.0 else
            "Sensor noise distribution appears statistically homogeneous across the document surface."
        )

        return {
            "technique": "Noise Residual Analysis",
            "anomaly_score": anomaly_score,
            "median_variance": round(median_var, 2),
            "max_variance": round(max_var, 2),
            "variance_ratio": round(ratio, 2),
            "anomalous_patches_count": len(anomalous_patches),
            "anomalous_patches": anomalous_patches,
            "observation": observation,
            "interpretation": interpretation,
            "recommendation": "Review high-residual regions for localized splicing." if anomaly_score >= 45.0 else "Noise characteristics normal."
        }
