"""
SatyaScan Phase 4 — Final Production Render Performance Benchmark
Measures authentic live performance of SatyaScan backend on Render:
- Server version & commit verification
- Micro-benchmarks (/diag endpoint)
- Warm Case 01 screening latency & breakdown
- Warm Case 09 imposter screening latency & breakdown
- Biometric & forensic verification
- Concurrent health check stability under active screening load
"""

import time
import os
import sys
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
    resp = requests.post(login_url, json=payload, timeout=20)
    dt = time.perf_counter() - t0
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    print(f"[Auth] Logged in successfully in {dt:.2f}s. Token: {token[:12]}...")
    return token


def run_screening(token: str, doc_path: str, live_path: str, case_name: str) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"[{case_name}] Submitting real screening to Render...")
    print(f"=======================================================")
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
    resp = requests.post(screenings_url, headers=headers, files=files, data=data, timeout=60)
    round_trip = time.perf_counter() - t0

    print(f"[{case_name}] HTTP {resp.status_code} in {round_trip:.2f}s")
    if resp.status_code != 200:
        print(f"[{case_name}] Error response: {resp.text}")
        return {"status_code": resp.status_code, "error": resp.text, "round_trip_seconds": round_trip}

    res = resp.json()
    res["round_trip_seconds"] = round_trip
    res["server_timing"] = {
        "files_time": float(resp.headers.get("X-Files-Time", 0)),
        "class_time": float(resp.headers.get("X-Class-Time", 0)),
        "proc_time": float(resp.headers.get("X-Proc-Time", 0)),
        "total_server_time": float(resp.headers.get("X-Total-Server-Time", 0))
    }
    
    timing = res["server_timing"]
    print(f"[{case_name}] Timing breakdown:")
    print(f"  Files/Upload time     : {timing['files_time']:.3f}s")
    print(f"  Classification + OCR  : {timing['class_time']:.3f}s")
    print(f"  Process Pipeline      : {timing['proc_time']:.3f}s")
    print(f"  Total Server Time     : {timing['total_server_time']:.3f}s")
    print(f"  Client Round-Trip     : {round_trip:.3f}s")
    print(f"  Engine Used           : {res.get('ocr_engine')}")
    print(f"  Status / Risk         : {res.get('status')} | Score: {res.get('risk_score')} ({res.get('risk_band')})")
    print(f"  SFace Result          : {res.get('face_result', {}).get('verification_result')} (Similarity: {res.get('face_result', {}).get('similarity_score')})")
    print(f"  MRZ Parsed / Valid    : {res.get('mrz_data', {}).get('parsed')} / {res.get('mrz_data', {}).get('all_checks_passed')}")
    return res


def main():
    print("=" * 70)
    print("SATYASCAN PHASE 4 — FINAL RENDER PERFORMANCE VALIDATION")
    print("=" * 70)

    # 1. Health & Version Check
    t0 = time.perf_counter()
    h_resp = requests.get(f"{RENDER_BASE}/health", timeout=15)
    t_health = time.perf_counter() - t0
    assert h_resp.status_code == 200, f"Health check failed: {h_resp.status_code}"
    health_data = h_resp.json()
    print(f"[Health] Status: {health_data['status']} in {t_health:.3f}s")
    print(f"[Health] Version: {health_data.get('version')} | Commit: {health_data.get('commit')}")

    # 2. Diagnostic Micro-Benchmark
    diag_data = {}
    try:
        d_resp = requests.get(f"{RENDER_BASE}/diag", timeout=20)
        if d_resp.status_code == 200:
            diag_data = d_resp.json()
            print(f"[Diag] Tesseract Only Time : {diag_data.get('tesseract_only_time')}s")
            print(f"[Diag] Engine Process Time : {diag_data.get('engine_process_time')}s")
            print(f"[Diag] Engine Used         : {diag_data.get('engine_used')}")
    except Exception as e:
        print(f"[Diag] /diag check error: {e}")

    # 3. Authenticate
    token = get_auth_token()

    # 4. Warm-up call
    print("\n[Warmup] Warming container caches with Case 01...")
    warmup_res = run_screening(token, DOC_CASE01, LIVE_CASE01, "Warmup-Case01")

    # 5. Benchmark Case 01 (Warm Genuine)
    case01_res = run_screening(token, DOC_CASE01, LIVE_CASE01, "Benchmark-Case01-Genuine")

    # 6. Benchmark Case 09 (Warm Imposter)
    case09_res = run_screening(token, DOC_CASE01, LIVE_CASE09, "Benchmark-Case09-Imposter")

    # 7. Concurrency & Stability Evaluation
    print("\n=======================================================")
    print("[Concurrency] Testing Health Stability Under Load")
    print("=======================================================")
    health_results = []
    stop_event = threading.Event()

    def poller():
        while not stop_event.is_set():
            t_p0 = time.perf_counter()
            try:
                r = requests.get(f"{RENDER_BASE}/health", timeout=5)
                dt_p = time.perf_counter() - t_p0
                health_results.append((r.status_code, dt_p))
            except Exception as e:
                health_results.append(("ERR", -1))
            time.sleep(0.5)

    th = threading.Thread(target=poller, daemon=True)
    th.start()

    load_res = run_screening(token, DOC_CASE01, LIVE_CASE01, "Concurrency-Case01")
    stop_event.set()
    th.join(timeout=3)

    successful_pings = [h for h in health_results if h[0] == 200]
    error_pings = [h for h in health_results if h[0] != 200]
    avg_ping_ms = (sum(h[1] for h in successful_pings) / len(successful_pings) * 1000) if successful_pings else 0
    print(f"[Concurrency] Total pings: {len(health_results)} | Success: {len(successful_pings)} | Errors: {len(error_pings)} | Avg: {avg_ping_ms:.1f}ms")

    # Save benchmark summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "health": health_data,
        "diagnostic": diag_data,
        "case01_warm": {
            "round_trip_seconds": case01_res.get("round_trip_seconds"),
            "server_timing": case01_res.get("server_timing"),
            "engine": case01_res.get("ocr_engine"),
            "status": case01_res.get("status"),
            "risk_score": case01_res.get("risk_score"),
            "risk_band": case01_res.get("risk_band"),
            "face_similarity": case01_res.get("face_result", {}).get("similarity_score"),
            "mrz_valid": case01_res.get("mrz_data", {}).get("all_checks_passed"),
            "extracted_fields_count": len(case01_res.get("extracted_fields", []))
        },
        "case09_warm": {
            "round_trip_seconds": case09_res.get("round_trip_seconds"),
            "server_timing": case09_res.get("server_timing"),
            "engine": case09_res.get("ocr_engine"),
            "status": case09_res.get("status"),
            "risk_score": case09_res.get("risk_score"),
            "risk_band": case09_res.get("risk_band"),
            "face_similarity": case09_res.get("face_result", {}).get("similarity_score"),
            "face_verdict": case09_res.get("face_result", {}).get("verification_result")
        },
        "concurrency": {
            "total_health_pings": len(health_results),
            "successful_pings": len(successful_pings),
            "error_pings": len(error_pings),
            "avg_ping_latency_ms": round(avg_ping_ms, 1)
        }
    }

    out_path = "render_phase4_benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[Results] Saved benchmark summary to {out_path}")


if __name__ == "__main__":
    main()
