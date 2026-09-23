"""
SatyaScan Explainable Risk Fusion Engine
Performs calibrated weighted fusion of independent forensic, biometric,
MRZ mathematical, and document rule signals to generate an explainable risk score
with explicit contributing reasons and officer recommendations.
"""

from typing import Dict, Any, List, Optional


class RiskEngine:
    """
    Decision-support risk fusion engine.
    Fuses multiple independent verification signals into an explainable 0–100 risk score.
    Never declares a person fake; frames all outcomes as operational risk levels.
    """

    def __init__(self):
        self.version = "RiskFusion-v1.2"
        # Configurable signal weight factors
        self.weights = {
            "mrz_check_digits": 0.22,
            "viz_mrz_consistency": 0.25,
            "tamper_forensics": 0.20,
            "face_verification": 0.18,
            "document_rules": 0.10,
            "quality_penalty": 0.05
        }

    def compute_risk(
        self,
        quality_res: Dict[str, Any],
        mrz_res: Dict[str, Any],
        viz_mrz_findings: List[Dict[str, Any]],
        rule_findings: List[Dict[str, Any]],
        tamper_res: Dict[str, Any],
        face_res: Optional[Dict[str, Any]] = None,
        duplicate_res: Optional[Dict[str, Any]] = None,
        doc_type: str = "PASSPORT"
    ) -> Dict[str, Any]:
        """
        Computes composite risk score and synthesizes prioritized evidence reasons.
        """
        reasons: List[Dict[str, Any]] = []
        signal_breakdown: Dict[str, float] = {}

        # 1. MRZ Check Digit Signal (0 - 100)
        mrz_score = 0.0
        if mrz_res.get("parsed"):
            checks = mrz_res.get("check_digits", {})
            failed_checks = [k for k, v in checks.items() if not v.get("valid")]
            if failed_checks:
                mrz_score = 40.0 + min(len(failed_checks) * 20.0, 60.0)
                names_str = ", ".join(k.replace('_', ' ').title() for k in failed_checks)
                reasons.append({
                    "category": "MRZ_CHECKSUM",
                    "severity": "CRITICAL" if "composite" in failed_checks else "HIGH",
                    "points": round(mrz_score * self.weights["mrz_check_digits"], 1),
                    "summary": f"MRZ Checksum Failure ({names_str})",
                    "detail": "Mathematical 7-3-1 check digit validation failed on machine-readable zone.",
                    "action": "Inspect document under UV/IR scanner for physical page alteration."
                })
        elif doc_type == "PASSPORT":
            mrz_score = 25.0
            reasons.append({
                "category": "MRZ_CHECKSUM",
                "severity": "MEDIUM",
                "points": round(mrz_score * self.weights["mrz_check_digits"], 1),
                "summary": "MRZ Missing or Unreadable",
                "detail": "Document lacks a readable 2-line machine-readable zone.",
                "action": "Manual visual examination required."
            })
        else:
            # For non-passport (e.g. Visa vignette without MRZ), no MRZ penalty
            mrz_score = 0.0
        signal_breakdown["mrz_integrity"] = round(mrz_score, 1)

        # 2. VIZ vs MRZ Cross-Check Consistency (0 - 100)
        viz_score = 0.0
        for f in viz_mrz_findings:
            sev = f.get("severity", "MEDIUM")
            pts = 75.0 if sev == "CRITICAL" else 45.0 if sev == "HIGH" else 20.0
            viz_score = max(viz_score, pts)
            reasons.append({
                "category": "VIZ_MRZ_CROSS_CHECK",
                "severity": sev,
                "points": round(pts * self.weights["viz_mrz_consistency"], 1),
                "summary": f"Field Inconsistency: {f.get('field', '').replace('_', ' ').title()}",
                "detail": f.get("message", "Visual field does not match machine-readable record."),
                "action": "Flag for supervisor review for date or number tampering."
            })
        signal_breakdown["viz_mrz_consistency"] = round(viz_score, 1)

        # 3. Tampering Forensics Signal (0 - 100)
        tamper_composite = tamper_res.get("composite_tamper_score", 0.0)
        if tamper_composite >= 35.0:
            for tf in tamper_res.get("findings", []):
                reasons.append({
                    "category": "FORENSICS",
                    "severity": tf.get("severity", "HIGH"),
                    "points": round(tf.get("score", 0.0) * (self.weights["tamper_forensics"] / max(len(tamper_res.get("findings", [1])), 1)), 1),
                    "summary": tf.get("summary", "Forensic Anomaly Detected"),
                    "detail": tf.get("observation", "Inconsistency in image compression, residual noise, or keypoints."),
                    "action": "Conduct forensic examination using magnification and spectral comparator."
                })
        signal_breakdown["tamper_forensics"] = round(tamper_composite, 1)

        # 4. Face Verification Signal (0 - 100)
        face_score = 0.0
        if face_res and (face_res.get("decision_state") or face_res.get("verification_result")):
            dstate = (face_res.get("decision_state") or face_res.get("verification_result") or "").upper()
            sim = float(face_res.get("similarity_score", 0.0) or 0.0)
            if dstate in ["VERIFIED_MISMATCH", "VERIFIED MISMATCH", "MISMATCH"]:
                face_score = 85.0
                reasons.append({
                    "category": "BIOMETRIC",
                    "severity": "CRITICAL",
                    "points": round(face_score * self.weights["face_verification"], 1),
                    "summary": f"Biometric Mismatch (Similarity: {sim:.2f})",
                    "detail": "Facial comparison indicates presented face diverges from document portrait.",
                    "action": "Secondary physical identity verification required."
                })
            elif dstate in ["INCONCLUSIVE", "BORDERLINE"]:
                face_score = 35.0
                reasons.append({
                    "category": "BIOMETRIC",
                    "severity": "MEDIUM",
                    "points": round(face_score * self.weights["face_verification"], 1),
                    "summary": f"Biometric Inconclusive (Similarity: {sim:.2f})",
                    "detail": "Biometric match cannot be reliably automated. Active descriptor lacks neural separation or falls in review band.",
                    "action": "Mandatory visual officer inspection of passport photo against passenger."
                })
            elif dstate in ["INPUT_FAILURE", "UNABLE_TO_VERIFY"]:
                face_score = 30.0
                reasons.append({
                    "category": "BIOMETRIC",
                    "severity": "MEDIUM",
                    "points": round(face_score * self.weights["face_verification"], 1),
                    "summary": "Facial Capture Incomplete",
                    "detail": face_res.get("reason", "Face could not be cropped or evaluated with adequate quality."),
                    "action": "Ensure traveler is positioned under neutral illumination and retake image."
                })
            elif dstate in ["VERIFIED_MATCH", "VERIFIED MATCH", "MATCH"]:
                face_score = 5.0
                app_diff = face_res.get("appearance_analysis", {}).get("appearance_difference_level", "MINIMAL") if isinstance(face_res.get("appearance_analysis"), dict) else "MINIMAL"
                if app_diff != "MINIMAL":
                    observations = face_res.get("appearance_analysis", {}).get("observations", []) if isinstance(face_res.get("appearance_analysis"), dict) else []
                    reasons.append({
                        "category": "BIOMETRIC",
                        "severity": "INFO",
                        "points": 0.0,
                        "summary": f"Appearance Variation: {app_diff}",
                        "detail": "; ".join(observations),
                        "action": "Note appearance variation on record; visual similarity consistent."
                    })
        signal_breakdown["face_verification"] = round(face_score, 1)

        # 5. Multi-Identity Reuse Signal
        dup_score = 0.0
        if duplicate_res and duplicate_res.get("duplicate_detected"):
            alert = duplicate_res.get("primary_alert", {})
            dup_score = 90.0
            reasons.append({
                "category": "MULTI_IDENTITY",
                "severity": "CRITICAL",
                "points": 25.0,  # Direct escalation
                "summary": "Multi-Identity Reuse Flagged",
                "detail": alert.get("message", "Face matches existing record under different identity."),
                "action": "Immediate border investigation referral."
            })
        signal_breakdown["multi_identity"] = round(dup_score, 1)

        # 6. Document Rules & Watchlist Findings (0 - 100)
        rules_score = 0.0
        for rf in rule_findings:
            sev = rf.get("severity", "LOW")
            pts = 85.0 if sev == "CRITICAL" else 55.0 if sev == "HIGH" else 25.0
            rules_score = max(rules_score, pts)
            reasons.append({
                "category": "RULES",
                "severity": sev,
                "points": round(pts * self.weights["document_rules"], 1),
                "summary": rf.get("name", "Document Rule Flag"),
                "detail": rf.get("message", rf.get("description", "")),
                "action": "Verify document issuance status."
            })
        signal_breakdown["document_rules"] = round(rules_score, 1)

        # 7. Quality Uncertainty Penalty
        qual_score = 0.0
        if quality_res.get("verdict") == "NEEDS_BETTER_IMAGE":
            qual_score = 60.0
            reasons.append({
                "category": "QUALITY",
                "severity": "MEDIUM",
                "points": round(qual_score * self.weights["quality_penalty"], 1),
                "summary": "Sub-Optimal Image Quality",
                "detail": "; ".join(quality_res.get("reasons", ["Image clarity insufficient"])),
                "action": "Request document re-scan under clean lighting."
            })
        signal_breakdown["quality_uncertainty"] = round(qual_score, 1)

        # Multi-factor compounding escalation:
        # If multiple independent orthogonal security dimensions fail simultaneously,
        # risk escalates above simple linear sum to reflect compounded threat likelihood.
        severe_categories = set(r.get("category") for r in reasons if r.get("severity") in ["CRITICAL", "HIGH"])
        multi_factor_escalation = 0.0
        if len(severe_categories) >= 3:
            multi_factor_escalation = 25.0
        elif len(severe_categories) >= 2:
            multi_factor_escalation = 15.0

        # Weighted composite score computation
        raw_risk = (
            mrz_score * self.weights["mrz_check_digits"] +
            viz_score * self.weights["viz_mrz_consistency"] +
            tamper_composite * self.weights["tamper_forensics"] +
            face_score * self.weights["face_verification"] +
            rules_score * self.weights["document_rules"] +
            qual_score * self.weights["quality_penalty"] +
            (dup_score * 0.20 if dup_score > 0 else 0.0) +
            multi_factor_escalation
        )

        final_risk = round(min(max(raw_risk, 0.0), 100.0), 1)

        # Map to Risk Bands
        if final_risk < 30.0:
            band = "LOW"
            recommendation = "Routine Clearance Permitted. Document passes automated integrity checks."
        elif final_risk < 60.0:
            band = "MEDIUM"
            recommendation = "Additional Verification Recommended. Minor inconsistencies require routine officer review."
        elif final_risk < 80.0:
            band = "HIGH"
            recommendation = "Manual Secondary Verification Required. Significant discrepancies or tampering indicators observed."
        else:
            band = "CRITICAL"
            recommendation = "Escalated Supervisor Intervention Required. Multiple critical integrity or biometric failures detected."

        # Sort reasons by severity order
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        sorted_reasons = sorted(reasons, key=lambda r: sev_order.get(r.get("severity", "LOW"), 5))

        return {
            "engine_version": self.version,
            "risk_score": final_risk,
            "risk_band": band,
            "recommendation": recommendation,
            "total_reasons_count": len(sorted_reasons),
            "reasons": sorted_reasons,
            "signal_breakdown": signal_breakdown,
            "weights_used": self.weights,
            "disclaimer": "AI-assisted decision support. The system does not decide legal status. Final authority resides with immigration officers."
        }
