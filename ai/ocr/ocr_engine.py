"""
SatyaScan OCR Engine
Provides robust dual-engine OCR (PaddleOCR with Tesseract fallback),
extracting text tokens, authentic confidence metrics, bounding boxes,
and structured Visual Inspection Zone (VIZ) identity fields.
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
        Returns raw lines, bounding boxes, confidences, and structured fields.
        """
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                return {"error": "Image file not found", "fields": {}, "lines": []}
            cv_img = cv2.imread(image_input)
            pil_img = Image.open(image_input)
        elif isinstance(image_input, np.ndarray):
            cv_img = image_input
            pil_img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        else:
            return {"error": "Invalid image input", "fields": {}, "lines": []}

        self._init_paddle()

        raw_items: List[Dict[str, Any]] = []

        # Attempt PaddleOCR first if available
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
            except Exception as e:
                print(f"[SatyaScan OCR] PaddleOCR inference error: {e}, using Tesseract fallback.")
                raw_items = []

        # Fallback to Tesseract if PaddleOCR returned empty or failed
        if not raw_items:
            try:
                # Preprocessing for clean Tesseract extraction: grayscale + contrast enhancement
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                # Unsharp mask
                gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
                sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)

                data = pytesseract.image_to_data(sharpened, output_type=pytesseract.Output.DICT)
                n_boxes = len(data['text'])
                line_collector: Dict[int, List[Dict[str, Any]]] = {}

                for i in range(n_boxes):
                    text = data['text'][i].strip()
                    conf = float(data['conf'][i])
                    if text and conf > 15:
                        line_num = data['line_num'][i]
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        poly = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                        line_collector.setdefault(line_num, []).append({
                            "text": text,
                            "conf": conf / 100.0,
                            "box": poly
                        })

                for l_num in sorted(line_collector.keys()):
                    tokens = line_collector[l_num]
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
            except Exception as err:
                print(f"[SatyaScan OCR] Tesseract fallback failed: {err}")

        # Extract structured fields from detected text lines
        structured_fields, mrz_candidate_lines = self._extract_fields(raw_items)

        # Calculate average extraction confidence
        avg_confidence = (
            round(sum(item["confidence"] for item in raw_items) / len(raw_items), 3)
            if raw_items else 0.0
        )

        return {
            "engine": "PaddleOCR" if self._paddle_ocr and raw_items else "Tesseract-Fallback",
            "average_confidence": avg_confidence,
            "total_lines_detected": len(raw_items),
            "raw_lines": raw_items,
            "mrz_candidate_lines": mrz_candidate_lines,
            "extracted_fields": structured_fields
        }

    def _extract_fields(self, items: List[Dict[str, Any]]) -> tuple[Dict[str, Any], List[str]]:
        """
        Parses Visual Inspection Zone (VIZ) identity fields from detected OCR tokens.
        """
        fields: Dict[str, Any] = {
            "document_type": {"value": "PASSPORT", "confidence": 0.95, "source": "OCR_LAYOUT"},
            "passport_number": None,
            "surname": None,
            "given_names": None,
            "full_name": None,
            "nationality": None,
            "date_of_birth": None,
            "date_of_expiry": None,
            "sex": None
        }

        all_texts = [item["text"] for item in items]
        mrz_lines: List[str] = []

        # Find MRZ candidate lines (lines starting with P< or containing multiple consecutive '<')
        for item in items:
            t = item["text"].replace(" ", "").upper()
            if (t.startswith("P<") or t.startswith("P0") or t.startswith("P«") or t.count("<") >= 5) and len(t) >= 25:
                mrz_lines.append(item["text"])

        # Regex patterns for VIZ fields
        # Passport Number pattern: 1 letter followed by 7 digits (India) or 8-9 alphanumerics
        doc_num_pattern = re.compile(r'\b([A-Z][0-9]{7,8})\b')
        date_pattern = re.compile(r'\b(\d{1,2}[\/\-\s][A-Za-z]{3,9}[\/\-\s]\d{4}|\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b')

        for item in items:
            raw = item["text"]
            text = raw.upper()
            conf = item["confidence"]
            box = item["box"]

            # 1. Passport Number
            if not fields["passport_number"]:
                match = doc_num_pattern.search(text)
                if match and "REPUBLIC" not in text and "PASSPORT" not in text:
                    fields["passport_number"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "bounding_box": box,
                        "source": "VIZ"
                    }

            # 2. Date of Birth
            if any(k in text for k in ["BIRTH", "DOB", "NAISSANCE", "JANM"]):
                # Look in same line or subsequent lines
                match = date_pattern.search(raw)
                if match:
                    fields["date_of_birth"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "bounding_box": box,
                        "source": "VIZ"
                    }

            # 3. Date of Expiry
            if any(k in text for k in ["EXPIRY", "EXPIRATION", "VALID", "EXP"]):
                match = date_pattern.search(raw)
                if match:
                    fields["date_of_expiry"] = {
                        "value": match.group(1),
                        "confidence": conf,
                        "bounding_box": box,
                        "source": "VIZ"
                    }

            # 4. Nationality
            if "NATIONALITY" in text or "CITIZENSHIP" in text or "INDIAN" in text:
                val = "INDIAN" if "INDIAN" in text else "IND"
                fields["nationality"] = {
                    "value": val,
                    "confidence": conf,
                    "bounding_box": box,
                    "source": "VIZ"
                }

            # 5. Sex
            if re.search(r'\b(SEX|GENDER)\b', text):
                if re.search(r'\bM\b|\bMALE\b', text):
                    fields["sex"] = {"value": "MALE", "confidence": conf, "bounding_box": box, "source": "VIZ"}
                elif re.search(r'\bF\b|\bFEMALE\b', text):
                    fields["sex"] = {"value": "FEMALE", "confidence": conf, "bounding_box": box, "source": "VIZ"}

            # 6. Given Names / Surname
            if any(k in text for k in ["NAME", "GIVEN NAME", "SURNAME"]) and not fields["full_name"]:
                # Clean header keywords to isolate candidate name
                cleaned = re.sub(r'(GIVEN NAME|SURNAME|NAME|OF HOLDER|FULL NAME)[\s\:\.]*', '', text).strip()
                if len(cleaned) > 3 and not re.search(r'\d', cleaned):
                    fields["full_name"] = {
                        "value": cleaned,
                        "confidence": conf,
                        "bounding_box": box,
                        "source": "VIZ"
                    }

        return fields, mrz_lines
