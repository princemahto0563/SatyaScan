import requests
import json
import time

BASE = "http://localhost:8000/api/v1"

print("==================================================")
print("SATYASCAN COMPLETE REAL PROTOTYPE SCREENING TEST")
print("==================================================")

# 1. Health
r_h = requests.get(f"{BASE}/health")
assert r_h.status_code == 200
h_data = r_h.json()
print(f"1. Health Check        : {h_data['status']} ({h_data['service']} v{h_data['version']})")

# 2. Login
r_auth = requests.post(f"{BASE}/auth/login", json={"username": "officer", "password": "officer123"})
assert r_auth.status_code == 200
auth_data = r_auth.json()
token = auth_data["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"2. Officer Login       : {auth_data['full_name']} [{auth_data['role']}] Badge: {auth_data['badge_number']}")

# 3. New Screening
doc_path = "data/genuine/case01_genuine_arjun.jpg"
selfie_path = "data/selfies/case01_selfie_arjun.jpg"

with open(doc_path, "rb") as f_doc, open(selfie_path, "rb") as f_selfie:
    files = {
        "document_file": ("case01_genuine_arjun.jpg", f_doc, "image/jpeg"),
        "live_selfie_file": ("case01_selfie_arjun.jpg", f_selfie, "image/jpeg")
    }
    data = {"document_type": "PASSPORT"}
    t0 = time.time()
    r_sc = requests.post(f"{BASE}/screenings", files=files, data=data, headers=headers)
    e2e_lat = round((time.time() - t0) * 1000, 1)

assert r_sc.status_code == 200, f"Screening failed: {r_sc.text}"
sc = r_sc.json()
case_id = sc["id"]

print(f"3. Screening Executed  : Case ID {case_id} in {e2e_lat}ms")
print(f"4. Quality Gate        : Verdict: {sc['quality_assessment']['verdict']} | Score: {sc['quality_assessment']['overall_score']}")
print(f"5. OCR Extracted       : {len(sc['extracted_fields'])} fields extracted")
print(f"6. MRZ Parsed          : {sc['mrz_data']['parsed']} | Country: {sc['mrz_data'].get('issuing_country')} | Name: {sc['mrz_data'].get('full_name')}")
print(f"7. Validation Findings : {len(sc['validation_findings'])} findings")
print(f"8. Tamper Score        : {sc['tamper_summary']['composite_tamper_score']}/100 (ELA: {sc['tamper_summary']['signals']['ela']['anomaly_score']})")

if sc.get("face_result"):
    print(f"9. Face Verification   : Similarity: {sc['face_result']['similarity_score']} | Verdict: {sc['face_result']['verification_result']} | Appearance: {sc['face_result']['appearance_level']}")
else:
    print(f"9. Face Verification   : Not run")

print(f"10. Risk Evaluation    : Score: {sc['risk_score']}/100 | Band: {sc['risk_band']}")
print(f"11. Recommendation     : {sc['recommendation']}")

# 12. Audit Trail
r_aud = requests.post(f"{BASE}/audit/{case_id}/verify")
assert r_aud.status_code == 200
aud = r_aud.json()
print(f"12. Audit Verification : Chain Valid: {aud['is_valid']} ({aud['total_events']} events verified)")

# 13. Local Notarization Adapter
r_anc = requests.post(f"{BASE}/audit/{case_id}/anchor")
assert r_anc.status_code == 200
anc = r_anc.json()
print(f"13. Local Notarization : Receipt Root: {anc['notarized_root_hash'][:16]}... | Block #{anc['block_number']}")

# 14. Report Generation
r_pdf = requests.get(f"{BASE}/reports/{case_id}/pdf")
assert r_pdf.status_code == 200
print(f"14. PDF Report Dossier : Downloaded {len(r_pdf.content)} bytes (ReportLab PDF format)")

# 15. Watchlist
r_wl = requests.get(f"{BASE}/watchlist")
assert r_wl.status_code == 200
print(f"15. Watchlist Records  : {len(r_wl.json())} active synthetic reference entries")

# 16. Analytics
r_ana = requests.get(f"{BASE}/analytics")
assert r_ana.status_code == 200
print(f"16. Analytics Engine   : Total Screenings: {r_ana.json()['summary']['total_screenings']}")

print("==================================================")
print("COMPLETE 16-STAGE WORKFLOW VERIFIED SUCCESSFULLY!")
print("==================================================")
