"""
SatyaScan Master Screening Orchestrator
Executes the full automated border screening pipeline:
Security & Quality Gate -> Document Classifier Gate ->
Dedicated Passport Pipeline (ICAO Doc 9303 TD3 MRZ, 7-3-1 checks, VIZ cross-validation, forensics, biometrics, FAISS)
OR Dedicated Visa Pipeline (Visa rules, validity date checks, stay duration, passport cross-check, forensics)
-> Risk Fusion -> DB Persistence -> SHA-256 Cryptographic Audit Trail.
Guarantees deterministic terminal states: COMPLETED, QUALITY_REJECTED, UNSUPPORTED_DOCUMENT,
MANUAL_REVIEW_REQUIRED, UNABLE_TO_VERIFY, or FAILED.
"""

from typing import Dict, Any, Optional, List
import os
import time
import uuid
from datetime import datetime, timezone
import json
import re
import cv2
import numpy as np
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger("satyascan.orchestrator")

from backend.app.core.config import settings
from backend.app.core.security import mask_document_number, mask_full_name, mask_date_of_birth
from backend.app.models.database import (
    Screening, ExtractedField, ValidationFinding, TamperFinding,
    FaceResult, IdentityMatch, ReferenceWatchlist, AuditEvent
)
from backend.app.services.audit_service import AuditService
from ai.quality.quality_gate import DocumentQualityGate
from ai.classifier.document_classifier import DocumentClassifier
from ai.ocr.ocr_engine import OCREngine
from ai.mrz.mrz_parser import MRZParser
from ai.visa.visa_parser import VisaParser
from ai.tamper.pipeline import TamperForensicsPipeline
from ai.face.face_verifier import FaceVerifier
from ai.duplicate.indexer import MultiIdentityIndexer
from ai.risk.risk_engine import RiskEngine
from backend.app.services.fabric_service import FabricAnchorService


