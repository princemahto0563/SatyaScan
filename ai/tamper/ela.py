"""
SatyaScan Error Level Analysis (ELA) Engine
Computes genuine Error Level Analysis by recompressing at a known JPEG quality,
measuring compression artifact residuals, and generating an anomaly heatmap.
"""

from typing import Dict, Any, Tuple
import cv2
import numpy as np
from PIL import Image, ImageChops
import io
import os


class ELAEngine:
    """
    Error Level Analysis (ELA) implementation.
    Detects compression inconsistencies caused by digital splicing or localized editing.
    """

    def __init__(self, quality: int = 90, scale_multiplier: float = 15.0):
        self.quality = quality
        self.scale_multiplier = scale_multiplier
        self.version = "ELA-v1.2"

    def analyze(self, image_input: Any, output_heatmap_path: str = None) -> Dict[str, Any]:
        """
        Executes Error Level Analysis on image_input (filepath or numpy BGR array).
        Returns ELA metrics, suspicious regions, and saves/encodes the color heatmap.
        """
        if isinstance(image_input, str):
            orig_pil = Image.open(image_input).convert("RGB")
            orig_cv = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            orig_cv = image_input
            orig_pil = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        else:
            return {"error": "Invalid image input"}

        # 1. Re-save in memory at target JPEG quality
        buffer = io.BytesIO()
        orig_pil.save(buffer, format="JPEG", quality=self.quality)
        buffer.seek(0)
        recompressed_pil = Image.open(buffer)

        # 2. Compute absolute difference between original and recompressed
        diff_pil = ImageChops.difference(orig_pil, recompressed_pil)
        diff_arr = np.array(diff_pil, dtype=np.float32)

        # 3. Calculate mean error levels per channel and overall
        mean_diff = float(np.mean(diff_arr))
        max_diff = float(np.max(diff_arr))
        std_diff = float(np.std(diff_arr))

        # 4. Generate visual ELA representation with contrast amplification
        scaled_diff = np.clip(diff_arr * self.scale_multiplier, 0, 255).astype(np.uint8)
        gray_ela = cv2.cvtColor(scaled_diff, cv2.COLOR_RGB2GRAY)

        # 5. Apply JET colormap for high-clarity forensic heatmap display
        heatmap_bgr = cv2.applyColorMap(gray_ela, cv2.COLORMAP_JET)

        # Overlay slightly with original for contextual recognition
        h, w = orig_cv.shape[:2]
        heatmap_resized = cv2.resize(heatmap_bgr, (w, h))
        blended = cv2.addWeighted(orig_cv, 0.35, heatmap_resized, 0.65, 0)

        # Save heatmap if path provided
        if output_heatmap_path:
            os.makedirs(os.path.dirname(output_heatmap_path), exist_ok=True)
            cv2.imwrite(output_heatmap_path, blended)

        # 6. Detect localized high-error outlier regions (potential spliced zones)
        # Threshold at mean + 2.5 standard deviations
        threshold_val = mean_diff + 2.2 * std_diff
        suspicious_mask = (gray_ela > np.clip(threshold_val * self.scale_multiplier, 40, 250)).astype(np.uint8)

        contours, _ = cv2.findContours(suspicious_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        suspicious_regions = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > (w * h * 0.002):  # Minimum 0.2% of document area
                x, y, rw, rh = cv2.boundingRect(c)
                region_mean = float(np.mean(gray_ela[y:y+rh, x:x+rw]))
                suspicious_regions.append({
                    "bounding_box": [x, y, rw, rh],
                    "area_pixels": int(area),
                    "local_ela_intensity": round(region_mean, 2),
                    "suspect_category": "PORTRAIT_ZONE" if x < w * 0.45 and y < h * 0.7 else "TEXT_ZONE"
                })

        # Calculate composite ELA anomaly score (0 - 100)
        # Standard uniform images have low std_diff and low max/mean ratio
        # Spliced images have distinct clusters of high difference
        anomaly_ratio = (max_diff / max(mean_diff, 0.1))
        raw_score = (std_diff * 4.0) + (len(suspicious_regions) * 12.0) + (anomaly_ratio * 2.0)
        anomaly_score = round(min(max(float(raw_score), 0.0), 100.0), 1)

        observation = (
            f"Mean ELA error is {mean_diff:.2f} (std {std_diff:.2f}). "
            f"Identified {len(suspicious_regions)} localized regions with anomalous compression residuals."
            if suspicious_regions else
            f"Compression residuals appear uniform across document (mean ELA: {mean_diff:.2f})."
        )

        interpretation = (
            "Compression inconsistency detected. Suggests portions of the document were saved under different compression parameters or edited independently."
            if anomaly_score >= 45.0 else
            "No significant compression discontinuity detected. Document exhibits consistent single-generation compression."
        )

        return {
            "technique": "Error Level Analysis (ELA)",
            "anomaly_score": anomaly_score,
            "mean_difference": round(mean_diff, 2),
            "max_difference": round(max_diff, 2),
            "std_difference": round(std_diff, 2),
            "suspicious_regions_detected": len(suspicious_regions),
            "suspicious_regions": suspicious_regions,
            "heatmap_path": output_heatmap_path,
            "observation": observation,
            "interpretation": interpretation,
            "recommendation": "Manual secondary verification recommended." if anomaly_score >= 45.0 else "Normal compression baseline."
        }
