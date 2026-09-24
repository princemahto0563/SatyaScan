"""
Deep Profiling and Benchmarking Script for SatyaScan OCR Engine.
Measures execution time and field accuracy across candidate configurations.
"""

import os
import sys
import time
import cv2
import numpy as np
import pytesseract
from typing import Dict, Any, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.ocr.ocr_engine import OCREngine
from ai.mrz.mrz_parser import MRZParser

TEST_DOCS = [
    ("Case01 Passport Genuine", "data/genuine/case01_genuine_arjun.jpg"),
    ("Case02 Passport Expired", "data/tampered/case02_expired_ravi.jpg"),
    ("Case03 Passport Tampered DOB", "data/tampered/case03_tampered_dob.jpg"),
    ("Case06 Passport Multi-ID", "data/genuine/case06_multi_identity.jpg"),
    ("Reference Visa 001", "data/reference/visas/PERSON-001_visa_ref.jpg"),
]


def profile_tesseract_internals(img_path: str):
    print("=" * 60)
    print(f"PROFILE INTERNALS: {os.path.basename(img_path)}")
    print("=" * 60)
    
    # 1. Decode
    t0 = time.perf_counter()
    img = cv2.imread(img_path)
    t_decode = time.perf_counter() - t0
    h, w = img.shape[:2]
    print(f"1. cv2.imread decode: {t_decode*1000:.2f}ms (Shape: {w}x{h})")

    # 2. Preprocessing variations
    # 2a. Grayscale
    t0 = time.perf_counter()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    t_gray = time.perf_counter() - t0
    print(f"2a. cv2.cvtColor BGR2GRAY: {t_gray*1000:.2f}ms")

    # 2b. Gaussian blur + unsharp mask (Phase 3 baseline)
    t0 = time.perf_counter()
    gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
    sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)
    t_sharp = time.perf_counter() - t0
    print(f"2b. Gaussian blur + unsharp mask: {t_sharp*1000:.2f}ms")

    # 2c. Otsu Threshold
    t0 = time.perf_counter()
    _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    t_otsu = time.perf_counter() - t0
    print(f"2c. Otsu threshold: {t_otsu*1000:.2f}ms")

    # 3. Tesseract image_to_data vs image_to_string on FULL sharpened image (Baseline)
    t0 = time.perf_counter()
    d_base = pytesseract.image_to_data(sharpened, output_type=pytesseract.Output.DICT)
    t_base = time.perf_counter() - t0
    print(f"3a. BASELINE full image_to_data (sharpened, default PSM 3, with DAWGs): {t_base*1000:.2f}ms | words: {len([w for w in d_base['text'] if w.strip()])}")

    # 3b. Without sharpening (raw grayscale)
    t0 = time.perf_counter()
    d_raw_gray = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    t_raw_gray = time.perf_counter() - t0
    print(f"3b. Raw gray image_to_data (default PSM 3, with DAWGs): {t_raw_gray*1000:.2f}ms")

    # 3c. Raw gray image_to_data without DAWGs (-c load_system_dawg=0 -c load_freq_dawg=0)
    t0 = time.perf_counter()
    d_nodawg = pytesseract.image_to_data(gray, config="-c load_system_dawg=0 -c load_freq_dawg=0", output_type=pytesseract.Output.DICT)
    t_nodawg = time.perf_counter() - t0
    print(f"3c. Raw gray image_to_data (PSM 3, NO DAWGs): {t_nodawg*1000:.2f}ms")

    # 4. PSM Modes on Raw Gray (no DAWGs)
    for psm in [3, 4, 6, 11, 12]:
        t0 = time.perf_counter()
        try:
            d_psm = pytesseract.image_to_data(gray, config=f"--psm {psm} -c load_system_dawg=0 -c load_freq_dawg=0", output_type=pytesseract.Output.DICT)
            words = [w for w in d_psm['text'] if w.strip()]
            dt = time.perf_counter() - t0
            print(f"4. PSM {psm:2d} image_to_data (no DAWGs): {dt*1000:.2f}ms | non-empty tokens: {len(words)}")
        except Exception as e:
            print(f"4. PSM {psm:2d} failed: {e}")

    # 5. image_to_string vs image_to_data
    t0 = time.perf_counter()
    s_full = pytesseract.image_to_string(gray, config="--psm 6 -c load_system_dawg=0 -c load_freq_dawg=0")
    t_str = time.perf_counter() - t0
    print(f"5. PSM  6 image_to_string (no DAWGs): {t_str*1000:.2f}ms | lines: {len(s_full.splitlines())}")

    # 6. Geometric Crops (Passport Fast Path)
    # MRZ crop: bottom 30%
    mrz_crop = gray[int(h * 0.70):, :]
    t0 = time.perf_counter()
    mrz_txt = pytesseract.image_to_string(
        mrz_crop,
        config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789< -c load_system_dawg=0 -c load_freq_dawg=0"
    )
    t_mrz = time.perf_counter() - t0
    mrz_lines = [l.strip().upper().replace(" ", "") for l in mrz_txt.splitlines() if len(l.strip()) >= 20 and ("<" in l or l.startswith("P"))]
    print(f"6a. MRZ crop PSM 6 (whitelist, no DAWGs): {t_mrz*1000:.2f}ms | lines detected: {len(mrz_lines)}")
    for l in mrz_lines:
        print(f"    -> {l}")

    # VIZ crop: upper 72%
    viz_crop = gray[:int(h * 0.72), :]
    t0 = time.perf_counter()
    d_viz = pytesseract.image_to_data(viz_crop, config="--psm 6 -c load_system_dawg=0 -c load_freq_dawg=0", output_type=pytesseract.Output.DICT)
    t_viz = time.perf_counter() - t0
    viz_words = [w for w in d_viz['text'] if w.strip()]
    print(f"6b. VIZ crop PSM 6 image_to_data: {t_viz*1000:.2f}ms | words: {len(viz_words)}")

    t_combined = t_mrz + t_viz
    speedup = (t_base / max(t_combined, 0.001))
    print(f"-> Combined Fast-Path Time (MRZ crop + VIZ crop): {t_combined*1000:.2f}ms vs Baseline: {t_base*1000:.2f}ms ({speedup:.2f}x faster)")


if __name__ == "__main__":
    for name, path in TEST_DOCS:
        full_p = os.path.join(PROJECT_ROOT, path)
        if os.path.exists(full_p):
            profile_tesseract_internals(full_p)
