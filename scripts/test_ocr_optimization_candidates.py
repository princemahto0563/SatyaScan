"""
Benchmark OCR Optimization Candidates:
Evaluates execution speed and extraction accuracy across test cases.
Checks:
- Candidate 0: Baseline (Phase 3 currently in production: sharpened + full image_to_data + second MRZ pass)
- Candidate 1: Single Pass Raw Gray PSM 6 + No DAWGs
- Candidate 2: Single Pass Raw Gray PSM 3 + No DAWGs
- Candidate 3: Two-Crop: MRZ Crop (bottom 30%, PSM 6, whitelist, no DAWGs) + VIZ Crop (top 72%, PSM 6, no DAWGs)
- Candidate 4: Scaled Two-Crop: MRZ Crop + VIZ Crop with optimal downscale
- Candidate 5: Single Pass with Bounded Dim (800px vs 1000px vs 1200px)
"""

import os
import sys
import time
import cv2
import numpy as np
import pytesseract
import re
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.mrz.mrz_parser import MRZParser

TEST_DOCS = [
    ("Case01", os.path.join(PROJECT_ROOT, "data/genuine/case01_genuine_arjun.jpg"), "PASSPORT"),
    ("Case02", os.path.join(PROJECT_ROOT, "data/tampered/case02_expired_ravi.jpg"), "PASSPORT"),
    ("Case03", os.path.join(PROJECT_ROOT, "data/tampered/case03_tampered_dob.jpg"), "PASSPORT"),
    ("Case06", os.path.join(PROJECT_ROOT, "data/genuine/case06_multi_identity.jpg"), "PASSPORT"),
    ("Visa001", os.path.join(PROJECT_ROOT, "data/reference/visas/PERSON-001_visa_ref.jpg"), "VISA"),
    ("Visa002", os.path.join(PROJECT_ROOT, "data/reference/visas/PERSON-002_visa_ref.jpg"), "VISA"),
]

