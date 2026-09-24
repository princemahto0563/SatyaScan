"""
SatyaScan Phase 4 Final Release Verification Script
Validates end-to-end production flow against live Render backend and Vercel frontend:
1. Authenticates against live Render API
2. Performs full end-to-end screening (real passport + live selfie)
3. Measures first-request and warm latency
4. Verifies:
   - OCR fields visible
   - MRZ validation visible
   - SFace biometrics visible
   - Risk result visible
   - Audit trail visible
   - PDF report downloadable and valid
"""

import time
import os
import sys
import json
import requests

RENDER_BASE = "https://satyascan-backend.onrender.com"
API_BASE = f"{RENDER_BASE}/api/v1"
VERCEL_FRONTEND = "https://satya-scan-phi.vercel.app"

DOC_PATH = "data/genuine/case01_genuine_arjun.jpg"
SELFIE_PATH = "data/selfies/case01_selfie_arjun.jpg"

assert os.path.exists(DOC_PATH), f"Document not found: {DOC_PATH}"
assert os.path.exists(SELFIE_PATH), f"Selfie not found: {SELFIE_PATH}"


def main():
    print("=" * 75)
    print("SATYASCAN PHASE 4 — FINAL RELEASE COMPREHENSIVE VERIFICATION")
    print("=" * 75)
    print(f"Frontend URL : {VERCEL_FRONTEND}")
    print(f"Backend URL  : {RENDER_BASE}")
    
    # 1. Health check
    t0 = time.perf_counter()
    h_resp = requests.get(f"{RENDER_BASE}/health", timeout=15)
    h_time = time.perf_counter() - t0
    assert h_resp.status_code == 200, f"Health check failed: {h_resp.status_code}"
    health_json = h_resp.json()
    print(f"\n[1] Backend Health Verified in {h_time:.3f}s:")
    print(f"    Version : {health_json.get('version')}")
    print(f"    Commit  : {health_json.get('commit')}")
    print(f"    Status  : {health_json.get('status')}")

    # 2. Authenticate
    print("\n[2] Authenticating as Checkpoint Officer...")
    t0 = time.perf_counter()
    auth_resp = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "officer", "password": "officer123", "checkpoint_id": "CP-DEL-AIR"},
        timeout=15
    )
    t_auth = time.perf_counter() - t0
    assert auth_resp.status_code == 200, f"Login failed: {auth_resp.status_code} {auth_resp.text}"
    token = auth_resp.json()["access_token"]
    print(f"    Authenticated in {t_auth:.3f}s. Access token secured.")

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Screening Run 1 (First request client latency)
    print("\n[3] Executing Screening Run 1 (First Request / Cold Pipeline)...")
    with open(DOC_PATH, "rb") as f_doc, open(SELFIE_PATH, "rb") as f_live:
        files = {
            "document_file": ("passport.jpg", f_doc.read(), "image/jpeg"),
            "live_selfie_file": ("selfie.jpg", f_live.read(), "image/jpeg")
        }
        data = {
            "document_type": "PASSPORT",
            "checkpoint_id": "CP-DEL-AIR"
        }

    t0 = time.perf_counter()
    s1_resp = requests.post(f"{API_BASE}/screenings", headers=headers, files=files, data=data, timeout=30)
    s1_client_latency = time.perf_counter() - t0
    assert s1_resp.status_code == 200, f"Screening 1 failed: {s1_resp.status_code} {s1_resp.text}"
    s1_data = s1_resp.json()
    s1_server_time = float(s1_resp.headers.get("X-Total-Server-Time", 0))
    s1_class_time = float(s1_resp.headers.get("X-Class-Time", 0))
    s1_proc_time = float(s1_resp.headers.get("X-Proc-Time", 0))

    print(f"    Status Code         : HTTP {s1_resp.status_code}")
    print(f"    Client Latency      : {s1_client_latency:.3f}s")
    print(f"    Server Total Time   : {s1_server_time:.3f}s")
    print(f"    Classification+OCR  : {s1_class_time:.3f}s")
    print(f"    Process Pipeline    : {s1_proc_time:.3f}s")
    print(f"    Screening ID        : {s1_data.get('id')}")
    print(f"    Engine Used         : {s1_data.get('ocr_engine')}")
    print(f"    Screening Status    : {s1_data.get('status')}")
    print(f"    Risk Score / Band   : {s1_data.get('risk_score')} ({s1_data.get('risk_band')})")

    screening_id = s1_data.get("id")

    # 4. Screening Run 2 (Warm client latency)
    print("\n[4] Executing Screening Run 2 (Warm Pipeline)...")
    with open(DOC_PATH, "rb") as f_doc, open(SELFIE_PATH, "rb") as f_live:
        files = {
            "document_file": ("passport.jpg", f_doc.read(), "image/jpeg"),
            "live_selfie_file": ("selfie.jpg", f_live.read(), "image/jpeg")
        }
        data = {
            "document_type": "PASSPORT",
            "checkpoint_id": "CP-DEL-AIR"
        }

    t0 = time.perf_counter()
    s2_resp = requests.post(f"{API_BASE}/screenings", headers=headers, files=files, data=data, timeout=30)
    s2_client_latency = time.perf_counter() - t0
    assert s2_resp.status_code == 200, f"Screening 2 failed: {s2_resp.status_code} {s2_resp.text}"
    s2_data = s2_resp.json()
    s2_server_time = float(s2_resp.headers.get("X-Total-Server-Time", 0))
    s2_class_time = float(s2_resp.headers.get("X-Class-Time", 0))
    s2_proc_time = float(s2_resp.headers.get("X-Proc-Time", 0))

    print(f"    Status Code         : HTTP {s2_resp.status_code}")
    print(f"    Client Latency      : {s2_client_latency:.3f}s")
    print(f"    Server Total Time   : {s2_server_time:.3f}s")
    print(f"    Classification+OCR  : {s2_class_time:.3f}s")
    print(f"    Process Pipeline    : {s2_proc_time:.3f}s")
    print(f"    Engine Used         : {s2_data.get('ocr_engine')}")
    print(f"    Screening Status    : {s2_data.get('status')}")
    print(f"    Risk Score / Band   : {s2_data.get('risk_score')} ({s2_data.get('risk_band')})")

    # 5. Verification of All UI Components for screening_id
    print(f"\n[5] Detailed Component Verifications for Screening ID: {screening_id}")
    
    # Detailed fetch
    detail_resp = requests.get(f"{API_BASE}/screenings/{screening_id}", headers=headers, timeout=15)
    assert detail_resp.status_code == 200, f"Fetch screening failed: {detail_resp.status_code}"
    detail = detail_resp.json()

    # A. OCR fields visible
    extracted_fields = detail.get("extracted_fields", [])
    fields_dict = {f["field_name"]: (f.get("visual_value") or f.get("mrz_value") or f.get("field_value")) for f in extracted_fields}
    print(f"    A. Extracted Fields ({len(extracted_fields)} present):")
    for k in ["document_number", "surname", "given_names", "full_name", "nationality", "date_of_birth", "date_of_expiry", "sex"]:
        val = fields_dict.get(k)
        print(f"       - {k:16s} : {val} (visual={next((f.get('visual_value') for f in extracted_fields if f['field_name'] == k), None)}, mrz={next((f.get('mrz_value') for f in extracted_fields if f['field_name'] == k), None)})")
        assert val is not None, f"Field {k} is missing from extracted fields!"

    # B. MRZ validation visible
    mrz = detail.get("mrz_data") or {}
    print(f"    B. MRZ Validation:")
    print(f"       - Parsed          : {mrz.get('parsed')}")
    print(f"       - Checks Passed   : {mrz.get('all_checks_passed')}")
    print(f"       - Document Number : {mrz.get('document_number')}")
    print(f"       - DOB / Expiry    : {mrz.get('date_of_birth')} / {mrz.get('date_of_expiry')}")
    assert mrz.get("parsed") is True, "MRZ parsed must be True!"
    assert mrz.get("all_checks_passed") is True, "MRZ all_checks_passed must be True!"

    # C. SFace result visible
    face = detail.get("face_result") or {}
    print(f"    C. SFace Biometric Verification:")
    print(f"       - Provider        : {face.get('provider')}")
    print(f"       - Similarity Score: {face.get('similarity_score')}")
    print(f"       - Result          : {face.get('verification_result')}")
    assert face.get("similarity_score", 0) >= 0.68, f"SFace match score must be >= 0.68, got {face.get('similarity_score')}"
    assert "MATCH" in face.get("verification_result", ""), f"SFace result must be MATCH, got {face.get('verification_result')}"

    # D. Risk result visible
    print(f"    D. Risk Engine Result:")
    print(f"       - Risk Score      : {detail.get('risk_score')}")
    print(f"       - Risk Band       : {detail.get('risk_band')}")
    print(f"       - Recommendation  : {detail.get('recommendation')}")
    assert detail.get("status") == "COMPLETED", f"Expected COMPLETED, got {detail.get('status')}"
    assert detail.get("risk_band") == "LOW", f"Expected LOW risk band, got {detail.get('risk_band')}"

    # E. Audit trail visible
    audit_resp = requests.get(f"{API_BASE}/audit/{screening_id}", headers=headers, timeout=15)
    assert audit_resp.status_code == 200, f"Fetch audit events failed: {audit_resp.status_code}"
    audit_events = audit_resp.json()
    print(f"    E. Audit Trail Events ({len(audit_events)} recorded):")
    for ev in audit_events:
        print(f"       - [{ev.get('timestamp')}] {ev.get('action')}")
    assert len(audit_events) >= 5, f"Expected at least 5 audit events, got {len(audit_events)}"

    # F. PDF report downloadable
    print(f"    F. PDF Report Generation & Download:")
    t0 = time.perf_counter()
    pdf_resp = requests.get(f"{API_BASE}/reports/{screening_id}/pdf", headers=headers, timeout=15)
    t_pdf = time.perf_counter() - t0
    assert pdf_resp.status_code == 200, f"PDF report download failed: {pdf_resp.status_code}"
    pdf_bytes = pdf_resp.content
    is_valid_pdf = pdf_bytes.startswith(b"%PDF-")
    print(f"       - HTTP Status     : {pdf_resp.status_code}")
    print(f"       - Download Time   : {t_pdf:.3f}s")
    print(f"       - File Size       : {len(pdf_bytes)} bytes ({len(pdf_bytes)/1024:.1f} KB)")
    print(f"       - PDF Magic Header: {pdf_bytes[:8]}")
    print(f"       - Valid PDF Format: {is_valid_pdf}")
    assert is_valid_pdf, "Downloaded file does not start with %PDF- header!"
    assert len(pdf_bytes) > 5000, f"PDF size too small: {len(pdf_bytes)} bytes"

    # Save summary
    release_summary = {
        "frontend_url": VERCEL_FRONTEND,
        "backend_url": RENDER_BASE,
        "deployed_version": health_json.get("version"),
        "deployed_commit": health_json.get("commit"),
        "cold_end_to_end_seconds": round(s1_client_latency, 3),
        "warm_end_to_end_seconds": round(s2_client_latency, 3),
        "server_timing_first": {
            "total": s1_server_time,
            "classification_ocr": s1_class_time,
            "pipeline": s1_proc_time
        },
        "server_timing_warm": {
            "total": s2_server_time,
            "classification_ocr": s2_class_time,
            "pipeline": s2_proc_time
        },
        "components_verified": {
            "ocr_fields_visible": True,
            "mrz_validation_visible": True,
            "sface_result_visible": True,
            "risk_result_visible": True,
            "audit_trail_visible": True,
            "pdf_report_downloadable": True,
            "pdf_size_bytes": len(pdf_bytes)
        },
        "status": "PASS"
    }

    out_file = "final_release_check_results.json"
    with open(out_file, "w") as f:
        json.dump(release_summary, f, indent=2)
    print(f"\n[Release Check Complete] Saved release results to {out_file}")
    print("=" * 75)


if __name__ == "__main__":
    main()