class ScreeningOrchestrator:
    """
    Singleton orchestrator coordinating all AI engines and database operations.
    """

    def __init__(self):
        self.quality_gate = DocumentQualityGate()
        self.document_classifier = DocumentClassifier()
        self.ocr_engine = OCREngine()
        self.tamper_pipeline = TamperForensicsPipeline()
        self.face_verifier = FaceVerifier()
        dim = getattr(getattr(self.face_verifier, "provider", None), "embedding_dim", getattr(self.face_verifier, "EMBEDDING_DIM", 128))
        self.identity_indexer = MultiIdentityIndexer(embedding_dim=dim)
        self.risk_engine = RiskEngine()
        self._seed_synthetic_gallery()

    def _seed_synthetic_gallery(self):
        """Seeds FAISS index with initial synthetic identities for duplicate detection."""
        rng = np.random.RandomState(42)
        dim = self.identity_indexer.embedding_dim
        emb1 = rng.randn(dim).astype(np.float32)
        emb1 /= np.linalg.norm(emb1)
        self.identity_indexer.add_identity(
            doc_id="DEMO-006",
            name="RAHUL VERMA",
            embedding=emb1,
            doc_type="PASSPORT",
            status="SUSPENDED"
        )

        emb2 = rng.randn(dim).astype(np.float32)
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
        doc_type: str = "PASSPORT",
        checkpoint_id: Optional[str] = None,
        checkpoint_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end screening workflow with robust exception handling and guaranteed terminal state.
        """
        start_time = time.time()
        screening_id = f"SAT-2026-{uuid.uuid4().hex[:8].upper()}"

        try:
            return self._execute_pipeline(
                db=db,
                screening_id=screening_id,
                start_time=start_time,
                doc_image_path=doc_image_path,
                live_image_path=live_image_path,
                operator_id=operator_id,
                requested_doc_type=doc_type,
                checkpoint_id=checkpoint_id,
                checkpoint_name=checkpoint_name
            )
        except Exception as exc:
            db.rollback()
            latency_ms = round((time.time() - start_time) * 1000.0, 1)
            logger.error(f"[SatyaScan Screening] Pipeline failure for {screening_id}: {exc}", exc_info=True)

            try:
                fail_rec = Screening(
                    id=screening_id,
                    operator_id=operator_id,
                    checkpoint_id=checkpoint_id,
                    checkpoint_name=checkpoint_name,
                    document_type=doc_type,
                    masked_document_id="UNKNOWN",
                    status="FAILED",
                    risk_score=75.0,
                    risk_band="HIGH",
                    recommendation="Screening could not be completed due to an internal processing error. Manual inspection required.",
                    doc_image_path=doc_image_path,
                    live_image_path=live_image_path,
                    ocr_engine=None,
                    execution_latency_ms=latency_ms
                )
                db.add(fail_rec)
                AuditService.record_event(
                    db, screening_id, "SCREENING_FAILED",
                    {"status": "FAILED", "code": "PIPELINE_ERROR", "checkpoint_id": checkpoint_id}
                )
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"[SatyaScan Screening] Could not persist failure record: {db_err}")

            raise HTTPException(
                status_code=500,
                detail="Screening could not be completed due to an internal processing error. Please retry or contact the administrator."
            )

    def _execute_pipeline(
        self,
        db: Session,
        screening_id: str,
        start_time: float,
        doc_image_path: str,
        live_image_path: Optional[str] = None,
        operator_id: Optional[int] = None,
        requested_doc_type: str = "PASSPORT",
        checkpoint_id: Optional[str] = None,
        checkpoint_name: Optional[str] = None
    ) -> Dict[str, Any]:
        # 0. Initial Audit Event: Upload
        AuditService.record_event(
            db, screening_id, "DOCUMENT_UPLOADED",
            {
                "file": os.path.basename(doc_image_path),
                "requested_type": requested_doc_type,
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": checkpoint_name
            }
        )

        # 1. Quality Gate Evaluation
        quality_res = self.quality_gate.assess_image(doc_image_path)
        AuditService.record_event(
            db, screening_id, "QUALITY_GATE_EVALUATED",
            {"verdict": quality_res["verdict"], "score": quality_res["overall_score"]}
        )

        # If quality is strictly rejected (corrupt/empty/degraded)
        if quality_res.get("verdict") in ["REJECTED"] or not quality_res.get("is_acceptable", True):
            return self._handle_quality_rejection(
                db=db,
                screening_id=screening_id,
                start_time=start_time,
                doc_image_path=doc_image_path,
                live_image_path=live_image_path,
                operator_id=operator_id,
                checkpoint_id=checkpoint_id,
                checkpoint_name=checkpoint_name,
                doc_type=requested_doc_type,
                quality_res=quality_res
            )

        # 2. Document Classifier Gate (Verify supported document type: Passport or Visa)
        class_res = self.document_classifier.classify_image(doc_image_path)
        AuditService.record_event(
            db, screening_id, "DOCUMENT_CLASSIFIED",
            {
                "verdict": class_res["verdict"],
                "detected_type": class_res["detected_type"],
                "confidence": class_res["confidence"]
            }
        )

        if not class_res.get("is_supported", False):
            return self._handle_unsupported_document(
                db=db,
                screening_id=screening_id,
                start_time=start_time,
                doc_image_path=doc_image_path,
                live_image_path=live_image_path,
                operator_id=operator_id,
                checkpoint_id=checkpoint_id,
                checkpoint_name=checkpoint_name,
                class_res=class_res,
                quality_res=quality_res
            )

        # Active verified document type
        active_doc_type = class_res["verdict"]  # "PASSPORT" or "VISA"

        # 3. Route to dedicated pipeline
        if active_doc_type == "VISA":
            return self._execute_visa_pipeline(
                db=db,
                screening_id=screening_id,
                start_time=start_time,
                doc_image_path=doc_image_path,
                live_image_path=live_image_path,
                operator_id=operator_id,
                checkpoint_id=checkpoint_id,
                checkpoint_name=checkpoint_name,
                quality_res=quality_res
            )
        else:
            return self._execute_passport_pipeline(
                db=db,
                screening_id=screening_id,
                start_time=start_time,
                doc_image_path=doc_image_path,
                live_image_path=live_image_path,
                operator_id=operator_id,
                checkpoint_id=checkpoint_id,
                checkpoint_name=checkpoint_name,
                quality_res=quality_res
            )

    def _execute_passport_pipeline(
        self,
        db: Session,
        screening_id: str,
        start_time: float,
        doc_image_path: str,
        live_image_path: Optional[str],
        operator_id: Optional[int],
        checkpoint_id: Optional[str],
        checkpoint_name: Optional[str],
        quality_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dedicated Passport Pipeline: OCR -> TD3 MRZ -> 7-3-1 -> VIZ Cross-Check -> Forensics -> Biometrics -> FAISS."""
        # 1. OCR Extraction
        ocr_res = self.ocr_engine.process_image(doc_image_path)
        actual_engine = ocr_res.get("engine")
        extracted_fields_dict = ocr_res.get("extracted_fields", {})
        AuditService.record_event(
            db, screening_id, "OCR_EXTRACTION_COMPLETED",
            {"total_lines": ocr_res.get("total_lines_detected"), "ocr_engine": actual_engine}
        )

        # 2. MRZ Extraction & 7-3-1 Check Digits
        mrz_candidates = ocr_res.get("mrz_candidate_lines", [])
        mrz_res: Dict[str, Any] = {"parsed": False}

        if len(mrz_candidates) >= 2:
            mrz_res = MRZParser.parse_td3(mrz_candidates[-2], mrz_candidates[-1])
        else:
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

        # 3. VIZ vs MRZ Cross-Check Findings
        viz_mrz_findings = MRZParser.cross_validate_viz(mrz_res, {
            "document_number": extracted_fields_dict.get("passport_number", {}).get("value") if extracted_fields_dict.get("passport_number") else None,
            "date_of_birth": extracted_fields_dict.get("date_of_birth", {}).get("value") if extracted_fields_dict.get("date_of_birth") else None,
            "date_of_expiry": extracted_fields_dict.get("date_of_expiry", {}).get("value") if extracted_fields_dict.get("date_of_expiry") else None,
            "full_name": extracted_fields_dict.get("full_name", {}).get("value") if extracted_fields_dict.get("full_name") else None
        })

        # 4. Document Rules Engine (Expiry & Watchlist)
        rule_findings: List[Dict[str, Any]] = []
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

        # 5. Multi-Signal Tampering Forensics
        tamper_res = self.tamper_pipeline.analyze(doc_image_path, output_dir=settings.HEATMAP_DIR)
        AuditService.record_event(
            db, screening_id, "TAMPER_FORENSICS_COMPLETED",
            {"score": tamper_res.get("composite_tamper_score"), "findings": tamper_res.get("findings_count")}
        )

        # 6. Face Verification
        face_res = None
        doc_face_crop_path = None
        live_face_crop_path = None
        if live_image_path and os.path.exists(live_image_path):
            face_res = self.face_verifier.verify(doc_image_path, live_image_path)
            try:
                os.makedirs(settings.STORAGE_DIR, exist_ok=True)
                if face_res.get("doc_face_crop") is not None:
                    p = os.path.join(settings.STORAGE_DIR, f"{screening_id}_doc_face.jpg")
                    cv2.imwrite(p, face_res["doc_face_crop"])
                    doc_face_crop_path = p
                if face_res.get("live_face_crop") is not None:
                    p = os.path.join(settings.STORAGE_DIR, f"{screening_id}_live_face.jpg")
                    cv2.imwrite(p, face_res["live_face_crop"])
                    live_face_crop_path = p
            except Exception as e:
                logger.warning(f"Failed to persist face crops for {screening_id}: {e}")

            AuditService.record_event(
                db, screening_id, "FACE_VERIFICATION_COMPLETED",
                {
                    "result": face_res.get("verification_result"),
                    "similarity": face_res.get("similarity_score"),
                    "provider": face_res.get("provider"),
                    "appearance": face_res.get("appearance_analysis", {}).get("appearance_difference_level") if isinstance(face_res.get("appearance_analysis"), dict) else None
                }
            )

        # 7. Duplicate / Multi-Identity Search
        dup_res = None
        if face_res and face_res.get("doc_face_box") and face_res.get("verification_result") not in ["UNABLE_TO_VERIFY", "INPUT_FAILURE"]:
            live_img = cv2.imread(live_image_path)
            if live_img is not None:
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

        # 8. Explainable Risk Fusion
        risk_res = self.risk_engine.compute_risk(
            quality_res=quality_res,
            mrz_res=mrz_res,
            viz_mrz_findings=viz_mrz_findings,
            rule_findings=rule_findings,
            tamper_res=tamper_res,
            face_res=face_res,
            duplicate_res=dup_res,
            doc_type="PASSPORT"
        )
        AuditService.record_event(
            db, screening_id, "RISK_SCORE_GENERATED",
            {"score": risk_res["risk_score"], "band": risk_res["risk_band"]}
        )

        # 9. Determine Terminal Status & Persist
        latency_ms = round((time.time() - start_time) * 1000.0, 1)
        raw_doc_id = doc_num_to_check or "UNKNOWN"
        masked_id = mask_document_number(raw_doc_id)

        if quality_res.get("verdict") in ["REJECTED", "NEEDS_BETTER_IMAGE"]:
            terminal_status = "UNABLE_TO_VERIFY"
            terminal_rec = "Unable to verify — image quality is insufficient. Please capture a clearer document."
        elif risk_res["risk_band"] == "LOW":
            terminal_status = "COMPLETED"
            terminal_rec = risk_res["recommendation"]
        else:
            terminal_status = "MANUAL_REVIEW_REQUIRED"
            terminal_rec = risk_res["recommendation"]

        screening_rec = Screening(
            id=screening_id,
            operator_id=operator_id,
            checkpoint_id=checkpoint_id,
            checkpoint_name=checkpoint_name,
            document_type="PASSPORT",
            masked_document_id=masked_id,
            status=terminal_status,
            risk_score=risk_res["risk_score"],
            risk_band=risk_res["risk_band"],
            recommendation=terminal_rec,
            doc_image_path=doc_image_path,
            live_image_path=live_image_path,
            ela_heatmap_path=tamper_res.get("heatmap_path"),
            ocr_engine=actual_engine,
            execution_latency_ms=latency_ms
        )
        db.add(screening_rec)

        # Save Extracted Fields (Consolidating Visual VIZ and ICAO MRZ sources)
        def _match_canonical_field(f_name: str, val_v: Any, val_m: Any) -> bool:
            if val_v is None or val_m is None:
                return False
            sv = str(val_v).strip().upper()
            sm = str(val_m).strip().upper()
            if sv == sm:
                return True
            if f_name in ["date_of_birth", "date_of_expiry"]:
                nv = MRZParser._normalize_date_string(sv) or sv
                nm = MRZParser._normalize_date_string(sm) or sm
                return nv == nm
            if f_name == "nationality":
                if (sv in ["INDIAN", "IND"] and sm in ["INDIAN", "IND"]) or sv.startswith(sm) or sm.startswith(sv):
                    return True
            if f_name == "sex":
                if (sv in ["M", "MALE"] and sm in ["M", "MALE"]) or (sv in ["F", "FEMALE"] and sm in ["F", "FEMALE"]):
                    return True
            if f_name == "full_name":
                t_v = set(re.findall(r'[A-Z]+', sv))
                t_m = set(re.findall(r'[A-Z]+', sm))
                if t_v and t_m and (t_v == t_m or (len(t_v & t_m) / max(len(t_v), len(t_m)) >= 0.7)):
                    return True
            if f_name == "document_number":
                cv = re.sub(r'[^A-Z0-9]', '', sv)
                cm = re.sub(r'[^A-Z0-9]', '', sm)
                return cv == cm
            if f_name == "document_type":
                if sv in ["PASSPORT", "P"] and sm in ["PASSPORT", "P"]:
                    return True
            return False

        canonical_fields = ["document_number", "full_name", "date_of_birth", "nationality", "date_of_expiry", "sex", "document_type"]
        field_records = []
        handled_keys = set()

        for fname in canonical_fields:
            handled_keys.add(fname)
            v_info = extracted_fields_dict.get(fname)
            if not v_info and fname == "document_number":
                v_info = extracted_fields_dict.get("passport_number")
                handled_keys.add("passport_number")
            elif not v_info and fname == "full_name":
                s_name = extracted_fields_dict.get("surname", {}).get("value") if extracted_fields_dict.get("surname") else ""
                g_name = extracted_fields_dict.get("given_names", {}).get("value") if extracted_fields_dict.get("given_names") else ""
                if s_name or g_name:
                    v_info = {"value": f"{g_name} {s_name}".strip(), "confidence": 0.85, "bounding_box": None}
                    handled_keys.add("surname")
                    handled_keys.add("given_names")
            elif not v_info and fname == "date_of_birth":
                v_info = extracted_fields_dict.get("dob")
                handled_keys.add("dob")
            elif not v_info and fname == "date_of_expiry":
                v_info = extracted_fields_dict.get("expiry")
                handled_keys.add("expiry")
            elif not v_info and fname == "sex":
                v_info = extracted_fields_dict.get("gender")
                handled_keys.add("gender")

            v_val = v_info.get("value") if (v_info and isinstance(v_info, dict)) else (v_info if isinstance(v_info, str) else None)

            m_val = None
            if mrz_res and mrz_res.get("parsed"):
                m_val = mrz_res.get(fname)
                if not m_val and fname == "document_number":
                    m_val = mrz_res.get("document_number") or mrz_res.get("passport_number")
                elif not m_val and fname == "document_type":
                    m_val = mrz_res.get("document_code")

            if v_val is not None or m_val is not None:
                if v_val is not None and m_val is not None:
                    is_match = _match_canonical_field(fname, v_val, m_val)
                    status_val = "MATCH" if is_match else "MISMATCH"
                elif m_val is not None:
                    status_val = "MRZ_ONLY"
                else:
                    status_val = "VIZ_ONLY"

                bbox = v_info.get("bounding_box") if (v_info and isinstance(v_info, dict)) else None
                conf = v_info.get("confidence", 0.90) if (v_info and isinstance(v_info, dict)) else 0.95

                f_rec = ExtractedField(
                    screening_id=screening_id,
                    field_name=fname,
                    visual_value=str(v_val) if v_val is not None else None,
                    mrz_value=str(m_val) if m_val is not None else None,
                    confidence=float(conf) if conf is not None else 1.0,
                    ocr_engine=actual_engine,
                    validation="VALID" if status_val in ["MATCH", "MRZ_ONLY", "VIZ_ONLY"] else "INVALID",
                    match_status=status_val,
                    bounding_box_json=json.dumps(bbox) if bbox else None
                )
                db.add(f_rec)
                canonical_val = str(v_val) if v_val is not None else (str(m_val) if m_val is not None else None)
                field_records.append({
                    "field_name": fname,
                    "field_value": canonical_val,
                    "visual_value": str(v_val) if v_val is not None else None,
                    "mrz_value": str(m_val) if m_val is not None else None,
                    "confidence": float(conf) if conf is not None else 1.0,
                    "ocr_engine": actual_engine,
                    "validation": f_rec.validation,
                    "match_status": status_val,
                    "bounding_box": bbox
                })

        # Also capture any remaining fields from visual OCR not in canonical set
        for fname, val_dict in extracted_fields_dict.items():
            if fname not in handled_keys and val_dict and val_dict.get("value"):
                v_val = val_dict.get("value")
                bbox = val_dict.get("bounding_box")
                f_rec = ExtractedField(
                    screening_id=screening_id,
                    field_name=fname,
                    visual_value=str(v_val) if v_val is not None else None,
                    mrz_value=None,
                    confidence=val_dict.get("confidence", 1.0) or 1.0,
                    ocr_engine=actual_engine,
                    validation="VALID",
                    match_status="VIZ_ONLY",
                    bounding_box_json=json.dumps(bbox) if bbox else None
                )
                db.add(f_rec)
                field_records.append({
                    "field_name": fname,
                    "field_value": str(v_val) if v_val is not None else None,
                    "visual_value": str(v_val) if v_val is not None else None,
                    "mrz_value": None,
                    "confidence": val_dict.get("confidence", 1.0) or 1.0,
                    "ocr_engine": actual_engine,
                    "validation": f_rec.validation,
                    "match_status": "VIZ_ONLY",
                    "bounding_box": bbox
                })

        # Save Findings
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

        face_record = None
        if face_res:
            vr = face_res.get("verification_result", "UNABLE_TO_VERIFY")
            fr_rec = FaceResult(
                screening_id=screening_id,
                metric=face_res.get("metric", "Cosine Similarity"),
                similarity_score=float(face_res.get("similarity_score", 0.0) or 0.0),
                threshold=float(face_res.get("threshold", 0.68) or 0.68),
                verification_result=vr,
                appearance_level=face_res.get("appearance_analysis", {}).get("appearance_difference_level", "MINIMAL") if isinstance(face_res.get("appearance_analysis"), dict) else "MINIMAL",
                observations_json=json.dumps(face_res.get("appearance_analysis", {}).get("observations", [])) if isinstance(face_res.get("appearance_analysis"), dict) else "[]",
                recommendation=face_res.get("recommendation", "") or face_res.get("reason", ""),
                provider=face_res.get("provider", "SFace-ResNet-128d-v1.0"),
                quality_status=face_res.get("live_quality", {}).get("status", "GOOD") if isinstance(face_res.get("live_quality"), dict) else "GOOD",
                pad_status=face_res.get("presentation_attack", {}).get("status", "NOT_AVAILABLE") if isinstance(face_res.get("presentation_attack"), dict) else "NOT_AVAILABLE",
                pad_reason=face_res.get("presentation_attack", {}).get("reason") if isinstance(face_res.get("presentation_attack"), dict) else None
            )
            db.add(fr_rec)
            face_record = {
                "metric": fr_rec.metric,
                "similarity_score": fr_rec.similarity_score,
                "threshold": fr_rec.threshold,
                "verification_result": fr_rec.verification_result,
                "decision_state": face_res.get("decision_state", "INCONCLUSIVE"),
                "appearance_level": fr_rec.appearance_level,
                "observations": face_res.get("appearance_analysis", {}).get("observations", []) if isinstance(face_res.get("appearance_analysis"), dict) else [],
                "recommendation": fr_rec.recommendation,
                "provider": fr_rec.provider,
                "provider_type": face_res.get("provider_type", "DEEP_NEURAL"),
                "quality_status": fr_rec.quality_status,
                "quality_reasons": face_res.get("live_quality", {}).get("reasons", []) if isinstance(face_res.get("live_quality"), dict) else [],
                "pad_status": fr_rec.pad_status,
                "pad_reason": fr_rec.pad_reason,
                "doc_face_crop_url": f"/api/v1/screenings/media/{screening_id}/doc_face" if doc_face_crop_path else None,
                "live_face_crop_url": f"/api/v1/screenings/media/{screening_id}/live_face" if live_face_crop_path else None,
                "evidence_metadata": face_res.get("evidence_metadata", {})
            }

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

        # 8. Blockchain Anchor (Hyperledger Fabric)
        blockchain_anchor_data = None
        try:
            blockchain_anchor_data = FabricAnchorService.create_anchor(
                db=db,
                screening_id=screening_id,
                doc_path=doc_image_path,
                risk_band=risk_res["risk_band"],
                checkpoint_id=checkpoint_id or "CP-DEL-AIR",
                actor=f"OFFICER_{operator_id}" if operator_id else "SYSTEM_AUTOMATION"
            )
        except Exception as bc_err:
            logger.warning(f"[Blockchain Anchor] Anchoring attempt for {screening_id}: {bc_err}")

        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        return {
            "id": screening_id,
            "screening_id": screening_id,
            "created_at": datetime.now(timezone.utc),
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": checkpoint_name,
            "document_type": "PASSPORT",
            "masked_document_id": masked_id,
            "status": screening_rec.status,
            "risk_score": risk_res["risk_score"],
            "risk_band": risk_res["risk_band"],
            "recommendation": screening_rec.recommendation,
            "ocr_status": ocr_res.get("ocr_status", "SUCCESS" if field_records else "FAILED"),
            "ocr_engine": actual_engine,
            "ocr_reason": ocr_res.get("ocr_reason", ""),
            "execution_latency_ms": latency_ms,
            "doc_image_url": f"/api/v1/screenings/media/{screening_id}/doc",
            "live_image_url": f"/api/v1/screenings/media/{screening_id}/live" if live_image_path else None,
            "doc_face_url": f"/api/v1/screenings/media/{screening_id}/doc_face" if doc_face_crop_path else None,
            "live_face_url": f"/api/v1/screenings/media/{screening_id}/live_face" if live_face_crop_path else None,
            "ela_heatmap_url": f"/api/v1/screenings/media/{screening_id}/heatmap" if tamper_res.get("heatmap_path") else None,
            "quality_assessment": quality_res,
            "extracted_fields": field_records,
            "mrz_data": mrz_res if mrz_res.get("parsed") else None,
            "validation_findings": val_records,
            "tamper_findings": tamper_records,
            "tamper_summary": tamper_res,
            "face_result": face_record,
            "biometric_verification": face_res.get("biometric_verification") if face_res else None,
            "identity_matches": identity_records,
            "risk_reasons": risk_res["reasons"],
            "signal_breakdown": risk_res["signal_breakdown"],
            "blockchain_anchor": blockchain_anchor_data,
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

    def _execute_visa_pipeline(
        self,
        db: Session,
        screening_id: str,
        start_time: float,
        doc_image_path: str,
        live_image_path: Optional[str],
        operator_id: Optional[int],
        checkpoint_id: Optional[str],
        checkpoint_name: Optional[str],
        quality_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dedicated Visa Pipeline: OCR -> Visa Field Extraction -> Visa Rule Validation -> Forensics -> Optional Biometrics."""
        # 1. OCR Extraction
        ocr_res = self.ocr_engine.process_image(doc_image_path)
        actual_engine = ocr_res.get("engine")
        raw_lines = ocr_res.get("raw_lines", [])
        AuditService.record_event(
            db, screening_id, "OCR_EXTRACTION_COMPLETED",
            {"total_lines": ocr_res.get("total_lines_detected"), "ocr_engine": actual_engine}
        )

        # 2. Dedicated Visa Field Extraction
        visa_fields = VisaParser.parse_visa_fields(raw_lines, ocr_engine_name=actual_engine or "Tesseract")
        AuditService.record_event(
            db, screening_id, "VISA_FIELDS_EXTRACTED",
            {"visa_number": visa_fields.get("visa_number", {}).get("value"), "visa_type": visa_fields.get("visa_type", {}).get("value")}
        )

        # 3. Visa Rule Validation
        visa_findings = VisaParser.validate_visa_rules(visa_fields)

        # Check watchlist on visa number or linked passport
        v_num = visa_fields.get("visa_number", {}).get("value")
        v_ppt = visa_fields.get("passport_number", {}).get("value")
        doc_num_to_check = v_num or v_ppt
        if doc_num_to_check:
            clean_num = doc_num_to_check.replace(" ", "").upper()
            w_entry = db.query(ReferenceWatchlist).filter(ReferenceWatchlist.document_id == clean_num).first()
            if w_entry:
                visa_findings.append({
                    "rule_id": "WATCHLIST_MATCH",
                    "category": "WATCHLIST",
                    "severity": "CRITICAL",
                    "field": "document_number",
                    "expected": "CLEAR",
                    "observed": f"FLAGGED ({w_entry.risk_category})",
                    "message": f"Visa/Passport reference matched watchlist: {w_entry.reason} (Subject: {w_entry.full_name})",
                    "classification": "PROTOTYPE_RULE"
                })

        AuditService.record_event(
            db, screening_id, "VISA_RULES_VALIDATED",
            {"findings_count": len(visa_findings)}
        )

        # 4. Tamper Forensics
        tamper_res = self.tamper_pipeline.analyze(doc_image_path, output_dir=settings.HEATMAP_DIR)
        AuditService.record_event(
            db, screening_id, "TAMPER_FORENSICS_COMPLETED",
            {"score": tamper_res.get("composite_tamper_score"), "findings": tamper_res.get("findings_count")}
        )

        # 5. Face Verification (if portrait detected on visa vignette)
        face_res = None
        doc_face_crop_path = None
        live_face_crop_path = None
        if live_image_path and os.path.exists(live_image_path):
            face_res = self.face_verifier.verify(doc_image_path, live_image_path)
            try:
                os.makedirs(settings.STORAGE_DIR, exist_ok=True)
                if face_res.get("doc_face_crop") is not None:
                    p = os.path.join(settings.STORAGE_DIR, f"{screening_id}_doc_face.jpg")
                    cv2.imwrite(p, face_res["doc_face_crop"])
                    doc_face_crop_path = p
                if face_res.get("live_face_crop") is not None:
                    p = os.path.join(settings.STORAGE_DIR, f"{screening_id}_live_face.jpg")
                    cv2.imwrite(p, face_res["live_face_crop"])
                    live_face_crop_path = p
            except Exception as e:
                logger.warning(f"Failed to persist face crops for {screening_id}: {e}")

            AuditService.record_event(
                db, screening_id, "FACE_VERIFICATION_COMPLETED",
                {
                    "result": face_res.get("verification_result"),
                    "similarity": face_res.get("similarity_score"),
                    "provider": face_res.get("provider")
                }
            )

        # 6. Risk Fusion calibrated for Visa
        risk_res = self.risk_engine.compute_risk(
            quality_res=quality_res,
            mrz_res={"parsed": False},
            viz_mrz_findings=[],
            rule_findings=visa_findings,
            tamper_res=tamper_res,
            face_res=face_res,
            duplicate_res=None,
            doc_type="VISA"
        )
        AuditService.record_event(
            db, screening_id, "RISK_SCORE_GENERATED",
            {"score": risk_res["risk_score"], "band": risk_res["risk_band"]}
        )

        # 7. Persist to Database
        latency_ms = round((time.time() - start_time) * 1000.0, 1)
        raw_doc_id = doc_num_to_check or "VISA-UNKNOWN"
        masked_id = mask_document_number(raw_doc_id)

        if quality_res.get("verdict") in ["REJECTED", "NEEDS_BETTER_IMAGE"]:
            terminal_status = "UNABLE_TO_VERIFY"
            terminal_rec = "Unable to verify — image quality is insufficient. Please capture a clearer visa document."
        elif risk_res["risk_band"] == "LOW":
            terminal_status = "COMPLETED"
            terminal_rec = risk_res["recommendation"]
        else:
            terminal_status = "MANUAL_REVIEW_REQUIRED"
            terminal_rec = risk_res["recommendation"]

        screening_rec = Screening(
            id=screening_id,
            operator_id=operator_id,
            checkpoint_id=checkpoint_id,
            checkpoint_name=checkpoint_name,
            document_type="VISA",
            masked_document_id=masked_id,
            status=terminal_status,
            risk_score=risk_res["risk_score"],
            risk_band=risk_res["risk_band"],
            recommendation=terminal_rec,
            doc_image_path=doc_image_path,
            live_image_path=live_image_path,
            ela_heatmap_path=tamper_res.get("heatmap_path"),
            ocr_engine=actual_engine,
            execution_latency_ms=latency_ms
        )
        db.add(screening_rec)

        # Save Extracted Fields
        field_records = []
        for fname, val_dict in visa_fields.items():
            v_val = val_dict.get("value")
            bbox = val_dict.get("bounding_box")
            st_val = val_dict.get("status", "NOT_FOUND")
            f_rec = ExtractedField(
                screening_id=screening_id,
                field_name=fname,
                visual_value=str(v_val) if v_val is not None else None,
                mrz_value=None,
                confidence=val_dict.get("confidence") or 1.0,
                ocr_engine=actual_engine,
                validation=val_dict.get("validation", "VALID"),
                match_status="MATCH" if st_val in ["FOUND", "LOW_CONFIDENCE"] else "NOT_PRESENT",
                bounding_box_json=json.dumps(bbox) if bbox else None
            )
            db.add(f_rec)
            field_records.append({
                "field_name": fname,
                "field_value": str(v_val) if v_val is not None else None,
                "visual_value": str(v_val) if v_val is not None else None,
                "mrz_value": None,
                "confidence": val_dict.get("confidence") or 1.0,
                "ocr_engine": actual_engine,
                "validation": f_rec.validation,
                "match_status": f_rec.match_status,
                "bounding_box": bbox
            })

        # Save Validation Findings
        val_records = []
        for vf in visa_findings:
            cat = vf.get("category", "VISA_COMPLIANCE")
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

        face_record = None
        if face_res:
            vr = face_res.get("verification_result", "UNABLE_TO_VERIFY")
            fr_rec = FaceResult(
                screening_id=screening_id,
                metric=face_res.get("metric", "Cosine Similarity"),
                similarity_score=float(face_res.get("similarity_score", 0.0) or 0.0),
                threshold=float(face_res.get("threshold", 0.68) or 0.68),
                verification_result=vr,
                appearance_level=face_res.get("appearance_analysis", {}).get("appearance_difference_level", "MINIMAL") if isinstance(face_res.get("appearance_analysis"), dict) else "MINIMAL",
                observations_json=json.dumps(face_res.get("appearance_analysis", {}).get("observations", [])) if isinstance(face_res.get("appearance_analysis"), dict) else "[]",
                recommendation=face_res.get("recommendation", "") or face_res.get("reason", ""),
                provider=face_res.get("provider", "SFace-ResNet-128d-v1.0"),
                quality_status=face_res.get("live_quality", {}).get("status", "GOOD") if isinstance(face_res.get("live_quality"), dict) else "GOOD",
                pad_status=face_res.get("presentation_attack", {}).get("status", "NOT_AVAILABLE") if isinstance(face_res.get("presentation_attack"), dict) else "NOT_AVAILABLE",
                pad_reason=face_res.get("presentation_attack", {}).get("reason") if isinstance(face_res.get("presentation_attack"), dict) else None
            )
            db.add(fr_rec)
            face_record = {
                "metric": fr_rec.metric,
                "similarity_score": fr_rec.similarity_score,
                "threshold": fr_rec.threshold,
                "verification_result": fr_rec.verification_result,
                "decision_state": face_res.get("decision_state", "INCONCLUSIVE"),
                "appearance_level": fr_rec.appearance_level,
                "observations": face_res.get("appearance_analysis", {}).get("observations", []) if isinstance(face_res.get("appearance_analysis"), dict) else [],
                "recommendation": fr_rec.recommendation,
                "provider": fr_rec.provider,
                "provider_type": face_res.get("provider_type", "DEEP_NEURAL"),
                "quality_status": fr_rec.quality_status,
                "quality_reasons": face_res.get("live_quality", {}).get("reasons", []) if isinstance(face_res.get("live_quality"), dict) else [],
                "pad_status": fr_rec.pad_status,
                "pad_reason": fr_rec.pad_reason,
                "doc_face_crop_url": f"/api/v1/screenings/media/{screening_id}/doc_face" if doc_face_crop_path else None,
                "live_face_crop_url": f"/api/v1/screenings/media/{screening_id}/live_face" if live_face_crop_path else None,
                "evidence_metadata": face_res.get("evidence_metadata", {})
            }

        db.commit()

        # 8. Blockchain Anchor (Hyperledger Fabric)
        blockchain_anchor_data = None
        try:
            blockchain_anchor_data = FabricAnchorService.create_anchor(
                db=db,
                screening_id=screening_id,
                doc_path=doc_image_path,
                risk_band=risk_res["risk_band"],
                checkpoint_id=checkpoint_id or "CP-DEL-AIR",
                actor=f"OFFICER_{operator_id}" if operator_id else "SYSTEM_AUTOMATION"
            )
        except Exception as bc_err:
            logger.warning(f"[Blockchain Anchor] Anchoring attempt for {screening_id}: {bc_err}")

        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        return {
            "id": screening_id,
            "screening_id": screening_id,
            "created_at": datetime.now(timezone.utc),
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": checkpoint_name,
            "document_type": "VISA",
            "masked_document_id": masked_id,
            "status": screening_rec.status,
            "risk_score": risk_res["risk_score"],
            "risk_band": risk_res["risk_band"],
            "recommendation": screening_rec.recommendation,
            "ocr_status": ocr_res.get("ocr_status", "SUCCESS" if field_records else "FAILED"),
            "ocr_engine": actual_engine,
            "ocr_reason": ocr_res.get("ocr_reason", ""),
            "execution_latency_ms": latency_ms,
            "doc_image_url": f"/api/v1/screenings/media/{screening_id}/doc",
            "live_image_url": f"/api/v1/screenings/media/{screening_id}/live" if live_image_path else None,
            "doc_face_url": f"/api/v1/screenings/media/{screening_id}/doc_face" if doc_face_crop_path else None,
            "live_face_url": f"/api/v1/screenings/media/{screening_id}/live_face" if live_face_crop_path else None,
            "ela_heatmap_url": f"/api/v1/screenings/media/{screening_id}/heatmap" if tamper_res.get("heatmap_path") else None,
            "quality_assessment": quality_res,
            "extracted_fields": field_records,
            "mrz_data": None,
            "validation_findings": val_records,
            "tamper_findings": tamper_records,
            "tamper_summary": tamper_res,
            "face_result": face_record,
            "biometric_verification": face_res.get("biometric_verification") if face_res else None,
            "identity_matches": [],
            "risk_reasons": risk_res["reasons"],
            "signal_breakdown": risk_res["signal_breakdown"],
            "blockchain_anchor": blockchain_anchor_data,
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

    def _handle_quality_rejection(
        self,
        db: Session,
        screening_id: str,
        start_time: float,
        doc_image_path: str,
        live_image_path: Optional[str],
        operator_id: Optional[int],
        checkpoint_id: Optional[str],
        checkpoint_name: Optional[str],
        doc_type: str,
        quality_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handles terminal QUALITY_REJECTED state cleanly."""
        latency_ms = round((time.time() - start_time) * 1000.0, 1)
        rec_msg = "Image quality is insufficient for reliable verification. Please upload a sharper, well-lit image of the Passport/Visa."

        screening_rec = Screening(
            id=screening_id,
            operator_id=operator_id,
            checkpoint_id=checkpoint_id,
            checkpoint_name=checkpoint_name,
            document_type=doc_type,
            masked_document_id="UNREADABLE",
            status="QUALITY_REJECTED",
            risk_score=60.0,
            risk_band="MEDIUM",
            recommendation=rec_msg,
            doc_image_path=doc_image_path,
            live_image_path=live_image_path,
            ocr_engine=None,
            execution_latency_ms=latency_ms
        )
        db.add(screening_rec)
        AuditService.record_event(
            db, screening_id, "QUALITY_GATE_REJECTED",
            {"score": quality_res.get("overall_score"), "reasons": quality_res.get("reasons")}
        )
        db.commit()

        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        return {
            "id": screening_id,
            "screening_id": screening_id,
            "created_at": datetime.now(timezone.utc),
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": checkpoint_name,
            "document_type": doc_type,
            "masked_document_id": "UNREADABLE",
            "status": "QUALITY_REJECTED",
            "risk_score": 60.0,
            "risk_band": "MEDIUM",
            "recommendation": rec_msg,
            "ocr_engine": None,
            "execution_latency_ms": latency_ms,
            "doc_image_url": f"/api/v1/screenings/media/{screening_id}/doc",
            "live_image_url": None,
            "ela_heatmap_url": None,
            "quality_assessment": quality_res,
            "extracted_fields": [],
            "mrz_data": None,
            "validation_findings": [],
            "tamper_findings": [],
            "tamper_summary": {"composite_tamper_score": 0.0, "findings_count": 0},
            "face_result": None,
            "identity_matches": [],
            "risk_reasons": [{
                "category": "QUALITY",
                "severity": "HIGH",
                "summary": "Quality Gate Failure",
                "detail": "; ".join(quality_res.get("reasons", ["Blur or glare exceeds tolerance."])),
                "action": "Request document re-capture."
            }],
            "signal_breakdown": {"quality_uncertainty": 60.0},
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

    def _handle_unsupported_document(
        self,
        db: Session,
        screening_id: str,
        start_time: float,
        doc_image_path: str,
        live_image_path: Optional[str],
        operator_id: Optional[int],
        checkpoint_id: Optional[str],
        checkpoint_name: Optional[str],
        class_res: Dict[str, Any],
        quality_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handles terminal UNSUPPORTED_DOCUMENT state cleanly."""
        latency_ms = round((time.time() - start_time) * 1000.0, 1)
        det_type = class_res.get("detected_type", "UNSUPPORTED")
        rec_msg = class_res.get("message", "Unsupported document type. SatyaScan currently supports Passport and Visa only.")

        screening_rec = Screening(
            id=screening_id,
            operator_id=operator_id,
            checkpoint_id=checkpoint_id,
            checkpoint_name=checkpoint_name,
            document_type=det_type,
            masked_document_id="REJECTED",
            status="UNSUPPORTED_DOCUMENT",
            risk_score=80.0,
            risk_band="HIGH",
            recommendation=rec_msg,
            doc_image_path=doc_image_path,
            live_image_path=live_image_path,
            ocr_engine=None,
            execution_latency_ms=latency_ms
        )
        db.add(screening_rec)
        AuditService.record_event(
            db, screening_id, "UNSUPPORTED_DOCUMENT_REJECTED",
            {"detected_type": det_type, "indicators": class_res.get("indicators")}
        )
        db.commit()

        audit_events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        return {
            "id": screening_id,
            "screening_id": screening_id,
            "created_at": datetime.now(timezone.utc),
            "checkpoint_id": checkpoint_id,
            "checkpoint_name": checkpoint_name,
            "document_type": det_type,
            "masked_document_id": "REJECTED",
            "status": "UNSUPPORTED_DOCUMENT",
            "risk_score": 80.0,
            "risk_band": "HIGH",
            "recommendation": rec_msg,
            "ocr_engine": None,
            "execution_latency_ms": latency_ms,
            "doc_image_url": f"/api/v1/screenings/media/{screening_id}/doc",
            "live_image_url": None,
            "ela_heatmap_url": None,
            "quality_assessment": quality_res,
            "extracted_fields": [],
            "mrz_data": None,
            "validation_findings": [],
            "tamper_findings": [],
            "tamper_summary": {"composite_tamper_score": 0.0, "findings_count": 0},
            "face_result": None,
            "identity_matches": [],
            "risk_reasons": [{
                "category": "DOCUMENT_TYPE",
                "severity": "CRITICAL",
                "summary": f"Unsupported Document Type: {det_type}",
                "detail": "; ".join(class_res.get("indicators", ["Document is not an accepted Passport or Visa."])),
                "action": "Reject document from border pipeline."
            }],
            "signal_breakdown": {"document_type_mismatch": 80.0},
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


# Global singleton instance
screening_orchestrator = ScreeningOrchestrator()
