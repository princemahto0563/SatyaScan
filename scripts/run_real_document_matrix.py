"""
Real Document Test Matrix (Phase 13)
Executes all 15 required scenarios against the actual SatyaScan Screening Engine:
A. Genuine Passport Identity Page
B. Passport Cover
C. Genuine Visa
D. Unsupported image (e.g. random image/noise)
E. Blurry document
F. Passport + genuine face
G. Passport + different face
H. Missing live face
I. Missing document portrait
J. MRZ valid
K. MRZ invalid
L. MRZ absent/not applicable
M. VIZ/MRZ date-format equivalent
N. True VIZ/MRZ mismatch
O. True document-number mismatch
"""

import os
import sys
import json
import time
import numpy as np
import cv2

# Set path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.orchestrator import ScreeningOrchestrator

orchestrator = ScreeningOrchestrator()

cases = [
    {
        "id": "A",
        "name": "Genuine Passport Identity Page",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": "data/selfies/case01_selfie_arjun.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "B",
        "name": "Passport Cover",
        "doc_path": "data/reference/booklets/crop_cover_1df5fe5b.jpg",
        "live_path": "data/selfies/case01_selfie_arjun.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "C",
        "name": "Genuine Visa",
        "doc_path": "data/reference/visas/PERSON-001_visa_ref.jpg",
        "live_path": "data/reference/faces/PERSON-001_face_ref.jpg",
        "doc_type": "VISA",
    },
    {
        "id": "D",
        "name": "Unsupported / Irrelevant Image",
        "doc_path": "scratch/unsupported_noise.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
        "create_fixture": "noise"
    },
    {
        "id": "E",
        "name": "Blurry Document",
        "doc_path": "data/tampered/case07_blurry_fail.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    },
    {
        "id": "F",
        "name": "Passport + Genuine Face",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": "data/selfies/case01_selfie_arjun.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "G",
        "name": "Passport + Imposter / Different Face",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": "data/selfies/case09_selfie_imposter.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "H",
        "name": "Missing Live Face",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    },
    {
        "id": "I",
        "name": "Missing Document Portrait",
        "doc_path": "data/reference/booklets/crop_obs_1df5fe5b.jpg",
        "live_path": "data/selfies/case01_selfie_arjun.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "J",
        "name": "MRZ Valid",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    },
    {
        "id": "K",
        "name": "MRZ Invalid",
        "doc_path": "data/mutations/mrz_tampering/CASE-F09_mrz_checksum_invalid.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    },
    {
        "id": "L",
        "name": "MRZ Absent / Not Applicable",
        "doc_path": "data/reference/visas/PERSON-001_visa_ref.jpg",
        "live_path": None,
        "doc_type": "VISA",
    },
    {
        "id": "M",
        "name": "VIZ/MRZ Date-Format Equivalent",
        "doc_path": "data/genuine/case01_genuine_arjun.jpg",
        "live_path": "data/selfies/case01_selfie_arjun.jpg",
        "doc_type": "PASSPORT",
    },
    {
        "id": "N",
        "name": "True VIZ/MRZ Mismatch",
        "doc_path": "data/tampered/case03_tampered_dob.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    },
    {
        "id": "O",
        "name": "True Document-Number Mismatch",
        "doc_path": "data/mutations/document_number_tampering/CASE-F03_passport_num_altered.jpg",
        "live_path": None,
        "doc_type": "PASSPORT",
    }
]

# Ensure noise image exists for D
os.makedirs("scratch", exist_ok=True)
noise_img = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
cv2.imwrite("scratch/unsupported_noise.jpg", noise_img)

matrix_results = []

from backend.app.models.database import SessionLocal

db = SessionLocal()

print("=" * 80)
print("RUNNING SATYASCAN REAL-DOCUMENT TEST MATRIX (PHASE 13)")
print("=" * 80)

for c in cases:
    cid = c["id"]
    name = c["name"]
    doc_p = c["doc_path"]
    live_p = c["live_path"]
    dtype = c["doc_type"]
    
    t0 = time.time()
    res = orchestrator.process_screening(
        db=db,
        doc_image_path=doc_p,
        live_image_path=live_p if live_p and os.path.exists(live_p) else None,
        doc_type=dtype
    )
    duration = time.time() - t0
    
    ocr_st = res.get("ocr_status")
    page_type = res.get("page_type")
    is_id_page = res.get("is_identity_page")
    mrz_st = res.get("mrz_status")
    face_res = res.get("face_result") or {}
    face_st = face_res.get("decision_state") or face_res.get("status")
    similarity = face_res.get("similarity_score")
    risk_score = res.get("risk_score")
    terminal_status = res.get("status")
    
    extracted_summary = {
        f["field_name"]: f.get("visual_value") or f.get("field_value") or f.get("value")
        for f in res.get("extracted_fields", [])
        if f.get("visual_value") or f.get("field_value") or f.get("value")
    }
    
    summary = {
        "case_id": cid,
        "name": name,
        "document_type": res.get("document_type"),
        "page_type": page_type,
        "is_identity_page": is_id_page,
        "ocr_status": ocr_st,
        "extracted_fields_count": len(extracted_summary),
        "extracted_sample": list(extracted_summary.keys())[:5],
        "mrz_status": mrz_st,
        "mrz_parsed": bool(res.get("mrz_data") and res["mrz_data"].get("parsed")),
        "mrz_checks_passed": bool(res.get("mrz_data") and res["mrz_data"].get("all_checks_passed")),
        "face_state": face_st,
        "face_similarity": round(similarity, 4) if similarity is not None else None,
        "face_reason": face_res.get("reason"),
        "tamper_score": res.get("tamper_summary", {}).get("aggregate_score"),
        "risk_score": risk_score,
        "terminal_status": terminal_status,
        "latency_sec": round(duration, 3)
    }
    matrix_results.append(summary)
    
    print(f"[{cid}] {name:38} | Page: {page_type:20} | MRZ: {mrz_st:22} | Face: {str(face_st):16} | Term: {terminal_status} ({duration:.2f}s)")

with open("real_document_test_matrix_results.json", "w") as out:
    json.dump(matrix_results, out, indent=2)

print("=" * 80)
print("REAL DOCUMENT TEST MATRIX COMPLETED SUCCESSFULLY!")
print("Saved to: real_document_test_matrix_results.json")
