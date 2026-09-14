"""
SatyaScan Master Screening Orchestrator
Executes the full automated border screening pipeline:
Quality Gate -> OCR -> MRZ -> Validation Engine -> Tamper Forensics ->
Face Verification -> FAISS Multi-Identity Search -> Risk Fusion -> DB Persistence -> SHA-256 Audit Trail.
"""

from typing import Dict, Any, Optional
import os
import time
import uuid
from datetime import datetime, timezone
import json
import cv2
import numpy as np
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import mask_document_number, mask_full_name, mask_date_of_birth
from backend.app.models.database import (
    Screening, ExtractedField, ValidationFinding, TamperFinding,
    FaceResult, IdentityMatch, ReferenceWatchlist, AuditEvent
)
from backend.app.services.audit_service import AuditService
from ai.quality.quality_gate import DocumentQualityGate
from ai.ocr.ocr_engine import OCREngine
from ai.mrz.mrz_parser import MRZParser
from ai.tamper.pipeline import TamperForensicsPipeline
from ai.face.face_verifier import FaceVerifier
from ai.duplicate.indexer import MultiIdentityIndexer
from ai.risk.risk_engine import RiskEngine


class ScreeningOrchestrator:
    """
    Singleton orchestrator coordinating all AI engines and database operations.
    """

    def __init__(self):
        self.quality_gate = DocumentQualityGate()
        self.ocr_engine = OCREngine()
        self.tamper_pipeline = TamperForensicsPipeline()
        self.face_verifier = FaceVerifier()
        self.identity_indexer = MultiIdentityIndexer()
        self.risk_engine = RiskEngine()
        self._seed_synthetic_gallery()

    def _seed_synthetic_gallery(self):
        """Seeds FAISS index with initial synthetic identities for duplicate detection."""
        # Add a synthetic watchlist/gallery entry: RAHUL VERMA (DEMO-006)
        rng = np.random.RandomState(42)
        emb1 = rng.randn(512).astype(np.float32)
        emb1 /= np.linalg.norm(emb1)
        self.identity_indexer.add_identity(
            doc_id="DEMO-006",
            name="RAHUL VERMA",
            embedding=emb1,
            doc_type="PASSPORT",
            status="SUSPENDED"
        )

        emb2 = rng.randn(512).astype(np.float32)
        emb2 /= np.linalg.norm(emb2)
        self.identity_indexer.add_identity(
            doc_id="DEMO-WATCH-01",
            name="VIKRAM SINGH",
            embedding=emb2,
            doc_type="PASSPORT",
            status="LOOKOUT_CIRCULAR"
        )

    def process_screening(
        self,
        db: Session,
        doc_image_path: str,
        live_image_path: Optional[str] = None,
        operator_id: Optional[int] = None,
        doc_type: str = "PASSPORT"
    ) -> Dict[str, Any]:
        """
        Executes end-to-end screening workflow.
        """
        start_time = time.time()
        screening_id = f"SAT-2026-{uuid.uuid4().hex[:8].upper()}"

        # 0. Initial Audit Event: Upload
        AuditService.record_event(
            db, screening_id, "DOCUMENT_UPLOADED",
            {"file": os.path.basename(doc_image_path), "doc_type": doc_type}
        )

        # 1. Quality Gate
        quality_res = self.quality_gate.assess_image(doc_image_path)
        AuditService.record_event(
            db, screening_id, "QUALITY_GATE_EVALUATED",
            {"verdict": quality_res["verdict"], "score": quality_res["overall_score"]}
        )

        # 2. OCR Extraction
        ocr_res = self.ocr_engine.process_image(doc_image_path)
        extracted_fields_dict = ocr_res.get("extracted_fields", {})
        AuditService.record_event(
            db, screening_id, "OCR_EXTRACTION_COMPLETED",
            {"total_lines": ocr_res.get("total_lines_detected"), "engine": ocr_res.get("engine")}
        )

        # 3. MRZ Extraction & Check Digits
        # Find MRZ candidate lines from OCR or attempt image bottom detection
        mrz_candidates = ocr_res.get("mrz_candidate_lines", [])
        mrz_res: Dict[str, Any] = {"parsed": False}

        if len(mrz_candidates) >= 2:
            mrz_res = MRZParser.parse_td3(mrz_candidates[-2], mrz_candidates[-1])
        else:
            # Fallback: scan all lines for TD3 patterns
            raw_lines = [r["text"] for r in ocr_res.get("raw_lines", [])]
            for i in range(len(raw_lines) - 1):
                t1 = raw_lines[i].replace(" ", "").upper()
                t2 = raw_lines[i+1].replace(" ", "").upper()
                if (t1.startswith("P<") or t1.count("<") >= 4) and len(t2) >= 25:
                    mrz_res = MRZParser.parse_td3(raw_lines[i], raw_lines[i+1])
                    break

        AuditService.record_event(
            db, screening_id, "MRZ_VALIDATION_COMPLETED",
            {"parsed": mrz_res.get("parsed", False), "all_checks_passed": mrz_res.get("all_checks_passed", False)}
        )

        # 4. VIZ vs MRZ Cross-Check Findings
        viz_mrz_findings = MRZParser.cross_validate_viz(mrz_res, {
            "document_number": extracted_fields_dict.get("passport_number", {}).get("value") if extracted_fields_dict.get("passport_number") else None,
            "date_of_birth": extracted_fields_dict.get("date_of_birth", {}).get("value") if extracted_fields_dict.get("date_of_birth") else None,
            "date_of_expiry": extracted_fields_dict.get("date_of_expiry", {}).get("value") if extracted_fields_dict.get("date_of_expiry") else None,
            "full_name": extracted_fields_dict.get("full_name", {}).get("value") if extracted_fields_dict.get("full_name") else None
        })

        # 5. Document Rules Engine (Expiry, DOB Plausibility, Watchlist)
        rule_findings: List[Dict[str, Any]] = []

        # Document Expiry Check
        exp_date_str = None
        if mrz_res.get("date_of_expiry"):
            exp_date_str = mrz_res["date_of_expiry"]
        elif extracted_fields_dict.get("date_of_expiry"):
            exp_date_str = extracted_fields_dict["date_of_expiry"]["value"]

        if exp_date_str:
            norm_exp = MRZParser._normalize_date_string(exp_date_str) or exp_date_str
            try:
                exp_dt = datetime.strptime(norm_exp[:10], "%Y-%m-%d")
                if exp_dt < datetime.now():
                    rule_findings.append({
                        "rule_id": "DOCUMENT_NOT_EXPIRED",
                        "severity": "HIGH",
                        "field": "date_of_expiry",
                        "expected": "Future Date",
                        "observed": norm_exp,
                        "message": f"Travel document expired on {norm_exp}. Invalid for border crossing.",
                        "classification": "OFFICIAL_STANDARD"
                    })
            except Exception:
                pass

        # Watchlist Check
        doc_num_to_check = (
            (mrz_res.get("document_number") if mrz_res.get("parsed") else None) or
            (extracted_fields_dict.get("passport_number", {}).get("value") if extracted_fields_dict.get("passport_number") else None)
        )
        if doc_num_to_check:
            clean_num = doc_num_to_check.replace(" ", "").upper()
            w_entry = db.query(ReferenceWatchlist).filter(ReferenceWatchlist.document_id == clean_num).first()
            if w_entry:
                rule_findings.append({
                    "rule_id": "WATCHLIST_MATCH",
                    "severity": "CRITICAL",
                    "field": "document_number",
                    "expected": "CLEAR",
                    "observed": f"FLAGGED ({w_entry.risk_category})",
                    "message": f"Document ID matched prototype watchlist: {w_entry.reason} (Subject: {w_entry.full_name})",
                    "classification": "PROTOTYPE_RULE"
                })

        AuditService.record_event(
            db, screening_id, "RULES_VALIDATION_COMPLETED",
            {"viz_findings_count": len(viz_mrz_findings), "rule_findings_count": len(rule_findings)}
        )

        # 6. Multi-Signal Tampering Forensics
        tamper_res = self.tamper_pipeline.analyze(doc_image_path, output_dir=settings.HEATMAP_DIR)
        AuditService.record_event(
            db, screening_id, "TAMPER_FORENSICS_COMPLETED",
            {"score": tamper_res.get("composite_tamper_score"), "findings": tamper_res.get("findings_count")}
        )

        # 7. Face Verification
        face_res = None
        if live_image_path and os.path.exists(live_image_path):
            face_res = self.face_verifier.verify(doc_image_path, live_image_path)
            AuditService.record_event(
                db, screening_id, "FACE_VERIFICATION_COMPLETED",
                {
                    "result": face_res.get("verification_result"),
                    "similarity": face_res.get("similarity_score"),
                    "appearance": face_res.get("appearance_analysis", {}).get("appearance_difference_level")
                }
            )

        # 8. Duplicate / Multi-Identity Search
        dup_res = None
        if face_res and face_res.get("doc_face_box") and face_res.get("verification_result") != "UNABLE_TO_VERIFY":
            # Extract live face embedding
            live_img = cv2.imread(live_image_path)
            live_cropped, _, _ = self.face_verifier.detect_and_crop_face(live_img)
            if live_cropped is not None:
                live_emb = self.face_verifier.extract_embedding(live_cropped)
                dup_res = self.identity_indexer.search_duplicate(
                    query_embedding=live_emb,
                    current_doc_id=doc_num_to_check
                )
                AuditService.record_event(
                    db, screening_id, "IDENTITY_SEARCH_COMPLETED",
                    {"duplicate_detected": dup_res.get("duplicate_detected")}
                )

        # 9. Explainable Risk Fusion
        risk_res = self.risk_engine.compute_risk(
            quality_res=quality_res,
            mrz_res=mrz_res,
            viz_mrz_findings=viz_mrz_findings,
            rule_findings=rule_findings,
            tamper_res=tamper_res,
            face_res=face_res,
            duplicate_res=dup_res
        )

        AuditService.record_event(
            db, screening_id, "RISK_SCORE_GENERATED",
            {"score": risk_res["risk_score"], "band": risk_res["risk_band"]}
        )

        # 10. Persist to Database
        latency_ms = round((time.time() - start_time) * 1000.0, 1)
        raw_doc_id = (
            doc_num_to_check or
            (extracted_fields_dict.get("passport_number", {}).get("value") if extracted_fields_dict.get("passport_number") else "UNKNOWN")
        )
        masked_id = mask_document_number(raw_doc_id)

        screening_rec = Screening(
            id=screening_id,
            operator_id=operator_id,
            document_type=doc_type,
            masked_document_id=masked_id,
            status="COMPLETED" if risk_res["risk_band"] == "LOW" else "MANUAL_REVIEW_REQUIRED",
            risk_score=risk_res["risk_score"],
            risk_band=risk_res["risk_band"],
            recommendation=risk_res["recommendation"],
            doc_image_path=doc_image_path,
            live_image_path=live_image_path,
            ela_heatmap_path=tamper_res.get("heatmap_path"),
            execution_latency_ms=latency_ms
        )
        db.add(screening_rec)

        # Save Extracted Fields
        field_records = []
        for fname, val_dict in extracted_fields_dict.items():
            if val_dict:
                v_val = val_dict.get("value")
                m_val = mrz_res.get(fname) if mrz_res.get("parsed") else None
                # Check status
                status_val = "MATCH"
                if m_val and v_val and str(v_val).upper() != str(m_val).upper():
                    status_val = "MISMATCH"

                bbox = val_dict.get("bounding_box")
                bbox_json = json.dumps(bbox) if bbox else None

                f_rec = ExtractedField(
                    screening_id=screening_id,
                    field_name=fname,
                    visual_value=str(v_val) if v_val is not None else None,
                    mrz_value=str(m_val) if m_val is not None else None,
                    confidence=val_dict.get("confidence", 1.0),
                    match_status=status_val,
                    bounding_box_json=bbox_json
                )
                db.add(f_rec)
                field_records.append({
                    "field_name": fname,
                    "visual_value": str(v_val) if v_val is not None else None,
                    "mrz_value": str(m_val) if m_val is not None else None,
                    "confidence": val_dict.get("confidence", 1.0),
                    "match_status": status_val,
                    "bounding_box": bbox
                })

        # Save Validation Findings
        all_val_findings = viz_mrz_findings + rule_findings
        val_records = []
        for vf in all_val_findings:
            cat = vf.get("category", "STANDARDS_COMPLIANCE")
            vf_rec = ValidationFinding(
                screening_id=screening_id,
                rule_id=vf["rule_id"],
                category=cat,
                severity=vf.get("severity", "MEDIUM"),
                field=vf.get("field"),
                expected=str(vf.get("expected")),
                observed=str(vf.get("observed")),
                message=vf.get("message", ""),
                classification=vf.get("classification", "OFFICIAL_STANDARD")
            )
            db.add(vf_rec)
            vf_dict = dict(vf)
            vf_dict["category"] = cat
            val_records.append(vf_dict)

        # Save Tamper Findings
        tamper_records = []
        for tf in tamper_res.get("findings", []):
            tf_rec = TamperFinding(
                screening_id=screening_id,
                technique=tf.get("technique", "FORENSIC"),
                severity=tf.get("severity", "MEDIUM"),
                score=tf.get("score", 0.0),
                summary=tf.get("summary", ""),
                observation=tf.get("observation", ""),
                interpretation=tf.get("interpretation", "")
            )
            db.add(tf_rec)
            tamper_records.append(tf)

        # Save Face Result
        face_record = None
        if face_res and face_res.get("verification_result") != "UNABLE_TO_VERIFY":
            fr_rec = FaceResult(
                screening_id=screening_id,
                metric=face_res.get("metric", "Cosine Similarity"),
                similarity_score=face_res.get("similarity_score", 0.0),
                threshold=face_res.get("threshold", 0.65),
                verification_result=face_res.get("verification_result", "MATCH"),
                appearance_level=face_res.get("appearance_analysis", {}).get("appearance_difference_level", "MINIMAL"),
                observations_json=json.dumps(face_res.get("appearance_analysis", {}).get("observations", [])),
                recommendation=face_res.get("recommendation", "")
            )
            db.add(fr_rec)
            face_record = {
                "metric": face_res.get("metric", "Cosine Similarity"),
                "similarity_score": face_res.get("similarity_score", 0.0),
                "threshold": face_res.get("threshold", 0.65),
                "verification_result": face_res.get("verification_result", "MATCH"),
                "appearance_level": face_res.get("appearance_analysis", {}).get("appearance_difference_level", "MINIMAL"),
                "observations": face_res.get("appearance_analysis", {}).get("observations", []),
                "recommendation": face_res.get("recommendation", "")
            }

        # Save Identity Matches
        identity_records = []
        if dup_res and dup_res.get("matches"):
            for m in dup_res["matches"]:
                if m.get("similarity", 0) >= 0.70:
                    im_rec = IdentityMatch(
                        screening_id=screening_id,
                        matched_document_id=m["document_id"],
                        matched_name=m["name"],
                        similarity=m["similarity"],
                        alert_message=f"Biometric similarity {m['similarity']} matches gallery record {m['document_id']}"
                    )
                    db.add(im_rec)
                    identity_records.append({
                        "matched_document_id": m["document_id"],
                        "matched_name": m["name"],
                        "similarity": m["similarity"],
                        "alert_message": im_rec.alert_message
                    })

        db.commit()

        # Fetch Audit Trail
        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        return {
            "id": screening_id,
            "created_at": datetime.now(timezone.utc),
            "document_type": doc_type,
            "masked_document_id": masked_id,
            "status": screening_rec.status,
            "risk_score": risk_res["risk_score"],
            "risk_band": risk_res["risk_band"],
            "recommendation": risk_res["recommendation"],
            "execution_latency_ms": latency_ms,
            "doc_image_url": f"/api/v1/screenings/media/{screening_id}/doc",
            "live_image_url": f"/api/v1/screenings/media/{screening_id}/live" if live_image_path else None,
            "ela_heatmap_url": f"/api/v1/screenings/media/{screening_id}/heatmap" if tamper_res.get("heatmap_path") else None,
            "quality_assessment": quality_res,
            "extracted_fields": field_records,
            "mrz_data": mrz_res if mrz_res.get("parsed") else None,
            "validation_findings": val_records,
            "tamper_findings": tamper_records,
            "tamper_summary": tamper_res,
            "face_result": face_record,
            "identity_matches": identity_records,
            "risk_reasons": risk_res["reasons"],
            "signal_breakdown": risk_res["signal_breakdown"],
            "audit_trail": [
                {
                    "id": a.id,
                    "timestamp": a.timestamp,
                    "actor": a.actor,
                    "event_type": a.event_type,
                    "payload_hash": a.payload_hash,
                    "previous_hash": a.previous_hash,
                    "event_hash": a.event_hash
                }
                for a in audit_events
            ]
        }


# Singleton instance
screening_orchestrator = ScreeningOrchestrator()
