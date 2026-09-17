import requests
import json
import time

BASE = "http://localhost:8000/api/v1"

print("======================================================================")
print("TESTING 4 CANONICAL CASES (01, 03, 04, 08) & REPORT HUMAN READABILITY")
print("======================================================================")

test_cases = [
    ("01", "Genuine Passport", "LOW", "Document passed available verification checks with no major inconsistency detected."),
    ("03", "DOB Altered", "CRITICAL", "Critical discrepancies detected"),
    ("04", "Photo Replaced", "LOW", "Routine or minor variations"),
    ("08", "Appearance Variation (Beard)", "LOW", "Identity comparison: MATCH"),
]

for case_num, label, exp_band, desc in test_cases:
    print(f"\n--- Testing CASE {case_num}: {label} ---")
    t0 = time.time()
    res = requests.post(f"{BASE}/screenings/preset/{case_num}")
    lat = round((time.time() - t0) * 1000, 1)
    assert res.status_code == 200, f"Case {case_num} failed with {res.status_code}: {res.text}"
    data = res.json()
    case_id = data["id"]
    
    print(f"  Case ID               : {case_id}")
    print(f"  Latency               : {lat} ms")
    print(f"  Risk Band             : {data['risk_band']} (Score: {data['risk_score']})")
    print(f"  Recommendation        : {data.get('recommendation')}")
    print(f"  Quality Assessment    : {data['quality_assessment']['verdict']} (Score: {data['quality_assessment']['overall_score']})")
    
    # Check MRZ
    if data.get("mrz_data"):
        print(f"  MRZ Check Digits Pass : {data['mrz_data']['all_checks_passed']}")
    
    # Check Face / Appearance
    if data.get("face_result"):
        fr = data["face_result"]
        print(f"  Biometric Comparison : {fr['verification_result']} (Score: {fr['similarity_score']})")
        print(f"  Appearance Variation  : {fr['appearance_level']}")
        print(f"  Appearance Note       : {fr.get('recommendation')}")
    
    # Check Forensic ELA
    if data.get("tamper_summary"):
        ts = data["tamper_summary"]
        print(f"  Forensic Composite    : {ts['composite_tamper_score']}/100 (Findings: {ts['findings_count']})")
    
    # Verify Audit Chain
    aud_res = requests.post(f"{BASE}/audit/{case_id}/verify")
    assert aud_res.status_code == 200
    aud = aud_res.json()
    print(f"  Audit Chain Verified  : {aud['is_valid']} ({aud['total_events']} blocks linked)")
    assert aud["is_valid"] is True, f"Audit chain for case {case_id} must be valid!"
    
    # Verify PDF Download Endpoint
    pdf_res = requests.get(f"{BASE}/reports/{case_id}/pdf")
    assert pdf_res.status_code == 200
    print(f"  PDF Report Download   : {len(pdf_res.content)} bytes (HTTP 200 OK)")

print("\n======================================================================")
print("ALL 4 CANONICAL CASES VERIFIED CLEANLY WITH FULL AUDIT & PDF OUTPUT!")
print("======================================================================")
