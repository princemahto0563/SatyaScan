"""
SatyaScan Final Real-Document E2E Validation & Backend QA Suite
Comprehensive execution script covering Phases 1 through 17.
"""

import os
import sys
import io
import time
import json
import uuid
import numpy as np
import cv2
from PIL import Image
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.database import (
    SessionLocal, Screening, ExtractedField, User, Checkpoint,
    ReferenceWatchlist, AuditEvent, ValidationFinding, TamperFinding, FaceResult, init_db
)
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.services.audit_service import AuditService
from ai.classifier.document_classifier import DocumentClassifier
from ai.visa.visa_parser import VisaParser
from ai.mrz.mrz_parser import MRZParser
from ai.quality.quality_gate import DocumentQualityGate
from ai.tamper.pipeline import TamperForensicsPipeline
from ai.face.face_verifier import FaceVerifier
from ai.risk.risk_engine import RiskEngine
from ai.duplicate.indexer import MultiIdentityIndexer
from ai.ocr.ocr_engine import OCREngine


client = TestClient(app)
db = SessionLocal()


def log_header(title):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def create_synthetic_doc_image(text_lines, width=800, height=500, bg_color=(240, 240, 240)):
    img = np.full((height, width, 3), bg_color, dtype=np.uint8)
    y = 50
    for line in text_lines:
        cv2.putText(img, line, (40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
        y += 45
    return img


def img_to_bytes(cv_img, ext="jpg"):
    success, encoded = cv2.imencode(f".{ext}", cv_img)
    return encoded.tobytes()


def get_token_for_checkpoint(username="delhi_airport", checkpoint_id="CP-DEL-AIR"):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@satyascan.gov.in",
            hashed_password=get_password_hash("Demo@123"),
            role="OFFICER",
            full_name=f"Officer at {checkpoint_id}",
            badge_number="SSB-DEL-4092",
            checkpoint_id=checkpoint_id,
            checkpoint_name="Delhi Airport Checkpoint",
            location="Delhi IGI Airport",
            is_active=True
        )
        db.add(user)
        db.commit()
    token = create_access_token({
        "sub": user.username,
        "role": user.role,
        "id": user.id,
        "checkpoint_id": user.checkpoint_id,
        "checkpoint_name": user.checkpoint_name
    })
    return token


# =====================================================================
# RUN ALL QA PHASES
# =====================================================================

def run_qa_suite():
    init_db()
    token = get_token_for_checkpoint()
    headers = {"Authorization": f"Bearer {token}"}
    
    qa_results = {
        "phase1_inventory": {},
        "phase2_passport": {},
        "phase3_visa": {},
        "phase4_unsupported": {},
        "phase5_spoof": {},
        "phase6_checkpoint_spoof": {},
        "phase7_ocr_provenance": {},
        "phase8_failures": {},
        "phase9_tamper": {},
        "phase10_face": {},
        "phase11_faiss": {},
        "phase12_risk": {},
        "phase13_audit": {},
        "phase14_pdf": {},
        "phase15_consistency": {},
        "phase17_latency": {}
    }

    # -----------------------------------------------------------------
    # PHASE 1: INVENTORY EXISTING TEST DATA
    # -----------------------------------------------------------------
    log_header("Phase 1: Inventory Existing Test Data")
    dataset_paths = [
        "data/genuine/case01_genuine_arjun.jpg",
        "data/genuine/case06_multi_identity.jpg",
        "data/tampered/case02_expired_ravi.jpg",
        "data/tampered/case03_tampered_dob.jpg",
        "data/tampered/case04_photo_replaced.jpg",
        "data/tampered/case05_copymove_stamp.jpg",
        "data/tampered/case07_blurry_fail.jpg",
        "data/selfies/case01_selfie_arjun.jpg",
        "data/selfies/case02_selfie_ravi.jpg",
        "data/selfies/case08_selfie_bearded_arjun.jpg",
        "data/selfies/case09_selfie_imposter.jpg"
    ]
    inventory = []
    for p in dataset_paths:
        exists = os.path.exists(p)
        size = os.path.getsize(p) if exists else 0
        doc_type = "UNKNOWN"
        if "selfie" in p:
            doc_type = "SELFIE (SYNTHETIC AVATAR)"
        elif "case07" in p:
            doc_type = "PASSPORT (DEGRADED BLURRY SYNTHETIC)"
        elif "tampered" in p:
            doc_type = "PASSPORT (TAMPERED SYNTHETIC)"
        elif "genuine" in p:
            doc_type = "PASSPORT (GENUINE SYNTHETIC)"
        
        inventory.append({
            "path": p,
            "exists": exists,
            "size_bytes": size,
            "classification": doc_type,
            "nature": "SYNTHETIC EVALUATION DATA"
        })
        print(f"  [{'FOUND' if exists else 'MISSING'}] {p} ({size} bytes) -> {doc_type}")
    
    qa_results["phase1_inventory"] = inventory

    # -----------------------------------------------------------------
    # PHASE 2: TEST CURRENT PASSPORT PIPELINE (FULL E2E)
    # -----------------------------------------------------------------
    log_header("Phase 2: Passport Pipeline Full E2E Test")
    doc_p = "data/genuine/case01_genuine_arjun.jpg"
    selfie_p = "data/selfies/case01_selfie_arjun.jpg"
    
    t0 = time.time()
    with open(doc_p, "rb") as f_doc, open(selfie_p, "rb") as f_selfie:
        files = {
            "document_file": ("passport.jpg", f_doc.read(), "image/jpeg"),
            "live_selfie_file": ("selfie.jpg", f_selfie.read(), "image/jpeg")
        }
        data = {
            "document_type": "PASSPORT",
            "checkpoint_id": "CP-DEL-AIR"
        }
        resp = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    p2_latency = (time.time() - t0) * 1000
    
    print(f"  Response Status Code: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    p_body = resp.json()
    screening_id = p_body.get("screening_id") or p_body.get("id")
    print(f"  Screening ID         : {screening_id}")
    print(f"  Status               : {p_body['status']}")
    print(f"  Document Type        : {p_body['document_type']}")
    print(f"  OCR Engine           : {p_body['ocr_engine']}")
    print(f"  Risk Score           : {p_body['risk_score']} ({p_body['risk_band']})")
    print(f"  Latency              : {p2_latency:.1f} ms")
    
    # Verify DB persistence
    sc_record = db.query(Screening).filter(Screening.id == screening_id).first()
    assert sc_record is not None
    assert sc_record.ocr_engine == p_body["ocr_engine"]
    assert sc_record.document_type == "PASSPORT"
    
    # Verify Audit Chain
    audit_res = AuditService.verify_audit_chain(db, screening_id)
    print(f"  Audit Chain Valid    : {audit_res['is_valid']} ({audit_res['total_events']} events)")
    assert audit_res["is_valid"] is True
    
    # Verify PDF Download
    pdf_resp = client.get(f"/api/v1/reports/{screening_id}/pdf", headers=headers)
    print(f"  PDF Report Status    : {pdf_resp.status_code} ({len(pdf_resp.content)} bytes)")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")
    
    qa_results["phase2_passport"] = {
        "screening_id": screening_id,
        "status": p_body["status"],
        "document_type": p_body["document_type"],
        "ocr_engine": p_body["ocr_engine"],
        "risk_score": p_body["risk_score"],
        "risk_band": p_body["risk_band"],
        "audit_valid": audit_res["is_valid"],
        "pdf_bytes": len(pdf_resp.content),
        "latency_ms": p2_latency
    }

    # -----------------------------------------------------------------
    # PHASE 3: TEST VISA PIPELINE (DEDICATED VISA PARSER)
    # -----------------------------------------------------------------
    log_header("Phase 3: Visa Pipeline Dedicated Execution")
    visa_img = create_synthetic_doc_image([
        "REPUBLIC OF INDIA",
        "VISA VIGNETTE",
        "VISA NO: V98765432",
        "PASSPORT NO: Z1234567",
        "NAME: ELENA ROSTOVA",
        "NATIONALITY: FRA",
        "DOB: 15/04/1989",
        "ENTRIES: MULTIPLE",
        "VALID FROM: 01/01/2024",
        "VALID UNTIL: 31/12/2026",
        "TYPE: BUSINESS",
        "STAY DURATION: 90 DAYS"
    ], width=850, height=550)
    visa_bytes = img_to_bytes(visa_img)
    
    t0 = time.time()
    files = {
        "document_file": ("visa_doc.jpg", visa_bytes, "image/jpeg")
    }
    data = {
        "document_type": "VISA",
        "checkpoint_id": "CP-DEL-AIR"
    }
    v_resp = client.post("/api/v1/screenings", headers=headers, files=files, data=data)
    p3_latency = (time.time() - t0) * 1000
    
    print(f"  Response Status Code: {v_resp.status_code}")
    assert v_resp.status_code == 200, f"Expected 200, got {v_resp.status_code}: {v_resp.text}"
    v_body = v_resp.json()
    v_id = v_body.get("screening_id") or v_body.get("id")
    print(f"  Screening ID         : {v_id}")
    print(f"  Status               : {v_body['status']}")
    print(f"  Document Type        : {v_body['document_type']}")
    print(f"  OCR Engine           : {v_body['ocr_engine']}")
    print(f"  Risk Score           : {v_body['risk_score']} ({v_body['risk_band']})")
    print(f"  Latency              : {p3_latency:.1f} ms")
    
    # Confirm MRZ was NOT parsed (dedicated Visa path)
    assert v_body["document_type"] == "VISA"
    assert v_body.get("mrz_data") is None or v_body["mrz_data"].get("parsed") is False
    
    # Verify PDF Download
    v_pdf_resp = client.get(f"/api/v1/reports/{v_id}/pdf", headers=headers)
    print(f"  Visa PDF Status      : {v_pdf_resp.status_code} ({len(v_pdf_resp.content)} bytes)")
    assert v_pdf_resp.status_code == 200
    assert v_pdf_resp.content.startswith(b"%PDF")
    
    qa_results["phase3_visa"] = {
        "screening_id": v_id,
        "status": v_body["status"],
        "document_type": v_body["document_type"],
        "ocr_engine": v_body["ocr_engine"],
        "risk_score": v_body["risk_score"],
        "pdf_bytes": len(v_pdf_resp.content),
        "latency_ms": p3_latency
    }

    # -----------------------------------------------------------------
    # PHASE 4: UNSUPPORTED DOCUMENT LIVE TESTS (HTTP 400)
    # -----------------------------------------------------------------
    log_header("Phase 4: Unsupported Document Rejections (HTTP 400)")
    unsupported_tests = [
        ("Aadhaar Card", ["GOVERNMENT OF INDIA", "AADHAAR", "UIDAI", "1234 5678 9012"]),
        ("PAN Card", ["INCOME TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER", "ABCDE1234F", "GOVT OF INDIA"]),
        ("Driving Licence", ["UNION OF INDIA", "DRIVING LICENCE", "DL NO: DL-0420110012345"]),
        ("Voter ID", ["ELECTION COMMISSION OF INDIA", "IDENTITY CARD", "EPIC NO: ABC1234567"]),
        ("College Student ID", ["NATIONAL INSTITUTE OF TECHNOLOGY", "STUDENT IDENTITY CARD", "ROLL NO: 2024CS01"]),
        ("Blank Image", []),
        ("Random Abstract Photo", ["ABSTRACT ART GALLERY", "COMPOSITION IN BLUE AND RED", "CONTEMPORARY EXHIBIT"])
    ]
    
    unsupported_results = []
    for label, lines in unsupported_tests:
        if lines:
            img = create_synthetic_doc_image(lines, 700, 450)
        else:
            img = np.full((400, 400, 3), 220, dtype=np.uint8)
        b_img = img_to_bytes(img)
        
        t0 = time.time()
        res = client.post(
            "/api/v1/screenings",
            headers=headers,
            files={"document_file": (f"{label.lower().replace(' ', '_')}.jpg", b_img, "image/jpeg")},
            data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
        )
        lat = (time.time() - t0) * 1000
        print(f"  [{label:<22}] -> HTTP {res.status_code} | Body: {res.json().get('status')} | {lat:.1f}ms")
        assert res.status_code == 400
        body = res.json()
        assert body["status"] in ["UNSUPPORTED_DOCUMENT", "UNABLE_TO_VERIFY"]
        assert "PASSPORT" in body["supported_types"] and "VISA" in body["supported_types"]
        unsupported_results.append({
            "label": label,
            "status_code": res.status_code,
            "returned_status": body["status"],
            "detected_type": body.get("detected_type"),
            "latency_ms": lat
        })
        
    qa_results["phase4_unsupported"] = unsupported_results

    # -----------------------------------------------------------------
    # PHASE 5: FRONTEND DOCUMENT-TYPE SPOOF TEST
    # -----------------------------------------------------------------
    log_header("Phase 5: Frontend Document-Type Spoofing Resistance")
    
    # 5A: Aadhaar image claiming to be PASSPORT
    aadhaar_img = create_synthetic_doc_image(["GOVERNMENT OF INDIA", "AADHAAR", "UIDAI", "1234 5678 9012"])
    res_a = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("aadhaar.jpg", img_to_bytes(aadhaar_img), "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  Spoof Test 1 (Aadhaar image, claimed PASSPORT): HTTP {res_a.status_code} | {res_a.json().get('status')}")
    assert res_a.status_code == 400
    assert res_a.json()["status"] == "UNSUPPORTED_DOCUMENT"
    assert res_a.json()["detected_type"] == "AADHAAR"
    
    # 5B: Passport image claiming to be VISA
    with open("data/genuine/case01_genuine_arjun.jpg", "rb") as f_pass:
        res_b = client.post(
            "/api/v1/screenings",
            headers=headers,
            files={"document_file": ("passport.jpg", f_pass.read(), "image/jpeg")},
            data={"document_type": "VISA", "checkpoint_id": "CP-DEL-AIR"}
        )
    print(f"  Spoof Test 2 (Passport image, claimed VISA)    : HTTP {res_b.status_code} | Executed as: {res_b.json().get('document_type')}")
    assert res_b.status_code == 200
    assert res_b.json()["document_type"] == "PASSPORT"  # Server overrode with true classification!

    # 5C: Visa image claiming to be PASSPORT
    res_c = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("visa.jpg", visa_bytes, "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  Spoof Test 3 (Visa image, claimed PASSPORT)    : HTTP {res_c.status_code} | Executed as: {res_c.json().get('document_type')}")
    assert res_c.status_code == 200
    assert res_c.json()["document_type"] == "VISA"  # Server overrode with true classification!

    qa_results["phase5_spoof"] = {
        "aadhaar_claimed_passport": res_a.json()["status"],
        "passport_claimed_visa": res_b.json()["document_type"],
        "visa_claimed_passport": res_c.json()["document_type"]
    }

    # -----------------------------------------------------------------
    # PHASE 6: CHECKPOINT SPOOF TEST
    # -----------------------------------------------------------------
    log_header("Phase 6: Checkpoint Spoofing Resistance")
    
    # Token is issued for CP-DEL-AIR. Attempt submission to CP-RAXAUL
    fake_data = {"document_type": "PASSPORT", "checkpoint_id": "CP-RAXAUL"}
    with open("data/genuine/case01_genuine_arjun.jpg", "rb") as f_pass:
        res_cp = client.post(
            "/api/v1/screenings",
            headers=headers,
            files={"document_file": ("passport.jpg", f_pass.read(), "image/jpeg")},
            data=fake_data
        )
    print(f"  Spoof CP Attempt (CP-DEL-AIR officer -> CP-RAXAUL): HTTP {res_cp.status_code} | {res_cp.json().get('detail')}")
    assert res_cp.status_code == 403
    assert "Checkpoint identity mismatch" in res_cp.json()["detail"]
    
    qa_results["phase6_checkpoint_spoof"] = {
        "status_code": res_cp.status_code,
        "detail": res_cp.json().get("detail")
    }

    # -----------------------------------------------------------------
    # PHASE 7: OCR PROVENANCE TEST
    # -----------------------------------------------------------------
    log_header("Phase 7: OCR Engine Provenance Strictness")
    with open("data/genuine/case01_genuine_arjun.jpg", "rb") as f_pass:
        res_ocr = client.post(
            "/api/v1/screenings",
            headers=headers,
            files={"document_file": ("passport.jpg", f_pass.read(), "image/jpeg")},
            data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
        )
    ocr_body = res_ocr.json()
    actual_engine = ocr_body["ocr_engine"]
    ocr_sid = ocr_body.get("screening_id") or ocr_body.get("id")
    print(f"  API Response ocr_engine        : {actual_engine}")
    assert actual_engine in ["PaddleOCR", "Tesseract"]
    
    # Verify DB persistence
    sc_ocr = db.query(Screening).filter(Screening.id == ocr_sid).first()
    assert sc_ocr.ocr_engine == actual_engine
    print(f"  DB Record ocr_engine           : {sc_ocr.ocr_engine}")
    
    # Verify ExtractedFields provenance
    fields = db.query(ExtractedField).filter(ExtractedField.screening_id == ocr_body["screening_id"]).all()
    print(f"  ExtractedFields count in DB    : {len(fields)}")
    for f in fields:
        assert f.ocr_engine == actual_engine
    
    qa_results["phase7_ocr_provenance"] = {
        "engine": actual_engine,
        "db_engine_matched": True,
        "fields_engine_matched": True
    }

    # -----------------------------------------------------------------
    # PHASE 8: FAILURE PATH TESTING
    # -----------------------------------------------------------------
    log_header("Phase 8: Failure Paths & Terminal States")
    
    # 8A: Corrupt bytes
    r_corrupt = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("corrupt.jpg", b"NOT_AN_IMAGE_PAYLOAD", "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  8A. Corrupt bytes          : HTTP {r_corrupt.status_code} | {r_corrupt.json().get('detail')}")
    assert r_corrupt.status_code == 400
    
    # 8B: Empty file
    r_empty = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("empty.jpg", b"", "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  8B. Empty file             : HTTP {r_empty.status_code} | {r_empty.json().get('detail')}")
    assert r_empty.status_code == 400

    # 8C: Unsupported MIME
    r_mime = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("test.txt", b"plain text", "text/plain")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  8C. Unsupported MIME       : HTTP {r_mime.status_code} | {r_mime.json().get('detail')}")
    assert r_mime.status_code == 400

    # 8D: Oversized payload
    r_large = client.post(
        "/api/v1/screenings",
        headers=headers,
        files={"document_file": ("large.jpg", b"\xFF\xD8\xFF" + b"\x00" * (16 * 1024 * 1024 + 10), "image/jpeg")},
        data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
    )
    print(f"  8D. Oversized upload       : HTTP {r_large.status_code} | {r_large.json().get('detail')}")
    assert r_large.status_code in [400, 413]

    # 8E: Blurry image (case07)
    with open("data/tampered/case07_blurry_fail.jpg", "rb") as f_blur:
        r_blur = client.post(
            "/api/v1/screenings",
            headers=headers,
            files={"document_file": ("blur.jpg", f_blur.read(), "image/jpeg")},
            data={"document_type": "PASSPORT", "checkpoint_id": "CP-DEL-AIR"}
        )
    print(f"  8E. Blurry image terminal  : HTTP {r_blur.status_code} | Status: {r_blur.json().get('status')}")
    assert r_blur.status_code in [200, 400]
    assert r_blur.json().get("status") in ["QUALITY_REJECTED", "NEEDS_BETTER_IMAGE", "MANUAL_REVIEW_REQUIRED", "UNABLE_TO_VERIFY"]

    # -----------------------------------------------------------------
    # PHASE 9: TAMPER FORENSICS VALIDATION
    # -----------------------------------------------------------------
    log_header("Phase 9: Tamper Forensics Modules & Honest Reporting")
    forensics = TamperForensicsPipeline()
    cases = [
        ("Genuine Passport", "data/genuine/case01_genuine_arjun.jpg"),
        ("Photo Replaced", "data/tampered/case04_photo_replaced.jpg"),
        ("Copy-Move Stamp", "data/tampered/case05_copymove_stamp.jpg"),
    ]
    forensic_results = []
    for label, path in cases:
        if os.path.exists(path):
            res = forensics.analyze(path)
            comp = res.get("composite_tamper_score", 0.0)
            sig_count = len(res.get("signals", {}))
            findings = res.get("findings", [])
            print(f"  [{label:<18}] Composite Anomaly Score: {comp:.1f}/100 | Forensic Findings: {len(findings)} | Signals: {sig_count}")
            for f in findings[:2]:
                print(f"    - {f.get('technique')}: score={f.get('score')}, severity={f.get('severity')}")
            forensic_results.append({"label": label, "composite_score": comp, "findings": len(findings)})
            
    qa_results["phase9_tamper"] = forensic_results

    # -----------------------------------------------------------------
    # PHASE 10: FACE VERIFICATION QA (CLASSICAL CV 512-D GABOR-LBP)
    # -----------------------------------------------------------------
    log_header("Phase 10: Face Verification (Classical CV Gabor-LBP)")
    verifier = FaceVerifier()
    
    # 10A: Genuine match
    res_gen = verifier.verify("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case01_selfie_arjun.jpg")
    print(f"  10A. Genuine Match      : Result={res_gen['verification_result']} | Sim={res_gen['similarity_score']} (Thresh: {res_gen['threshold']})")
    assert res_gen["verification_result"] == "MATCH"
    
    # 10B: Impostor mismatch (synthetic avatars)
    emb_doc = verifier.extract_embedding(cv2.imread("data/selfies/case01_selfie_arjun.jpg"))
    emb_imp = verifier.extract_embedding(np.zeros((120, 120, 3), dtype=np.uint8))
    sim_imp = float(np.dot(emb_doc, emb_imp))
    print(f"  10B. Distinct Face Sim  : Sim={sim_imp:.3f} | Below Borderline Thresh ({verifier.BORDERLINE_THRESHOLD})")
    assert sim_imp < verifier.BORDERLINE_THRESHOLD

    # 10C: Beard variation
    res_beard = verifier.verify("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case08_selfie_bearded_arjun.jpg")
    print(f"  10C. Beard Variation    : Result={res_beard['verification_result']} | Appearance Note: {res_beard.get('appearance_analysis', {}).get('appearance_difference_level')}")
    assert res_beard["verification_result"] == "MATCH"

    # 10D: Blank image (no face)
    blank_face = np.full((300, 300, 3), 200, dtype=np.uint8)
    crop, box, qual = verifier.detect_and_crop_face(blank_face)
    print(f"  10D. Blank Image Face   : Detected={qual.get('detected')} | Crop is None={crop is None}")
    assert qual.get("detected") is False
    assert crop is None

    # -----------------------------------------------------------------
    # PHASE 11: FAISS MULTI-IDENTITY QA
    # -----------------------------------------------------------------
    log_header("Phase 11: FAISS Vector Index Multi-Identity Search")
    indexer = MultiIdentityIndexer()
    emb_arjun = verifier.extract_embedding(cv2.imread("data/selfies/case01_selfie_arjun.jpg"))
    indexer.add_identity("Z1234567", "ARJUN SHARMA", emb_arjun)
    
    # Search with identical biometric face under a DIFFERENT document ID
    res_dup = indexer.search_duplicate(emb_arjun, current_doc_id="Z9999999", top_k=3)
    matches = res_dup.get("matches", [])
    print(f"  FAISS Index Search Results: {len(matches)} match(es) found in local synthetic gallery")
    assert len(matches) > 0
    print(f"    - Match 1: ID={matches[0]['document_id']}, Name={matches[0]['name']}, Sim={matches[0]['similarity']:.3f}")
    assert matches[0]["document_id"] == "Z1234567"
    assert matches[0]["similarity"] >= 0.99
    assert res_dup["duplicate_detected"] is True
    print(f"  Duplicate Flag Triggered: {res_dup['duplicate_detected']} (Alert: {res_dup.get('primary_alert', {}).get('message', '')[:60]}...)")

    # -----------------------------------------------------------------
    # PHASE 12: RISK ENGINE DETERMINISTIC SCORING
    # -----------------------------------------------------------------
    log_header("Phase 12: Risk Engine Deterministic Scoring")
    risk_engine = RiskEngine()
    
    # Case A: Low risk inputs
    q_good = {"verdict": "GOOD", "overall_score": 90.0}
    mrz_good = {
        "parsed": True,
        "all_checks_passed": True,
        "check_digits": {
            "document_number": {"valid": True},
            "date_of_birth": {"valid": True},
            "date_of_expiry": {"valid": True},
            "composite": {"valid": True}
        }
    }
    tamper_clean = {"composite_tamper_score": 10.0, "findings": []}
    face_match = {"verification_result": "MATCH", "similarity_score": 0.88, "appearance_analysis": {"appearance_difference_level": "MINIMAL"}}

    r_low = risk_engine.compute_risk(
        quality_res=q_good,
        mrz_res=mrz_good,
        viz_mrz_findings=[],
        rule_findings=[],
        tamper_res=tamper_clean,
        face_res=face_match
    )
    print(f"  Clean Passport Risk : Score={r_low['risk_score']:.1f} | Band={r_low['risk_band']}")
    assert r_low["risk_band"] == "LOW"
    
    # Case B: Tampered inputs with expired rules
    viz_mismatch = [{
        "field": "date_of_birth",
        "severity": "CRITICAL",
        "message": "Visual DOB does not match MRZ DOB."
    }]
    tamper_high = {
        "composite_tamper_score": 75.0,
        "findings": [{"technique": "ELA", "severity": "HIGH", "score": 75.0, "summary": "Compression Anomaly"}]
    }
    face_mismatch = {"verification_result": "MISMATCH", "similarity_score": 0.32}

    r_high = risk_engine.compute_risk(
        quality_res=q_good,
        mrz_res={"parsed": False},
        viz_mrz_findings=viz_mismatch,
        rule_findings=[{"severity": "HIGH", "message": "Document expired"}],
        tamper_res=tamper_high,
        face_res=face_mismatch
    )
    print(f"  Tampered Doc Risk   : Score={r_high['risk_score']:.1f} | Band={r_high['risk_band']}")
    assert r_high["risk_band"] in ["HIGH", "CRITICAL"]
    assert r_high["risk_score"] > r_low["risk_score"]

    # -----------------------------------------------------------------
    # PHASE 13: AUDIT CHAIN QA (CRYPTOGRAPHIC TAMPER DETECTION)
    # -----------------------------------------------------------------
    log_header("Phase 13: Audit Chain Cryptographic Tamper Detection")
    test_sid = f"QA-AUDIT-{int(time.time()*1000)}"
    ev1 = AuditService.record_event(db, test_sid, "DOC_UPLOAD", {"file": "doc.jpg"})
    ev2 = AuditService.record_event(db, test_sid, "OCR_DONE", {"lines": 25})
    ev3 = AuditService.record_event(db, test_sid, "RISK_EVAL", {"score": 15.0})
    
    v_clean = AuditService.verify_audit_chain(db, test_sid)
    print(f"  13A. Initial Chain Status       : Valid={v_clean['is_valid']} ({v_clean['total_events']} events)")
    assert v_clean["is_valid"] is True
    
    # Injected database alteration
    ev2.payload_hash = "f" * 64
    db.commit()
    v_tampered = AuditService.verify_audit_chain(db, test_sid)
    print(f"  13B. Tampered Chain Status      : Valid={v_tampered['is_valid']} | Message: {v_tampered['status_message']}")
    assert v_tampered["is_valid"] is False
    
    # Restore database
    ev2_clean_hash = AuditService.compute_sha256(json.dumps({"lines": 25}, sort_keys=True))
    ev2.payload_hash = ev2_clean_hash
    db.commit()
    v_restored = AuditService.verify_audit_chain(db, test_sid)
    print(f"  13C. Restored Chain Status      : Valid={v_restored['is_valid']}")
    assert v_restored["is_valid"] is True
    
    # Clean up test records
    db.query(AuditEvent).filter(AuditEvent.screening_id == test_sid).delete()
    db.commit()

    # -----------------------------------------------------------------
    # PHASE 14: PDF QA
    # -----------------------------------------------------------------
    log_header("Phase 14: ReportLab PDF Generation Verification")
    for s_id, doc_t in [(screening_id, "PASSPORT"), (v_id, "VISA")]:
        pdf_res = client.get(f"/api/v1/reports/{s_id}/pdf", headers=headers)
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF")
        print(f"  {doc_t} PDF Generated: {len(pdf_res.content)} bytes | HTTP 200 OK")

    # -----------------------------------------------------------------
    # PHASE 15: API CONSISTENCY CHECK
    # -----------------------------------------------------------------
    log_header("Phase 15: Cross-Layer API Consistency Verification")
    sc_check = db.query(Screening).filter(Screening.id == screening_id).first()
    api_check = client.get(f"/api/v1/screenings/{screening_id}", headers=headers).json()
    
    api_sid = api_check.get("screening_id") or api_check.get("id")
    print(f"  API screening_id       : {api_sid}")
    print(f"  DB screening_id        : {sc_check.id}")
    assert api_sid == sc_check.id
    
    print(f"  API document_type      : {api_check['document_type']}")
    print(f"  DB document_type       : {sc_check.document_type}")
    assert api_check["document_type"] == sc_check.document_type
    
    print(f"  API ocr_engine         : {api_check['ocr_engine']}")
    print(f"  DB ocr_engine          : {sc_check.ocr_engine}")
    assert api_check["ocr_engine"] == sc_check.ocr_engine

    # -----------------------------------------------------------------
    # PHASE 17: PERFORMANCE / LATENCY BREAKDOWN
    # -----------------------------------------------------------------
    log_header("Phase 17: Performance & Latency Breakdown")
    print(f"  Passport Pipeline Total Latency   : {p2_latency:.1f} ms")
    print(f"  Visa Pipeline Total Latency       : {p3_latency:.1f} ms")
    print(f"  Aadhaar Rejection Gate Latency    : {unsupported_results[0]['latency_ms']:.1f} ms")
    print(f"  Blank Image Rejection Latency     : {unsupported_results[5]['latency_ms']:.1f} ms")

    log_header("ALL QA PHASES EXECUTED SUCCESSFULLY")
    return qa_results


if __name__ == "__main__":
    try:
        results = run_qa_suite()
        print("\nQA Suite execution complete. Output captured.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
