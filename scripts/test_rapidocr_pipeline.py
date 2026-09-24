"""
Test RapidOCR integration with SatyaScan OCREngine, MRZ Parser, and Document Classifier.
"""

import os
import sys
import time
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.ocr.ocr_engine import OCREngine
from ai.mrz.mrz_parser import MRZParser
from ai.classifier.document_classifier import DocumentClassifier

from rapidocr_onnxruntime import RapidOCR

def test_engine_integration():
    print("=" * 70)
    print("RAPIDOCR + SATYASCAN OCR ENGINE VERIFICATION")
    print("=" * 70)
    
    cases = [
        ("Case 01 Genuine", "data/genuine/case01_genuine_arjun.jpg"),
        ("Case 02 Expired", "data/tampered/case02_expired_ravi.jpg"),
        ("Case 03 Tampered DOB", "data/tampered/case03_tampered_dob.jpg"),
        ("Case 04 Photo Replaced", "data/tampered/case04_photo_replaced.jpg"),
        ("Case 05 Copy-Move", "data/tampered/case05_copymove_stamp.jpg"),
        ("Case 06 Multi-ID", "data/genuine/case06_multi_identity.jpg"),
        ("Ref Visa 001", "data/reference/visas/PERSON-001_visa_ref.jpg"),
        ("Ref Visa 002", "data/reference/visas/PERSON-002_visa_ref.jpg"),
    ]

    rapid = RapidOCR()

    for name, rel_path in cases:
        full_p = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(full_p):
            continue
        
        cv_img = cv2.imread(full_p)
        t0 = time.perf_counter()
        res, elapse = rapid(cv_img)
        dt = time.perf_counter() - t0
        
        raw_items = []
        if res:
            for item in res:
                bx = item[0]
                txt = str(item[1]).strip()
                try:
                    sc = float(item[2])
                except Exception:
                    sc = 0.90
                raw_items.append({
                    "text": txt,
                    "confidence": round(sc, 4),
                    "box": bx
                })
        
        # Test field extraction using OCREngine's _extract_fields logic
        dummy_eng = OCREngine()
        fields, mrz_lines = dummy_eng._extract_fields(raw_items, "PaddleOCR")
        
        # Test MRZ parsing if >= 2 lines
        mrz_parsed = False
        all_passed = False
        if len(mrz_lines) >= 2:
            mrz_res = MRZParser.parse_td3(mrz_lines[-2], mrz_lines[-1])
            mrz_parsed = mrz_res.get("parsed", False)
            all_passed = mrz_res.get("all_checks_passed", False)
        
        # Count non-empty fields
        populated = {k: v["value"] for k, v in fields.items() if v and k != "document_type"}
        
        print(f"[{name:22s}] Time: {dt*1000:5.1f}ms | Lines: {len(raw_items):2d} | Fields: {len(populated):1d}/7 | MRZ: {len(mrz_lines)} (parsed={mrz_parsed}, checks={all_passed})")
        print(f"   Fields: {populated}")
        if mrz_lines:
            print(f"   MRZ Lines: {mrz_lines[:2]}")

if __name__ == "__main__":
    test_engine_integration()
