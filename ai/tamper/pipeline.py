"""
SatyaScan Master Tampering Forensics Pipeline
Integrates 5 independent forensic signals:
1. Error Level Analysis (ELA)
2. Noise / Residual Analysis
3. Copy-Move Forgery Detection (CMFD)
4. Edge & Boundary Discontinuity Analysis
5. Metadata & EXIF Analysis
"""

from typing import Dict, Any, List
import os
import cv2
import numpy as np

from ai.tamper.ela import ELAEngine
from ai.tamper.noise_residual import NoiseResidualEngine
from ai.tamper.copy_move import CopyMoveDetector
from ai.tamper.edge_analysis import EdgeDiscontinuityAnalyzer
from ai.tamper.metadata import MetadataForensics


class TamperForensicsPipeline:
    """
    Multi-signal forensic analysis orchestrator.
    Combines independent physical and mathematical image artifacts
    into a calibrated anomaly score and explainable evidence cards.
    """

    def __init__(self):
        self.version = "MultiSignal-Forensics-v1.0"
        self.ela_engine = ELAEngine()
        self.noise_engine = NoiseResidualEngine()
        self.copy_move_detector = CopyMoveDetector()
        self.edge_analyzer = EdgeDiscontinuityAnalyzer()
        self.metadata_forensics = MetadataForensics()

    def analyze(self, image_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Executes full forensic suite on document image.
        """
        if not os.path.exists(image_path):
            return {"error": "Image file not found"}

        heatmap_path = None
        if output_dir:
            base_name = os.path.basename(image_path)
            heatmap_path = os.path.join(output_dir, f"ela_{base_name}")

        # 1. Run ELA
        ela_res = self.ela_engine.analyze(image_path, output_heatmap_path=heatmap_path)

        # 2. Run Noise Residual
        noise_res = self.noise_engine.analyze(image_path)

        # 3. Run Copy-Move
        cm_res = self.copy_move_detector.analyze(image_path)

        # 4. Run Edge Boundary Analysis
        edge_res = self.edge_analyzer.analyze(image_path)

        # 5. Run Metadata Forensics
        meta_res = self.metadata_forensics.analyze(image_path)

        # Multi-signal weighted anomaly fusion
        # Weights: ELA (0.35), Noise (0.25), Copy-Move (0.20), Edge (0.15), Metadata (0.05)
        w_ela = 0.35
        w_noise = 0.25
        w_cm = 0.20
        w_edge = 0.15
        w_meta = 0.05

        composite_score = (
            ela_res.get("anomaly_score", 0.0) * w_ela +
            noise_res.get("anomaly_score", 0.0) * w_noise +
            cm_res.get("anomaly_score", 0.0) * w_cm +
            edge_res.get("anomaly_score", 0.0) * w_edge +
            meta_res.get("anomaly_score", 0.0) * w_meta
        )

        composite_score = round(min(max(float(composite_score), 0.0), 100.0), 1)

        # Build list of specific forensic flags / findings
        findings: List[Dict[str, Any]] = []

        if ela_res.get("anomaly_score", 0) >= 40.0:
            findings.append({
                "technique": "ELA",
                "severity": "HIGH" if ela_res["anomaly_score"] >= 65 else "MEDIUM",
                "score": ela_res["anomaly_score"],
                "summary": "Compression Inconsistency Detected",
                "observation": ela_res.get("observation"),
                "interpretation": ela_res.get("interpretation")
            })

        if noise_res.get("anomaly_score", 0) >= 40.0:
            findings.append({
                "technique": "NOISE_RESIDUAL",
                "severity": "HIGH" if noise_res["anomaly_score"] >= 65 else "MEDIUM",
                "score": noise_res["anomaly_score"],
                "summary": "Sensor Noise Disparity Detected",
                "observation": noise_res.get("observation"),
                "interpretation": noise_res.get("interpretation")
            })

        if cm_res.get("anomaly_score", 0) >= 40.0:
            findings.append({
                "technique": "COPY_MOVE",
                "severity": "HIGH",
                "score": cm_res["anomaly_score"],
                "summary": "Duplicated Visual Region Detected",
                "observation": cm_res.get("observation"),
                "interpretation": cm_res.get("interpretation")
            })

        if edge_res.get("anomaly_score", 0) >= 40.0:
            findings.append({
                "technique": "EDGE_BOUNDARY",
                "severity": "MEDIUM",
                "score": edge_res["anomaly_score"],
                "summary": "Boundary Gradient Discontinuity Detected",
                "observation": edge_res.get("observation"),
                "interpretation": edge_res.get("interpretation")
            })

        if meta_res.get("editing_software_detected"):
            findings.append({
                "technique": "METADATA",
                "severity": "HIGH",
                "score": meta_res["anomaly_score"],
                "summary": f"Manipulation Software Tagged ({meta_res.get('software_signature')})",
                "observation": meta_res.get("observation"),
                "interpretation": meta_res.get("interpretation")
            })

        verdict = (
            "FORENSIC_ANOMALIES_DETECTED"
            if composite_score >= 40.0 else
            "NO_SIGNIFICANT_TAMPERING_DETECTED"
        )

        recommendation = (
            "Forensic evidence indicates digital tampering or image splicing. Manual secondary inspection required."
            if composite_score >= 40.0 else
            "Forensic signals are within normal baseline boundaries."
        )

        return {
            "pipeline_version": self.version,
            "composite_tamper_score": composite_score,
            "verdict": verdict,
            "recommendation": recommendation,
            "findings_count": len(findings),
            "findings": findings,
            "heatmap_path": heatmap_path,
            "signals": {
                "ela": ela_res,
                "noise_residual": noise_res,
                "copy_move": cm_res,
                "edge_analysis": edge_res,
                "metadata": meta_res
            }
        }
