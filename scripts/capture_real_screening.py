import requests
import json
import os
import sys

BACKEND_URL = "https://satyascan-backend.onrender.com"
API_BASE = f"{BACKEND_URL}/api/v1"

DOC_PATH = "data/genuine/case01_genuine_arjun.jpg"
SELFIE_PATH = "data/selfies/case01_selfie_arjun.jpg"

ARTIFACT_DIR = "/Users/princemahto/.gemini/antigravity-ide/brain/b3033d63-4f18-4514-aad8-3a17ffd81b70"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

print("[1] Logging in...")
login_resp = requests.post(
    f"{API_BASE}/auth/login",
    json={"username": "delhi_airport", "password": "Demo@123", "checkpoint_id": "CP-DEL-AIR"},
    timeout=20
)
print("Login status:", login_resp.status_code)
if login_resp.status_code != 200:
    # Try alternative password
    login_resp = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": "officer", "password": "officer123", "checkpoint_id": "CP-DEL-AIR"},
        timeout=20
    )
    print("Alternative login status:", login_resp.status_code)

assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n[2] Uploading real document and selfie to POST /api/v1/screenings...")
with open(DOC_PATH, "rb") as f_doc, open(SELFIE_PATH, "rb") as f_selfie:
    files = {
        "document_file": ("passport.jpg", f_doc.read(), "image/jpeg"),
        "live_selfie_file": ("selfie.jpg", f_selfie.read(), "image/jpeg")
    }
    data = {
        "document_type": "PASSPORT",
        "checkpoint_id": "CP-DEL-AIR"
    }
    post_resp = requests.post(
        f"{API_BASE}/screenings",
        headers=headers,
        files=files,
        data=data,
        timeout=35
    )

print("POST /api/v1/screenings status:", post_resp.status_code)
assert post_resp.status_code == 200, f"POST screening failed: {post_resp.text}"
post_data = post_resp.json()
screening_id = post_data["id"]
print("Screening ID:", screening_id)

print("\n[3] Fetching GET /api/v1/screenings/{screening_id}...")
get_resp = requests.get(
    f"{API_BASE}/screenings/{screening_id}",
    headers=headers,
    timeout=20
)
print("GET /api/v1/screenings/{id} status:", get_resp.status_code)
assert get_resp.status_code == 200, f"GET screening failed: {get_resp.text}"
detail_data = get_resp.json()

# Save complete raw responses
raw_output = {
    "post_screening_response": post_data,
    "get_screening_detail_response": detail_data,
}

raw_path = os.path.join(ARTIFACT_DIR, "raw_production_response.json")
with open(raw_path, "w") as f:
    json.dump(raw_output, f, indent=2)
print(f"\n[4] Complete raw production response saved to {raw_path}")

# Test asset URLs from detail_data
print("\n[5] Testing Asset URLs from detail_data:")
asset_keys = [
    "doc_image_url",
    "live_image_url",
    "doc_face_url",
    "live_face_url",
    "ela_heatmap_url",
]

asset_results = {}
for k in asset_keys:
    raw_val = detail_data.get(k)
    print(f"\nKey: {k}")
    print(f"  Raw value: {raw_val}")
    if not raw_val:
        asset_results[k] = {"url": None, "status": "MISSING_IN_RESPONSE"}
        continue
    
    # Try fetching with Bearer header
    full_url = f"{BACKEND_URL}{raw_val}" if raw_val.startswith("/") else raw_val
    resp_bearer = requests.get(full_url, headers=headers, timeout=15)
    print(f"  Fetch with Bearer: {resp_bearer.status_code}, Content-Type: {resp_bearer.headers.get('content-type')}, Length: {len(resp_bearer.content)}")

    # Try fetching with query token ?token=...
    url_with_token = f"{full_url}?token={token}" if "?" not in full_url else f"{full_url}&token={token}"
    resp_query = requests.get(url_with_token, timeout=15)
    print(f"  Fetch with ?token: {resp_query.status_code}, Content-Type: {resp_query.headers.get('content-type')}, Length: {len(resp_query.content)}")

    # Try fetching without auth
    resp_noauth = requests.get(full_url, timeout=15)
    print(f"  Fetch without auth: {resp_noauth.status_code}")

    asset_results[k] = {
        "raw_val": raw_val,
        "bearer_status": resp_bearer.status_code,
        "bearer_ct": resp_bearer.headers.get("content-type"),
        "query_status": resp_query.status_code,
        "query_ct": resp_query.headers.get("content-type"),
        "noauth_status": resp_noauth.status_code,
    }

# Also test GET /api/v1/screenings/{id}/assets/{asset_name}
print("\n[6] Testing /api/v1/screenings/{id}/assets/{media_type} endpoints:")
for media_type in ["doc", "live", "heatmap", "doc_face", "live_face"]:
    url = f"{API_BASE}/screenings/{screening_id}/assets/{media_type}?token={token}"
    r = requests.get(url, timeout=15)
    print(f"  Asset {media_type}: {r.status_code}, Content-Type: {r.headers.get('content-type')}, Length: {len(r.content)}")

# Test PDF report endpoint
print("\n[7] Testing PDF report download...")
pdf_url = f"{API_BASE}/reports/{screening_id}/pdf?token={token}"
pdf_resp = requests.get(pdf_url, timeout=20)
print(f"  PDF report: {pdf_resp.status_code}, Content-Type: {pdf_resp.headers.get('content-type')}, Size: {len(pdf_resp.content)}")

# Save asset results to artifact
with open(os.path.join(ARTIFACT_DIR, "asset_test_results.json"), "w") as f:
    json.dump(asset_results, f, indent=2)

print("\nFinished Phase A test script successfully.")
