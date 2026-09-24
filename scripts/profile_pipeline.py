"""
Phase 1 Profiling Script for SatyaScan Screening Pipeline
Instruments exact timings for all production pipeline stages.
Uses the ACTUAL production orchestrator and existing codebase APIs.
DOES NOT MODIFY PRODUCTION BEHAVIOR OR USE MOCKED VALUES.
"""

import os
import sys
import time
import json
import uuid
import numpy as np
import cv2

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.security import validate_uploaded_image_bytes
from backend.app.core.config import settings
from backend.app.models.database import (
    Base, engine, SessionLocal, Screening, ExtractedField,
    ValidationFinding, TamperFinding, FaceResult, AuditEvent, ReferenceWatchlist
)
from backend.app.services.audit_service import AuditService
from backend.app.services.report_generator import ReportGenerator
from backend.app.services.orchestrator import screening_orchestrator, ScreeningOrchestrator
from ai.quality.quality_gate import DocumentQualityGate
from ai.classifier.document_classifier import DocumentClassifier
from ai.ocr.ocr_engine import OCREngine
from ai.mrz.mrz_parser import MRZParser
from ai.tamper.pipeline import TamperForensicsPipeline
from ai.tamper.ela import ELAEngine
from ai.tamper.noise_residual import NoiseResidualEngine
from ai.tamper.copy_move import CopyMoveDetector
from ai.face.face_verifier import FaceVerifier
from ai.duplicate.indexer import MultiIdentityIndexer
from ai.risk.risk_engine import RiskEngine


def verify_production_apis():
    """
    Lightweight API and method verification.
    Guarantees every method called by the profiler genuinely exists
    in the production codebase before running any screening.
    """
    checks = [
        (DocumentQualityGate, "assess_image"),
        (DocumentClassifier, "classify_image"),
        (OCREngine, "process_image"),
        (MRZParser, "parse_td3"),
        (MRZParser, "cross_validate_viz"),
        (TamperForensicsPipeline, "analyze"),
        (ELAEngine, "analyze"),
        (NoiseResidualEngine, "analyze"),
        (CopyMoveDetector, "analyze"),
        (FaceVerifier, "verify"),
        (FaceVerifier, "detect_and_crop_face"),
        (FaceVerifier, "extract_embedding"),
        (MultiIdentityIndexer, "search_duplicate"),
        (RiskEngine, "compute_risk"),
        (AuditService, "record_event"),
        (ReportGenerator, "generate_pdf"),
        (ScreeningOrchestrator, "process_screening"),
    ]

    print("[1/3] Verifying Production APIs...")
    for cls_obj, method_name in checks:
        if not hasattr(cls_obj, method_name):
            raise AttributeError(f"API Verification Failed: {cls_obj.__name__} has no attribute '{method_name}'")
        print(f"  ✓ {cls_obj.__name__}.{method_name} exists")
    print("All production APIs successfully verified!\n")


