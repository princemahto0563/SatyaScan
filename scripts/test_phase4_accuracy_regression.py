"""
Phase 4F: Accuracy Regression Validation Script.
Validates Case 01 and Case 09 in-depth through the production ScreeningOrchestrator:
- OCR fields extraction
- MRZ parsing and 7-3-1 check digits
- SFace similarity score and thresholds
- Final verdict and risk band
"""

import os
import sys
import json
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.models.database import SessionLocal
from backend.app.services.orchestrator import screening_orchestrator

def evaluate_case(doc_path: str, live_path: str, case_name: str):
    print("=" * 70)
    print(f"EVALUATING {case_name}")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        
        # 1. Classification
        class_res = screening_orchestrator.document_classifier.classify_image(doc_path)
        t_class = time.perf_counter() - t0
        
        # 2. Screening
        t1 = time.perf_counter()
        res = screening_orchestrator.process_screening(
            db=db,
            doc_image_path=doc_path,
            live_image_path=live_path,
            operator_id="test-officer",
            doc_type="PASSPORT",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi IGI Terminal 3",
            classification_result=class_res
        )
        t_proc = time.perf_counter() - t1
        t_total = time.perf_counter() - t0

        print(f"Timing: Classification+OCR={t_class*1000:.1f}ms | Pipeline={t_proc*1000:.1f}ms | Total={t_total*1000:.1f}ms")
        print(f"Engine used: {res.get('ocr_engine')}")
        print(f"Status: {res.get('status')} | Verdict: {res.get('recommendation')}")
        print(f"Risk Score: {res.get('risk_score')} (Band: {res.get('risk_band')})")
        
        # Extracted fields
        fields = {f['field_name']: f['field_value'] for f in res.get('extracted_fields', [])}
        print(f"Extracted Fields ({len(fields)}):")
        for k in ['document_number', 'surname', 'given_names', 'full_name', 'nationality', 'date_of_birth', 'date_of_expiry', 'sex']:
            print(f"  {k:16s}: {fields.get(k)}")

        # MRZ data
        mrz = res.get('mrz_data') or {}
        print(f"MRZ Data:")
        print(f"  Parsed            : {mrz.get('parsed')}")
        print(f"  All Checks Passed : {mrz.get('all_checks_passed')}")
        print(f"  Document Number   : {mrz.get('document_number')}")
        print(f"  DOB               : {mrz.get('date_of_birth')}")
        print(f"  Expiry            : {mrz.get('date_of_expiry')}")
        print(f"  Issuing Country   : {mrz.get('issuing_country')}")

        # Biometrics / Face
        face = res.get('face_result') or {}
        if face:
            print(f"Biometric Verification:")
            print(f"  Similarity Score  : {face.get('similarity_score')}")
            print(f"  Result            : {face.get('verification_result')}")
            print(f"  Confidence        : {face.get('confidence')}")

        # Assertions
        if "Case 01" in case_name:
            assert fields.get("document_number") == "Z1234567" or fields.get("passport_number") == "Z1234567", f"Expected Z1234567, got {fields.get('document_number')}"
            assert fields.get("surname") == "SHARMA", f"Expected SHARMA, got {fields.get('surname')}"
            assert fields.get("given_names") == "ARJUN", f"Expected ARJUN, got {fields.get('given_names')}"
            assert mrz.get("parsed") is True, f"MRZ should be parsed: {mrz}"
            assert mrz.get("all_checks_passed") is True, f"MRZ all checks should pass: {mrz}"
            assert face.get("similarity_score", 0) >= 0.68, f"SFace should match genuine face >= 0.68, got {face.get('similarity_score')}"
            assert "MATCH" in face.get("verification_result", ""), f"Expected MATCH, got {face.get('verification_result')}"
            assert res.get("status") == "COMPLETED", f"Expected COMPLETED, got {res.get('status')}"
            assert res.get("risk_band") == "LOW", f"Expected LOW risk, got {res.get('risk_band')}"
            print(">>> CASE 01 ASSERTIONS PASSED PERFECTLY! <<<")

        elif "Case 09" in case_name:
            assert fields.get("document_number") == "Z1234567" or fields.get("passport_number") == "Z1234567", f"Expected Z1234567, got {fields.get('document_number')}"
            assert mrz.get("parsed") is True, "MRZ should be parsed"
            assert face.get("similarity_score", 1.0) < 0.48, f"SFace should detect imposter < 0.48, got {face.get('similarity_score')}"
            assert "MISMATCH" in face.get("verification_result", "") or face.get("verification_result") == "REJECT", f"Expected MISMATCH, got {face.get('verification_result')}"
            assert res.get("status") == "MANUAL_REVIEW_REQUIRED", f"Expected MANUAL_REVIEW_REQUIRED, got {res.get('status')}"
            assert res.get("risk_band") in ["MEDIUM", "HIGH", "CRITICAL"], f"Expected MEDIUM/HIGH/CRITICAL risk, got {res.get('risk_band')}"
            print(">>> CASE 09 ASSERTIONS PASSED PERFECTLY! <<<")

        return res
    finally:
        db.close()


if __name__ == "__main__":
    c1_doc = os.path.join(PROJECT_ROOT, "data/genuine/case01_genuine_arjun.jpg")
    c1_live = os.path.join(PROJECT_ROOT, "data/selfies/case01_selfie_arjun.jpg")
    c9_live = os.path.join(PROJECT_ROOT, "data/selfies/case09_selfie_imposter.jpg")

    evaluate_case(c1_doc, c1_live, "Case 01 Genuine")
    evaluate_case(c1_doc, c9_live, "Case 09 Imposter")
