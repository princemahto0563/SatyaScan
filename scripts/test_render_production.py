"""
SatyaScan Phase 3 — Real Production / Render Performance Validation
Tests the live deployed Render API against Case 01 and Case 09,
measures latency, evaluates stability and concurrent /health pings,
and reports authentic production metrics.
"""

import time
import os
import json
import threading
import requests
from typing import Dict, Any, List

RENDER_BASE = "https://satyascan-backend.onrender.com"
API_BASE = f"{RENDER_BASE}/api/v1"

DOC_CASE01 = "data/genuine/case01_genuine_arjun.jpg"
LIVE_CASE01 = "data/selfies/case01_selfie_arjun.jpg"
LIVE_CASE09 = "data/selfies/case09_selfie_imposter.jpg"


def get_auth_token() -> str:
    print("[Auth] Authenticating against Render API as officer...")
    login_url = f"{API_BASE}/auth/login"
    payload = {
        "username": "officer",
        "password": "officer123",
        "checkpoint_id": "CP-DEL-AIR"
    }
    t0 = time.perf_counter()
    resp = requests.post(login_url, json=payload, timeout=15)
    dt = time.perf_counter() - t0
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    print(f"[Auth] Logged in successfully in {dt:.2f}s. Token: {token[:12]}...")
    return token


def run_single_screening(token: str, doc_path: str, live_path: str, case_name: str) -> Dict[str, Any]:
    print(f"\n[{case_name}] Submitting real multipart screening to Render...")
    screenings_url = f"{API_BASE}/screenings"
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(doc_path, "rb") as f_doc, open(live_path, "rb") as f_live:
        files = {
            "document_file": ("document.jpg", f_doc.read(), "image/jpeg"),
            "live_selfie_file": ("selfie.jpg", f_live.read(), "image/jpeg")
        }
        data = {
            "document_type": "PASSPORT",
            "checkpoint_id": "CP-DEL-AIR"
        }

    t0 = time.perf_counter()
    resp = requests.post(screenings_url, headers=headers, files=files, data=data, timeout=120)
    round_trip = time.perf_counter() - t0

    print(f"[{case_name}] HTTP {resp.status_code} in {round_trip:.2f}s")
    if resp.status_code != 200:
        print(f"[{case_name}] Error response: {resp.text}")
        return {"status_code": resp.status_code, "error": resp.text, "round_trip": round_trip}

    res = resp.json()
    res["round_trip_seconds"] = round_trip
    res["server_timing"] = {
        "files_time": resp.headers.get("X-Files-Time"),
        "class_time": resp.headers.get("X-Class-Time"),
        "proc_time": resp.headers.get("X-Proc-Time"),
        "total_server_time": resp.headers.get("X-Total-Server-Time")
    }
    print(f"[{case_name}] Timing breakdown: Files={res['server_timing']['files_time']}s | Classify={res['server_timing']['class_time']}s | Process={res['server_timing']['proc_time']}s | TotalServer={res['server_timing']['total_server_time']}s | RoundTrip={round_trip:.2f}s")
    return res


def test_health_concurrency(token: str):
    print("\n=== Testing Concurrency & Health Stability Under Load ===")
    health_results = []
    stop_event = threading.Event()

    def health_poller():
        while not stop_event.is_set():
            t0 = time.perf_counter()
            try:
                r = requests.get(f"{RENDER_BASE}/health", timeout=5)
                dt = time.perf_counter() - t0
                health_results.append((r.status_code, dt, time.strftime("%H:%M:%S")))
            except Exception as e:
                health_results.append(("ERR", -1, str(e)))
            time.sleep(1.0)

    poller_thread = threading.Thread(target=health_poller, daemon=True)
    poller_thread.start()

    # Run 1 screening while polling
    print("\n--- Running Screening #1 during health polling ---")
    res1 = run_single_screening(token, DOC_CASE01, LIVE_CASE01, "Case01-During-Health")

    # Run 2 back-to-back screenings
    print("\n--- Running Back-to-Back Screenings ---")
    res2 = run_single_screening(token, DOC_CASE01, LIVE_CASE09, "Case09-B2B-1")
    res3 = run_single_screening(token, DOC_CASE01, LIVE_CASE01, "Case01-B2B-2")

    stop_event.set()
    poller_thread.join(timeout=3)

    print(f"\n[Health Poller Summary] Total pings during screening: {len(health_results)}")
    success_pings = [h for h in health_results if h[0] == 200]
    latencies = [h[1] for h in success_pings]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0

    print(f"  Pings successful: {len(success_pings)} / {len(health_results)}")
    print(f"  Average health ping latency: {avg_lat*1000:.1f}ms")
    print(f"  Maximum health ping latency: {max_lat*1000:.1f}ms")
    
    return {
        "total_pings": len(health_results),
        "successful_pings": len(success_pings),
        "avg_latency_ms": round(avg_lat * 1000, 1),
        "max_latency_ms": round(max_lat * 1000, 1),
        "health_results": health_results
    }


if __name__ == "__main__":
    token = get_auth_token()
    print("\n--- 1. Testing Case 01 Genuine ---")
    c1 = run_single_screening(token, DOC_CASE01, LIVE_CASE01, "Case 01")
    
    print("\n--- 2. Testing Case 09 Imposter ---")
    c9 = run_single_screening(token, DOC_CASE01, LIVE_CASE09, "Case 09")
    
    print("\n--- 3. Testing Health Concurrency ---")
    hc = test_health_concurrency(token)

    output = {
        "case01": c1,
        "case09": c9,
        "health_concurrency": hc
    }
    with open("render_performance_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nSaved full results to render_performance_results.json")