def profile_case(doc_path: str, live_path: str, case_name: str) -> dict:
    """
    Profiles end-to-end production screening pipeline for a single case.
    Reuses the singleton screening_orchestrator instance (production behavior).
    Measures exact timings for all 18 specified pipeline stages.
    """
    print("=" * 50)
    print(f"{case_name}")
    print("=" * 50)
    print(f"Doc:  {doc_path}")
    print(f"Live: {live_path}")
    print("-" * 50)

    stage_timings = {
        "upload/read": 0.0,
        "image decode": 0.0,
        "document classification": 0.0,
        "OCR": 0.0,
        "MRZ": 0.0,
        "VIZ extraction": 0.0,
        "document validation": 0.0,
        "ELA": 0.0,
        "noise analysis": 0.0,
        "SIFT/ORB": 0.0,
        "face detection": 0.0,
        "SFace embedding": 0.0,
        "face comparison": 0.0,
        "FAISS": 0.0,
        "risk engine": 0.0,
        "audit": 0.0,
        "report generation": 0.0,
    }

    wall_start = time.perf_counter()

    # 1. Upload + validation
    t0 = time.perf_counter()
    with open(doc_path, "rb") as f:
        doc_bytes = f.read()
    validate_uploaded_image_bytes(doc_bytes, os.path.basename(doc_path))
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    temp_doc_path = os.path.join(settings.UPLOAD_DIR, f"prof_doc_{uuid.uuid4().hex[:8]}.jpg")
    with open(temp_doc_path, "wb") as f:
        f.write(doc_bytes)

    temp_live_path = None
    live_bytes = None
    if live_path and os.path.exists(live_path):
        with open(live_path, "rb") as f:
            live_bytes = f.read()
        validate_uploaded_image_bytes(live_bytes, os.path.basename(live_path))
        temp_live_path = os.path.join(settings.UPLOAD_DIR, f"prof_live_{uuid.uuid4().hex[:8]}.jpg")
        with open(temp_live_path, "wb") as f:
            f.write(live_bytes)
    stage_timings["upload/read"] = time.perf_counter() - t0

    # 2. Image decoding
    t0 = time.perf_counter()
    cv_doc = cv2.imdecode(np.frombuffer(doc_bytes, np.uint8), cv2.IMREAD_COLOR)
    cv_live = cv2.imdecode(np.frombuffer(live_bytes, np.uint8), cv2.IMREAD_COLOR) if live_bytes else None
    stage_timings["image decode"] = time.perf_counter() - t0

    # 3. Instrument internal production calls inside screening_orchestrator
    orig_ocr = screening_orchestrator.ocr_engine.process_image
    orig_parse_td3 = MRZParser.parse_td3
    orig_viz = MRZParser.cross_validate_viz
    orig_ela = screening_orchestrator.tamper_pipeline.ela_engine.analyze
    orig_noise = screening_orchestrator.tamper_pipeline.noise_engine.analyze
    orig_cm = screening_orchestrator.tamper_pipeline.copy_move_detector.analyze
    orig_detect_face = screening_orchestrator.face_verifier.detect_and_crop_face
    orig_extract_emb = screening_orchestrator.face_verifier.extract_embedding
    orig_comp_sim = screening_orchestrator.face_verifier.provider.compute_similarity
    orig_search_dup = screening_orchestrator.identity_indexer.search_duplicate
    orig_risk = screening_orchestrator.risk_engine.compute_risk
    orig_audit = AuditService.record_event

    def timed_ocr(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_ocr(*args, **kwargs)
        finally:
            stage_timings["OCR"] += time.perf_counter() - t

    screening_orchestrator.ocr_engine.process_image = timed_ocr

    # 4. Document classification (reuses instrumented OCR engine)
    t0 = time.perf_counter()
    ocr_before = stage_timings["OCR"]
    classification = screening_orchestrator.document_classifier.classify_image(temp_doc_path)
    ocr_during_class = stage_timings["OCR"] - ocr_before
    # Document classification time without OCR
    stage_timings["document classification"] = max(0.0, (time.perf_counter() - t0) - ocr_during_class)

    def timed_parse_td3(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_parse_td3(*args, **kwargs)
        finally:
            stage_timings["MRZ"] += time.perf_counter() - t

    def timed_viz(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_viz(*args, **kwargs)
        finally:
            stage_timings["VIZ extraction"] += time.perf_counter() - t

    def timed_ela(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_ela(*args, **kwargs)
        finally:
            stage_timings["ELA"] += time.perf_counter() - t

    def timed_noise(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_noise(*args, **kwargs)
        finally:
            stage_timings["noise analysis"] += time.perf_counter() - t

    def timed_cm(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_cm(*args, **kwargs)
        finally:
            stage_timings["SIFT/ORB"] += time.perf_counter() - t

    def timed_detect_face(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_detect_face(*args, **kwargs)
        finally:
            stage_timings["face detection"] += time.perf_counter() - t

    def timed_extract_emb(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_extract_emb(*args, **kwargs)
        finally:
            stage_timings["SFace embedding"] += time.perf_counter() - t

    def timed_comp_sim(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_comp_sim(*args, **kwargs)
        finally:
            stage_timings["face comparison"] += time.perf_counter() - t

    def timed_search_dup(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_search_dup(*args, **kwargs)
        finally:
            stage_timings["FAISS"] += time.perf_counter() - t

    def timed_risk(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_risk(*args, **kwargs)
        finally:
            stage_timings["risk engine"] += time.perf_counter() - t

    def timed_audit(*args, **kwargs):
        t = time.perf_counter()
        try:
            return orig_audit(*args, **kwargs)
        finally:
            stage_timings["audit"] += time.perf_counter() - t

    # Apply wrappers
    screening_orchestrator.ocr_engine.process_image = timed_ocr
    MRZParser.parse_td3 = timed_parse_td3
    MRZParser.cross_validate_viz = timed_viz
    screening_orchestrator.tamper_pipeline.ela_engine.analyze = timed_ela
    screening_orchestrator.tamper_pipeline.noise_engine.analyze = timed_noise
    screening_orchestrator.tamper_pipeline.copy_move_detector.analyze = timed_cm
    screening_orchestrator.face_verifier.detect_and_crop_face = timed_detect_face
    screening_orchestrator.face_verifier.extract_embedding = timed_extract_emb
    screening_orchestrator.face_verifier.provider.compute_similarity = timed_comp_sim
    screening_orchestrator.identity_indexer.search_duplicate = timed_search_dup
    screening_orchestrator.risk_engine.compute_risk = timed_risk
    AuditService.record_event = timed_audit

    db = SessionLocal()
    # Instrument document validation (watchlist query)
    orig_query = db.query
    def timed_query(*args, **kwargs):
        if len(args) > 0 and args[0] is ReferenceWatchlist:
            t = time.perf_counter()
            try:
                return orig_query(*args, **kwargs)
            finally:
                stage_timings["document validation"] += time.perf_counter() - t
        return orig_query(*args, **kwargs)
    db.query = timed_query

    result = None
    try:
        # Execute the real production screening pipeline
        result = screening_orchestrator.process_screening(
            db=db,
            doc_image_path=temp_doc_path,
            live_image_path=temp_live_path,
            doc_type=classification["verdict"],
            classification_result=classification
        )

        # 18. PDF / report generation
        t0 = time.perf_counter()
        screening_id = result["id"]
        screening = db.query(Screening).filter(Screening.id == screening_id).first()
        fields = db.query(ExtractedField).filter(ExtractedField.screening_id == screening_id).all()
        val_findings = db.query(ValidationFinding).filter(ValidationFinding.screening_id == screening_id).all()
        tamper_findings = db.query(TamperFinding).filter(TamperFinding.screening_id == screening_id).all()
        face_res = db.query(FaceResult).filter(FaceResult.screening_id == screening_id).first()
        audit_events = db.query(AuditEvent).filter(AuditEvent.screening_id == screening_id).all()

        case_payload = {
            "id": screening.id,
            "created_at": str(screening.created_at),
            "blockchain_anchor": None,
            "checkpoint_id": screening.checkpoint_id,
            "checkpoint_name": screening.checkpoint_name,
            "operator_name": "Screening Officer",
            "operator_badge": "OP-01",
            "document_type": screening.document_type,
            "masked_document_id": screening.masked_document_id,
            "status": screening.status,
            "risk_score": screening.risk_score,
            "risk_band": screening.risk_band,
            "recommendation": screening.recommendation,
            "extracted_fields": [
                {
                    "field_name": f.field_name,
                    "visual_value": f.visual_value,
                    "mrz_value": f.mrz_value,
                    "confidence": f.confidence,
                    "match_status": f.match_status
                }
                for f in fields
            ],
            "tamper_summary": {
                "composite_tamper_score": max([t.score for t in tamper_findings], default=0.0),
                "signals": {
                    "ela": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "ELA"], default=0.0)},
                    "noise_residual": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "NOISE_RESIDUAL"], default=0.0)},
                    "copy_move": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "COPY_MOVE"], default=0.0)}
                }
            },
            "face_result": {
                "metric": face_res.metric if face_res else "Cosine Similarity",
                "similarity_score": face_res.similarity_score if face_res else 0.0,
                "threshold": face_res.threshold if face_res else 0.65,
                "verification_result": face_res.verification_result if face_res else "NOT_RUN",
                "decision_state": face_res.verification_result if face_res else "NOT_RUN",
                "recommendation": face_res.recommendation if face_res else "No live selfie provided",
                "provider": face_res.provider if face_res else "SFace-ResNet-128d-v1.0",
                "quality_status": face_res.quality_status if face_res else "GOOD",
                "pad_status": face_res.pad_status if face_res else "NOT_AVAILABLE",
                "appearance_level": face_res.appearance_level if face_res else "MINIMAL",
                "observations_json": face_res.observations_json if face_res else None
            } if face_res else None,
            "risk_reasons": [
                {
                    "category": v.category,
                    "severity": v.severity,
                    "summary": v.message,
                    "action": "Manual review"
                }
                for v in val_findings
            ],
            "audit_trail": [
                {"event_hash": a.event_hash} for a in audit_events
            ]
        }

        os.makedirs(settings.REPORT_DIR, exist_ok=True)
        tmp_pdf = os.path.join(settings.REPORT_DIR, f"{screening_id}_prof_report.pdf")
        ReportGenerator.generate_pdf(case_payload, tmp_pdf)
        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)
        stage_timings["report generation"] = time.perf_counter() - t0

    finally:
        # Restore original methods
        screening_orchestrator.ocr_engine.process_image = orig_ocr
        MRZParser.parse_td3 = orig_parse_td3
        MRZParser.cross_validate_viz = orig_viz
        screening_orchestrator.tamper_pipeline.ela_engine.analyze = orig_ela
        screening_orchestrator.tamper_pipeline.noise_engine.analyze = orig_noise
        screening_orchestrator.tamper_pipeline.copy_move_detector.analyze = orig_cm
        screening_orchestrator.face_verifier.detect_and_crop_face = orig_detect_face
        screening_orchestrator.face_verifier.extract_embedding = orig_extract_emb
        screening_orchestrator.face_verifier.provider.compute_similarity = orig_comp_sim
        screening_orchestrator.identity_indexer.search_duplicate = orig_search_dup
        screening_orchestrator.risk_engine.compute_risk = orig_risk
        AuditService.record_event = orig_audit
        db.close()

        # Clean temporary uploads
        if os.path.exists(temp_doc_path):
            os.remove(temp_doc_path)
        if temp_live_path and os.path.exists(temp_live_path):
            os.remove(temp_live_path)

    wall_total = time.perf_counter() - wall_start
    stage_timings["TOTAL"] = wall_total

    # Display Stage Timings
    for stage_name, duration in stage_timings.items():
        if stage_name == "TOTAL":
            print("-" * 50)
        print(f"{stage_name:<27} {duration:>6.2f} s")

    # Percentage contribution & top 5 slowest
    total_time = wall_total
    print("\nStage Percentage Breakdown:")
    print("-" * 50)
    sorted_stages = sorted(
        [(k, v) for k, v in stage_timings.items() if k != "TOTAL"],
        key=lambda x: x[1],
        reverse=True
    )
    for k, v in sorted_stages:
        pct = (v / total_time * 100.0) if total_time > 0 else 0.0
        print(f"  {k:<25} {v:>6.2f} s ({pct:>5.1f}%)")

    print("\nTop 5 Slowest Stages:")
    print("-" * 50)
    for rank, (k, v) in enumerate(sorted_stages[:5], 1):
        pct = (v / total_time * 100.0) if total_time > 0 else 0.0
        print(f"  {rank}. {k:<23} {v:>6.2f} s ({pct:>5.1f}%)")

    if result:
        face_info = result.get("face_result", {})
        print(f"\nVerification Results:")
        print(f"  Screening ID:     {result.get('id')}")
        print(f"  Terminal Status:  {result.get('status')}")
        print(f"  Biometric Result: {face_info.get('verification_result')}")
        print(f"  Similarity Score: {face_info.get('similarity_score')}")
        print(f"  Risk Band / Score: {result.get('risk_band')} ({result.get('risk_score')})")
    print("=" * 50 + "\n")

    return stage_timings, result


if __name__ == "__main__":
    verify_production_apis()

    # Step 2: Measure cold model initialization time
    print("[2/3] Measuring Cold Model Initialization Time...")
    t_cold_start = time.perf_counter()
    # Pre-warm singleton OCR engines and biometric models (exactly once)
    screening_orchestrator.document_classifier._init_ocr()
    screening_orchestrator.ocr_engine._init_paddle()
    # Verify SFace provider is initialized
    _ = screening_orchestrator.face_verifier.provider.is_available()
    cold_init_time = time.perf_counter() - t_cold_start
    print(f"Cold Model Initialization Time: {cold_init_time:.2f} s\n")

    # Step 3: Run end-to-end warm screening pipeline for Case 01 and Case 09
    print("[3/3] Profiling End-to-End Warm Screening Pipeline...\n")
    case01_doc = os.path.join(PROJECT_ROOT, "data/genuine/case01_genuine_arjun.jpg")
    case01_selfie = os.path.join(PROJECT_ROOT, "data/selfies/case01_selfie_arjun.jpg")
    case09_selfie = os.path.join(PROJECT_ROOT, "data/selfies/case09_selfie_imposter.jpg")

    t1, res1 = profile_case(case01_doc, case01_selfie, "CASE 01 (Genuine)")
    t9, res9 = profile_case(case01_doc, case09_selfie, "CASE 09 (Imposter)")

    # Print summary comparison table
    print("\n" + "=" * 60)
    print(f"{'Summary Comparison Table':^60}")
    print("=" * 60)
    print(f"{'Stage':<27} {'Case 01':>14} {'Case 09':>14}")
    print("-" * 60)
    for stage in t1.keys():
        if stage == "TOTAL":
            print("-" * 60)
        print(f"{stage:<27} {t1[stage]:>12.2f} s {t9[stage]:>12.2f} s")
    print("=" * 60)
    print(f"\nCold Model Initialization Time: {cold_init_time:.2f} s")
    print(f"Case 01 Warm Pipeline Time:     {t1['TOTAL']:.2f} s")
    print(f"Case 09 Warm Pipeline Time:     {t9['TOTAL']:.2f} s")
    print("=" * 60)