def extract_fields_from_tokens(items: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    fields = {
        "passport_number": None,
        "surname": None,
        "given_names": None,
        "full_name": None,
        "nationality": None,
        "date_of_birth": None,
        "date_of_expiry": None,
        "sex": None
    }
    mrz_lines = []
    for item in items:
        t = item["text"].replace(" ", "").upper()
        if (t.startswith("P<") or t.startswith("P0") or t.startswith("P«") or t.count("<") >= 4) and len(t) >= 20:
            mrz_lines.append(item["text"])

    doc_num_pattern = re.compile(r'\b([A-Z][0-9]{7,8})\b')
    date_pattern = re.compile(r'\b(\d{1,2}[\/\-\s][A-Za-z]{3,9}[\/\-\s]\d{4}|\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b')

    for i, item in enumerate(items):
        raw = item["text"]
        text = raw.upper()
        conf = item["confidence"]
        box = item["box"]
        lookahead = items[i + 1 : min(len(items), i + 4)]

        if not fields["passport_number"]:
            match = doc_num_pattern.search(text)
            if match and "REPUBLIC" not in text and "PASSPORT" not in text:
                fields["passport_number"] = {"value": match.group(1), "confidence": conf}
            elif any(k in text for k in ["PASSPORT NO", "PASSPORT NUMBER", "DOCUMENT NO", "PASSEPORT"]):
                for la in lookahead:
                    la_match = doc_num_pattern.search(la["text"].upper())
                    if la_match:
                        fields["passport_number"] = {"value": la_match.group(1), "confidence": la["confidence"]}
                        break

        if not fields["surname"] and any(k in text for k in ["SURNAME", "NOM"]):
            cleaned = re.sub(r'.*(SURNAME|NOM)[\s\:\./]*', '', text).strip()
            if len(cleaned) >= 2 and cleaned.replace(" ", "").isalpha():
                fields["surname"] = {"value": cleaned, "confidence": conf}
            else:
                for la in lookahead:
                    la_t = la["text"].strip()
                    if len(la_t) >= 2 and la_t.replace(" ", "").isalpha() and not any(k in la_t.upper() for k in ["NAME", "GIVEN", "SURNAME", "NATIONALITY", "PASSPORT"]):
                        fields["surname"] = {"value": la_t, "confidence": la["confidence"]}
                        break

        if not fields["given_names"] and any(k in text for k in ["GIVEN NAME", "PRENOM", "PRENOW"]):
            cleaned = re.sub(r'.*(GIVEN NAME|PRENOM|PRENOW)[\s\:\./]*', '', text).strip()
            if len(cleaned) >= 2 and cleaned.replace(" ", "").isalpha():
                fields["given_names"] = {"value": cleaned, "confidence": conf}
            else:
                for la in lookahead:
                    la_t = la["text"].strip()
                    if len(la_t) >= 2 and la_t.replace(" ", "").isalpha() and not any(k in la_t.upper() for k in ["NAME", "GIVEN", "PRENOM", "PRENOW", "SURNAME", "NATIONALITY", "PASSPORT"]):
                        fields["given_names"] = {"value": la_t, "confidence": la["confidence"]}
                        break

        if not fields["date_of_birth"] and any(k in text for k in ["BIRTH", "DOB", "NAISSANCE", "JANM"]):
            m = date_pattern.search(raw)
            if m:
                fields["date_of_birth"] = {"value": m.group(1), "confidence": conf}
            else:
                for la in lookahead:
                    la_m = date_pattern.search(la["text"])
                    if la_m:
                        fields["date_of_birth"] = {"value": la_m.group(1), "confidence": la["confidence"]}
                        break

        if not fields["date_of_expiry"] and any(k in text for k in ["EXPIRY", "EXPIRATION", "VALID", "EXP"]):
            m = date_pattern.search(raw)
            if m:
                fields["date_of_expiry"] = {"value": m.group(1), "confidence": conf}
            else:
                for la in lookahead:
                    la_m = date_pattern.search(la["text"])
                    if la_m:
                        fields["date_of_expiry"] = {"value": la_m.group(1), "confidence": la["confidence"]}
                        break

        if not fields["nationality"] and ("NATIONALITY" in text or "CITIZENSHIP" in text or "INDIAN" in text):
            fields["nationality"] = {"value": "INDIAN" if "INDIAN" in text else "IND", "confidence": conf}

        if not fields["sex"] and re.search(r'\b(SEX|GENDER|SEXE)\b', text):
            if re.search(r'\bM\b|\bMALE\b', text):
                fields["sex"] = {"value": "MALE", "confidence": conf}
            elif re.search(r'\bF\b|\bFEMALE\b', text):
                fields["sex"] = {"value": "FEMALE", "confidence": conf}

    # Full name composition
    if fields["surname"] and fields["given_names"]:
        fields["full_name"] = {"value": f"{fields['given_names']['value']} {fields['surname']['value']}".strip()}
    elif fields["given_names"]:
        fields["full_name"] = {"value": fields["given_names"]["value"]}
    elif fields["surname"]:
        fields["full_name"] = {"value": fields["surname"]["value"]}

    return fields, mrz_lines


def run_candidate_0_baseline(cv_img: np.ndarray) -> Tuple[float, Dict[str, Any], List[str]]:
    """Phase 3 Production Baseline: Sharpened + Full image_to_data + MRZ fallback"""
    t0 = time.perf_counter()
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
    sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)
    data = pytesseract.image_to_data(sharpened, output_type=pytesseract.Output.DICT)
    
    n_boxes = len(data['text'])
    line_collector = {}
    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        if text and conf > 15:
            block_num = data['block_num'][i]
            par_num = data['par_num'][i]
            line_num = data['line_num'][i]
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            poly = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            line_key = (block_num, par_num, line_num)
            line_collector.setdefault(line_key, []).append({
                "text": text, "conf": conf / 100.0, "box": poly, "x": x, "y": y
            })

    sorted_keys = sorted(line_collector.keys(), key=lambda k: min(t["y"] for t in line_collector[k]))
    raw_items = []
    for l_key in sorted_keys:
        tokens = sorted(line_collector[l_key], key=lambda t: t["x"])
        joined_text = " ".join(t["text"] for t in tokens)
        avg_conf = sum(t["conf"] for t in tokens) / len(tokens)
        min_x = min(t["box"][0][0] for t in tokens)
        min_y = min(t["box"][0][1] for t in tokens)
        max_x = max(t["box"][1][0] for t in tokens)
        max_y = max(t["box"][2][1] for t in tokens)
        raw_items.append({
            "text": joined_text,
            "confidence": round(avg_conf, 4),
            "box": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
        })

    fields, mrz_lines = extract_fields_from_tokens(raw_items)
    
    # Baseline second pass if mrz_lines < 2
    if len(mrz_lines) < 2:
        ih, iw = cv_img.shape[:2]
        mrz_crop = cv_img[int(ih * 0.70):, :]
        gray_crop = cv2.cvtColor(mrz_crop, cv2.COLOR_BGR2GRAY)
        crop_txt = pytesseract.image_to_string(
            gray_crop,
            config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        )
        for line in crop_txt.splitlines():
            clean_l = line.strip().upper().replace(" ", "")
            if ("<" in clean_l or clean_l.startswith("P")) and len(clean_l) >= 20:
                if clean_l not in mrz_lines:
                    mrz_lines.append(clean_l)

    dt = time.perf_counter() - t0
    return dt, fields, mrz_lines


