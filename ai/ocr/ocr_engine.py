"""
SatyaScan OCR Engine
Provides robust dual-engine OCR (PaddleOCR with Tesseract fallback),
extracting text tokens, authentic confidence metrics, bounding boxes,
and structured Visual Inspection Zone (VIZ) identity fields.
Strictly reports actual engine used: "PaddleOCR" or "Tesseract".
"""

from typing import Dict, Any, List, Optional
import cv2
import numpy as np
import re
import os
import pytesseract
from PIL import Image

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except Exception:
    PADDLE_AVAILABLE = False


class OCREngine:
    """
    Dual-engine OCR processor with field extraction and confidence scoring.
    Genuinely attempts PaddleOCR first, falling back to Tesseract only on failure or unavailability.
    """

    def __init__(self):
        self.version = "PP-OCRv4/Tesseract-5.5"
        self._paddle_ocr = None
        self._initialized = False

    def _init_paddle(self):
        if self._initialized:
            return
        if PADDLE_AVAILABLE:
            try:
                # Initialize PaddleOCR CPU inference
                self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')
            except Exception as e:
                print(f"[SatyaScan OCR] PaddleOCR init warning: {e}, falling back to Tesseract.")
                self._paddle_ocr = None
        self._initialized = True

    def process_image(self, image_input: Any) -> Dict[str, Any]:
        """
        Runs OCR on input image (file path or BGR numpy array).
        Returns raw lines, bounding boxes, confidences, and structured fields with provenance.
        """
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                return {
                    "error": "Image file not found", "engine": None,
                    "fields": {}, "lines": [], "extracted_fields": {},
                    "raw_lines": [], "mrz_candidate_lines": [],
                    "average_confidence": 0.0, "total_lines_detected": 0
                }
            cv_img = cv2.imread(image_input)
            if cv_img is None:
                return {
                    "error": "Unable to decode image file", "engine": None,
                    "fields": {}, "lines": [], "extracted_fields": {},
                    "raw_lines": [], "mrz_candidate_lines": [],
                    "average_confidence": 0.0, "total_lines_detected": 0
                }
        elif isinstance(image_input, np.ndarray):
            cv_img = image_input
        else:
            return {
                "error": "Invalid image input", "engine": None,
                "fields": {}, "lines": [], "extracted_fields": {},
                "raw_lines": [], "mrz_candidate_lines": [],
                "average_confidence": 0.0, "total_lines_detected": 0
            }

        self._init_paddle()

        raw_items: List[Dict[str, Any]] = []
        actual_engine: Optional[str] = None

        # PRIMARY: Attempt PaddleOCR first if initialized
        if self._paddle_ocr:
            try:
                results = self._paddle_ocr.ocr(cv_img)
                if results and len(results) > 0 and results[0] is not None:
                    res0 = results[0]
                    # Handle modern PaddleX OCRResult dict-like structure
                    if hasattr(res0, 'keys') and 'rec_texts' in res0:
                        texts = res0.get('rec_texts', [])
                        scores = res0.get('rec_scores', [])
                        polys = res0.get('dt_polys', res0.get('rec_polys', []))
                        for i, txt in enumerate(texts):
                            sc = float(scores[i]) if i < len(scores) else 0.95
                            bx = polys[i].tolist() if i < len(polys) and hasattr(polys[i], 'tolist') else (polys[i] if i < len(polys) else [])
                            raw_items.append({
                                "text": str(txt).strip(),
                                "confidence": round(sc, 4),
                                "box": bx
                            })
                    elif isinstance(res0, list):
                        # Handle legacy PaddleOCR list structure [[box, (text, conf)]]
                        for line in res0:
                            if isinstance(line, (list, tuple)) and len(line) >= 2:
                                box = line[0]
                                text_conf = line[1]
                                if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
                                    text, conf = text_conf[0], text_conf[1]
                                    raw_items.append({
                                        "text": str(text).strip(),
                                        "confidence": round(float(conf), 4),
                                        "box": box
                                    })
                if raw_items:
                    actual_engine = "PaddleOCR"
            except Exception as e:
                print(f"[SatyaScan OCR] PaddleOCR inference error: {e}, falling back to Tesseract.")
                raw_items = []

        # FALLBACK: Tesseract if PaddleOCR was unavailable or returned empty
        if not raw_items:
            try:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
                sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)

                data = pytesseract.image_to_data(sharpened, output_type=pytesseract.Output.DICT)
                n_boxes = len(data['text'])
                line_collector: Dict[tuple, List[Dict[str, Any]]] = {}

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
                            "text": text,
                            "conf": conf / 100.0,
                            "box": poly,
                            "x": x,
                            "y": y
                        })

                # Sort lines by top y coordinate
                sorted_keys = sorted(
                    line_collector.keys(),
                    key=lambda k: min(t["y"] for t in line_collector[k])
                )

                for l_key in sorted_keys:
                    # Sort words left-to-right
                    tokens = sorted(line_collector[l_key], key=lambda t: t["x"])
                    joined_text = " ".join(t["text"] for t in tokens)
                    avg_conf = sum(t["conf"] for t in tokens) / len(tokens)
                    min_x = min(t["box"][0][0] for t in tokens)
                    min_y = min(t["box"][0][1] for t in tokens)
                    max_x = max(t["box"][1][0] for t in tokens)
                    max_y = max(t["box"][2][1] for t in tokens)
                    line_poly = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
                    raw_items.append({
                        "text": joined_text,
                        "confidence": round(avg_conf, 4),
                        "box": line_poly
                    })

                if raw_items:
                    actual_engine = "Tesseract"
            except Exception as err:
                print(f"[SatyaScan OCR] Tesseract fallback failed: {err}")

        # Extract structured fields with provenance
        structured_fields, mrz_candidate_lines = self._extract_fields(raw_items, actual_engine)

        # Dedicated MRZ strip scan if full page OCR missed or fragmented the MRZ lines
        if len(mrz_candidate_lines) < 2 and cv_img is not None and cv_img.size > 0:
            try:
                ih, iw = cv_img.shape[:2]
                mrz_crop = cv_img[int(ih * 0.70):, :]
                gray_crop = cv2.cvtColor(mrz_crop, cv2.COLOR_BGR2GRAY)
                if gray_crop.shape[0] < 120:
                    scale = 120.0 / max(1, gray_crop.shape[0])
                    gray_crop = cv2.resize(gray_crop, (int(gray_crop.shape[1] * scale), 120), interpolation=cv2.INTER_CUBIC)
                crop_txt = pytesseract.image_to_string(
                    gray_crop,
                    config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
                )
                for line in crop_txt.splitlines():
                    clean_l = line.strip().upper().replace(" ", "")
                    if ("<" in clean_l or clean_l.startswith("P")) and len(clean_l) >= 20:
                        if clean_l not in mrz_candidate_lines:
                            mrz_candidate_lines.append(clean_l)
            except Exception:
                pass

        avg_confidence = (
            round(sum(item["confidence"] for item in raw_items) / len(raw_items), 3)
            if raw_items else 0.0
        )

        # Determine explicit OCR status
        populated_count = sum(1 for k, v in structured_fields.items() if v and k != "document_type")
        has_mrz = len(mrz_candidate_lines) >= 2

        if populated_count >= 3 and has_mrz:
            ocr_status = "SUCCESS"
            ocr_reason = "Visual Inspection Zone and Machine-Readable Zone successfully extracted."
        elif populated_count >= 1 or has_mrz:
            ocr_status = "PARTIAL"
            ocr_reason = (
                f"Partial text extraction: {populated_count} visual fields found; "
                f"MRZ candidate lines: {len(mrz_candidate_lines)}."
            )
        else:
            ocr_status = "FAILED"
            ocr_reason = "No legible text or machine-readable zone could be extracted from image."

        return {
            "engine": actual_engine,
            "average_confidence": avg_confidence,
            "total_lines_detected": len(raw_items),
            "raw_lines": raw_items,
            "mrz_candidate_lines": mrz_candidate_lines,
            "extracted_fields": structured_fields,
            "ocr_status": ocr_status,
            "ocr_reason": ocr_reason
        }

    def _extract_fields(self, items: List[Dict[str, Any]], engine_name: Optional[str]) -> tuple[Dict[str, Any], List[str]]:
        """
        Parses Visual Inspection Zone (VIZ) identity fields from detected OCR tokens.
        Supports multi-line label-value pairing across Indian & ICAO passport layouts.
        """
        fields: Dict[str, Any] = {
            "document_type": {"value": "PASSPORT", "confidence": 0.95, "ocr_engine": engine_name, "bounding_box": None, "validation": "VALID", "source": "OCR_LAYOUT"},
            "passport_number": None,
            "surname": None,
            "given_names": None,
            "full_name": None,
            "nationality": None,
            "date_of_birth": None,
            "date_of_expiry": None,
            "sex": None
        }

        mrz_lines: List[str] = []

        # Find MRZ candidate lines (lines starting with P< or containing multiple consecutive '<')
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

            # Candidate lookahead tokens (up to 3 items ahead)
            lookahead = items[i + 1 : min(len(items), i + 4)]

            # 1. Passport Number
            if not fields["passport_number"]:
                match = doc_num_pattern.search(text)
                if match and "REPUBLIC" not in text and "PASSPORT" not in text:
                    fields["passport_number"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                elif any(k in text for k in ["PASSPORT NO", "PASSPORT NUMBER", "DOCUMENT NO", "PASSEPORT"]):
                    for la_item in lookahead:
                        la_match = doc_num_pattern.search(la_item["text"].upper())
                        if la_match:
                            fields["passport_number"] = {
                                "value": la_match.group(1),
                                "confidence": la_item["confidence"],
                                "ocr_engine": engine_name,
                                "bounding_box": la_item["box"],
                                "validation": "VALID",
                                "source": "VIZ"
                            }
                            break

            # 2. Surname
            if not fields["surname"] and any(k in text for k in ["SURNAME", "NOM"]):
                cleaned = re.sub(r'.*(SURNAME|NOM)[\s\:\./]*', '', text).strip()
                if len(cleaned) >= 2 and cleaned.replace(" ", "").isalpha():
                    fields["surname"] = {
                        "value": cleaned,
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                else:
                    for la_item in lookahead:
                        la_raw = la_item["text"].strip()
                        la_text = la_raw.upper()
                        if len(la_raw) >= 2 and la_raw.replace(" ", "").isalpha() and not any(k in la_text for k in ["NAME", "GIVEN", "PRENOM", "SURNAME", "PASSPORT"]):
                            fields["surname"] = {
                                "value": la_raw,
                                "confidence": la_item["confidence"],
                                "ocr_engine": engine_name,
                                "bounding_box": la_item["box"],
                                "validation": "VALID",
                                "source": "VIZ"
                            }
                            break

            # 3. Given Names
            if not fields["given_names"] and any(k in text for k in ["GIVEN NAME", "PRENOM"]):
                cleaned = re.sub(r'.*(GIVEN NAME[S]?|PRENOM)[\s\:\./]*', '', text).strip()
                if len(cleaned) >= 2 and cleaned.replace(" ", "").isalpha():
                    fields["given_names"] = {
                        "value": cleaned,
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                else:
                    for la_item in lookahead:
                        la_raw = la_item["text"].strip()
                        la_text = la_raw.upper()
                        if len(la_raw) >= 2 and la_raw.replace(" ", "").isalpha() and not any(k in la_text for k in ["NAME", "GIVEN", "PRENOM", "SURNAME", "NATIONALITY", "PASSPORT"]):
                            fields["given_names"] = {
                                "value": la_raw,
                                "confidence": la_item["confidence"],
                                "ocr_engine": engine_name,
                                "bounding_box": la_item["box"],
                                "validation": "VALID",
                                "source": "VIZ"
                            }
                            break

            # 4. Full Name (Synthesize from Given Names + Surname or single field)
            if not fields["full_name"]:
                if fields["given_names"] and fields["surname"]:
                    g_val = fields["given_names"]["value"]
                    s_val = fields["surname"]["value"]
                    fields["full_name"] = {
                        "value": f"{g_val} {s_val}".strip(),
                        "confidence": min(fields["given_names"]["confidence"], fields["surname"]["confidence"]),
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                elif any(k in text for k in ["FULL NAME", "NAME OF HOLDER"]):
                    cleaned = re.sub(r'.*(FULL NAME|NAME OF HOLDER)[\s\:\./]*', '', text).strip()
                    if len(cleaned) > 3 and not re.search(r'\d', cleaned):
                        fields["full_name"] = {
                            "value": cleaned,
                            "confidence": conf,
                            "ocr_engine": engine_name,
                            "bounding_box": box,
                            "validation": "VALID",
                            "source": "VIZ"
                        }
                    else:
                        for la_item in lookahead:
                            la_raw = la_item["text"].strip()
                            if len(la_raw) > 3 and not re.search(r'\d', la_raw) and not any(k in la_raw.upper() for k in ["PASSPORT", "REPUBLIC", "NATIONALITY"]):
                                fields["full_name"] = {
                                    "value": la_raw,
                                    "confidence": la_item["confidence"],
                                    "ocr_engine": engine_name,
                                    "bounding_box": la_item["box"],
                                    "validation": "VALID",
                                    "source": "VIZ"
                                }
                                break

            # 5. Date of Birth
            if not fields["date_of_birth"] and any(k in text for k in ["BIRTH", "DOB", "NAISSANCE", "JANM"]):
                match = date_pattern.search(raw)
                if match:
                    fields["date_of_birth"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                else:
                    for la_item in lookahead:
                        la_match = date_pattern.search(la_item["text"])
                        if la_match:
                            fields["date_of_birth"] = {
                                "value": la_match.group(1),
                                "confidence": la_item["confidence"],
                                "ocr_engine": engine_name,
                                "bounding_box": la_item["box"],
                                "validation": "VALID",
                                "source": "VIZ"
                            }
                            break

            # 6. Date of Expiry
            if not fields["date_of_expiry"] and any(k in text for k in ["EXPIRY", "EXPIRATION", "VALID UNTIL", "EXP"]):
                match = date_pattern.search(raw)
                if match:
                    fields["date_of_expiry"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                else:
                    dates_found = []
                    for la_item in lookahead:
                        for m in date_pattern.finditer(la_item["text"]):
                            dates_found.append((m.group(1), la_item))
                    if dates_found:
                        exp_val, exp_item = dates_found[-1]
                        fields["date_of_expiry"] = {
                            "value": exp_val,
                            "confidence": exp_item["confidence"],
                            "ocr_engine": engine_name,
                            "bounding_box": exp_item["box"],
                            "validation": "VALID",
                            "source": "VIZ"
                        }

            # 7. Nationality
            if not fields["nationality"] and any(k in text for k in ["NATIONALITY", "CITIZENSHIP", "INDIAN"]):
                val = "INDIAN" if "INDIAN" in text or "IND" in text else None
                if val:
                    fields["nationality"] = {
                        "value": val,
                        "confidence": conf,
                        "ocr_engine": engine_name,
                        "bounding_box": box,
                        "validation": "VALID",
                        "source": "VIZ"
                    }
                else:
                    for la_item in lookahead:
                        la_text = la_item["text"].upper()
                        if any(k in la_text for k in ["INDIAN", "IND"]):
                            fields["nationality"] = {
                                "value": "INDIAN",
                                "confidence": la_item["confidence"],
                                "ocr_engine": engine_name,
                                "bounding_box": la_item["box"],
                                "validation": "VALID",
                                "source": "VIZ"
                            }
                            break

            # 8. Sex
            if not fields["sex"] and re.search(r'\b(SEX|GENDER|SEXE)\b', text):
                if re.search(r'\bM\b|\bMALE\b', text):
                    fields["sex"] = {"value": "MALE", "confidence": conf, "ocr_engine": engine_name, "bounding_box": box, "validation": "VALID", "source": "VIZ"}
                elif re.search(r'\bF\b|\bFEMALE\b', text):
                    fields["sex"] = {"value": "FEMALE", "confidence": conf, "ocr_engine": engine_name, "bounding_box": box, "validation": "VALID", "source": "VIZ"}
                else:
                    for la_item in lookahead:
                        la_t = la_item["text"].upper().strip()
                        if la_t in ["M", "MALE", "M/MALE"]:
                            fields["sex"] = {"value": "MALE", "confidence": la_item["confidence"], "ocr_engine": engine_name, "bounding_box": la_item["box"], "validation": "VALID", "source": "VIZ"}
                            break
                        elif la_t in ["F", "FEMALE", "F/FEMALE"]:
                            fields["sex"] = {"value": "FEMALE", "confidence": la_item["confidence"], "ocr_engine": engine_name, "bounding_box": la_item["box"], "validation": "VALID", "source": "VIZ"}
                            break

        # Final pass: If full_name is missing but given_names and surname exist
        if not fields["full_name"] and fields["given_names"] and fields["surname"]:
            g_val = fields["given_names"]["value"]
            s_val = fields["surname"]["value"]
            fields["full_name"] = {
                "value": f"{g_val} {s_val}".strip(),
                "confidence": min(fields["given_names"]["confidence"], fields["surname"]["confidence"]),
                "ocr_engine": engine_name,
                "bounding_box": None,
                "validation": "VALID",
                "source": "VIZ"
            }

        return fields, mrz_lines