def run_candidate_1_single_pass_psm6(cv_img: np.ndarray) -> Tuple[float, Dict[str, Any], List[str]]:
    """Candidate 1: Single Pass Raw Gray PSM 6 without DAWGs"""
    t0 = time.perf_counter()
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    cfg = "--psm 6 -c load_system_dawg=0 -c load_freq_dawg=0"
    data = pytesseract.image_to_data(gray, config=cfg, output_type=pytesseract.Output.DICT)
    
    n_boxes = len(data['text'])
    line_collector = {}
    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        if text and conf > 15:
            block_num = data['block_num'][i]
            par_num = data['par_num'][i]
            line_num = data['line_num'][i]
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            line_key = (block_num, par_num, line_num)
            line_collector.setdefault(line_key, []).append({
                "text": text, "conf": conf / 100.0,
                "box": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                "x": x, "y": y
            })

    sorted_keys = sorted(line_collector.keys(), key=lambda k: min(t["y"] for t in line_collector[k]))
    raw_items = []
    for l_key in sorted_keys:
        tokens = sorted(line_collector[l_key], key=lambda t: t["x"])
        joined_text = " ".join(t["text"] for t in tokens)
        avg_conf = sum(t["conf"] for t in tokens) / len(tokens)
        min_x = min(t["box"][0][0] for t in tokens)
        min_y = min(t["box"][0][1] for t in tokens)
        max_x = max(t["box"][1][0] for t in tokens)
        max_y = max(t["box"][2][1] for t in tokens)
        raw_items.append({
            "text": joined_text, "confidence": round(avg_conf, 4),
            "box": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
        })

    fields, mrz_lines = extract_fields_from_tokens(raw_items)
    dt = time.perf_counter() - t0
    return dt, fields, mrz_lines


def run_candidate_3_geometry_two_crop(cv_img: np.ndarray) -> Tuple[float, Dict[str, Any], List[str]]:
    """Candidate 3: Geometry Two-Crop (MRZ strip crop PSM 6 whitelist + VIZ crop PSM 6 no DAWGs)"""
    t0 = time.perf_counter()
    ih, iw = cv_img.shape[:2]
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # 1. MRZ Crop (bottom 30%)
    mrz_y0 = int(ih * 0.70)
    mrz_crop = gray[mrz_y0:, :]
    mrz_cfg = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789< -c load_system_dawg=0 -c load_freq_dawg=0"
    mrz_txt = pytesseract.image_to_string(mrz_crop, config=mrz_cfg)
    mrz_lines = [l.strip().upper().replace(" ", "") for l in mrz_txt.splitlines() if len(l.strip()) >= 20 and ("<" in l or l.startswith("P"))]

    # 2. VIZ Crop (top 72%)
    viz_crop = gray[:int(ih * 0.72), :]
    viz_cfg = "--psm 6 -c load_system_dawg=0 -c load_freq_dawg=0"
    data = pytesseract.image_to_data(viz_crop, config=viz_cfg, output_type=pytesseract.Output.DICT)
    
    n_boxes = len(data['text'])
    line_collector = {}
    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        if text and conf > 15:
            block_num = data['block_num'][i]
            par_num = data['par_num'][i]
            line_num = data['line_num'][i]
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            line_key = (block_num, par_num, line_num)
            line_collector.setdefault(line_key, []).append({
                "text": text, "conf": conf / 100.0,
                "box": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                "x": x, "y": y
            })

    sorted_keys = sorted(line_collector.keys(), key=lambda k: min(t["y"] for t in line_collector[k]))
    raw_items = []
    for l_key in sorted_keys:
        tokens = sorted(line_collector[l_key], key=lambda t: t["x"])
        joined_text = " ".join(t["text"] for t in tokens)
        avg_conf = sum(t["conf"] for t in tokens) / len(tokens)
        min_x = min(t["box"][0][0] for t in tokens)
        min_y = min(t["box"][0][1] for t in tokens)
        max_x = max(t["box"][1][0] for t in tokens)
        max_y = max(t["box"][2][1] for t in tokens)
        raw_items.append({
            "text": joined_text, "confidence": round(avg_conf, 4),
            "box": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
        })

    fields, _ = extract_fields_from_tokens(raw_items)
    dt = time.perf_counter() - t0
    return dt, fields, mrz_lines


def benchmark_all():
    print("=" * 80)
    print("SATYASCAN OCR OPTIMIZATION BENCHMARK MATRIX")
    print("=" * 80)

    candidates = [
        ("Candidate 0: Baseline (Sharpened + PSM 3 + Fallback)", run_candidate_0_baseline),
        ("Candidate 1: Single Pass Raw Gray (PSM 6, No DAWGs)", run_candidate_1_single_pass_psm6),
        ("Candidate 3: Geometry Two-Crop (MRZ Whitelist + VIZ PSM 6)", run_candidate_3_geometry_two_crop),
    ]

    for doc_name, doc_path, doc_type in TEST_DOCS:
        if not os.path.exists(doc_path):
            continue
        print(f"\n--- Testing Document: {doc_name} ({doc_type}) ---")
        img = cv2.imread(doc_path)
        
        for cand_name, fn in candidates:
            # Run 2 iterations to ensure warm timing
            fn(img)
            dt, fields, mrz_lines = fn(img)
            
            # Count populated fields
            valid_fields = {k: v["value"] for k, v in fields.items() if v}
            mrz_parsed = False
            if len(mrz_lines) >= 2:
                parsed = MRZParser.parse_td3(mrz_lines[-2], mrz_lines[-1])
                mrz_parsed = parsed.get("parsed", False)
            
            print(f"  [{cand_name[:25]:25s}] Time: {dt*1000:6.1f}ms | Fields: {len(valid_fields)}/8 | MRZ: {len(mrz_lines)} lines (parsed={mrz_parsed})")
            if "Case01" in doc_name:
                print(f"       Extracted: PassNo={valid_fields.get('passport_number')} | Name={valid_fields.get('full_name')} | DOB={valid_fields.get('date_of_birth')} | Exp={valid_fields.get('date_of_expiry')}")
            elif "Case03" in doc_name:
                print(f"       Extracted: PassNo={valid_fields.get('passport_number')} | VIZ DOB={valid_fields.get('date_of_birth')}")

if __name__ == "__main__":
    benchmark_all()
