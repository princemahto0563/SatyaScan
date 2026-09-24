"""
SatyaScan Document Type Classifier Gate
Enforces strict document type boundaries BEFORE OCR / MRZ / Forensics.
Supported types in prototype: PASSPORT and VISA only.
Explicitly rejects: Aadhaar, PAN, Driving Licence, Voter ID, College/Student ID,
Employee ID, National ID cards, Blank images, and Unrelated images.
"""

from typing import Dict, Any, List, Optional
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except Exception:
    PADDLE_AVAILABLE = False


_SHARED_OCR_ENGINE = None

def get_shared_ocr_engine():
    global _SHARED_OCR_ENGINE
    if _SHARED_OCR_ENGINE is None:
        from ai.ocr.ocr_engine import OCREngine
        _SHARED_OCR_ENGINE = OCREngine()
    return _SHARED_OCR_ENGINE


class DocumentClassifier:
    """
    Deterministic document classifier gate that inspects image characteristics,
    visual layout, text tokens, and structural markers.
    """

    REJECTION_MESSAGE = (
        "Unsupported document type. SatyaScan currently supports Passport and Visa only. "
        "Please upload a valid Passport or Visa."
    )

    UNABLE_TO_CLASSIFY_MESSAGE = (
        "The submitted document could not be reliably identified as a Passport or Visa. "
        "Please provide a clearer, well-lit image of a valid Passport or Visa."
    )

    def __init__(self, ocr_engine: Optional[Any] = None):
        self._ocr_engine = ocr_engine if ocr_engine is not None else get_shared_ocr_engine()
        self._paddle_ocr = None
        self._initialized = True

    def _init_ocr(self):
        if self._initialized:
            return
        if self._ocr_engine is not None:
            self._initialized = True
            return
        if PADDLE_AVAILABLE:
            try:
                self._paddle_ocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    lang='en'
                )
            except Exception:
                try:
                    self._paddle_ocr = PaddleOCR(use_angle_cls=False, lang='en')
                except Exception:
                    self._paddle_ocr = None
        self._initialized = True

    def classify_image(self, image_input: Any, ocr_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Classifies input image into:
        - PASSPORT (Supported)
        - VISA (Supported)
        - AADHAAR (Explicitly Rejected)
        - PAN (Explicitly Rejected)
        - DRIVING_LICENCE (Explicitly Rejected)
        - VOTER_ID (Explicitly Rejected)
        - STUDENT_ID (Explicitly Rejected)
        - EMPLOYEE_ID (Explicitly Rejected)
        - BLANK_IMAGE (Explicitly Rejected)
        - UNSUPPORTED_DOCUMENT (Explicitly Rejected)
        - UNABLE_TO_CLASSIFY (Rejected — Inconclusive)
        
        Supports pre-computed ocr_result to eliminate duplicate PaddleOCR inferences (Phase 2A).
        """
        # 1. Decode image to numpy BGR array
        if isinstance(image_input, str):
            cv_img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            cv_img = image_input
        else:
            return {
                "verdict": "UNSUPPORTED_DOCUMENT",
                "detected_type": "INVALID_INPUT",
                "is_supported": False,
                "confidence": 0.0,
                "indicators": ["Invalid image input type"],
                "message": self.REJECTION_MESSAGE,
                "raw_text": "",
                "ocr_result": None
            }

        if cv_img is None or cv_img.size == 0:
            return {
                "verdict": "UNSUPPORTED_DOCUMENT",
                "detected_type": "CORRUPT_IMAGE",
                "is_supported": False,
                "confidence": 0.0,
                "indicators": ["Unable to decode image bytes"],
                "message": self.REJECTION_MESSAGE,
                "raw_text": "",
                "ocr_result": None
            }

        # 2. Check for Blank / Monochrome Image
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        std_dev = float(np.std(gray))
        mean_val = float(np.mean(gray))

        if std_dev < 8.0 or (mean_val > 248.0 and std_dev < 12.0) or (mean_val < 8.0 and std_dev < 12.0):
            return {
                "verdict": "UNSUPPORTED_DOCUMENT",
                "detected_type": "BLANK_IMAGE",
                "is_supported": False,
                "confidence": 0.99,
                "indicators": [f"Image has negligible visual variance (std_dev={std_dev:.2f})"],
                "message": self.REJECTION_MESSAGE,
                "raw_text": "",
                "ocr_result": None
            }

        # 3. Extract Text Tokens for Classification (reusing shared OCR result when available)
        shared_ocr_result: Optional[Dict[str, Any]] = None
        if ocr_result is not None:
            shared_ocr_result = ocr_result
            ocr_lines = ocr_result.get("lines", [r["text"] for r in ocr_result.get("raw_lines", [])])
            raw_text = ocr_result.get("raw_text", " ".join(ocr_lines))
        elif self._ocr_engine is not None:
            shared_ocr_result = self._ocr_engine.process_image(cv_img)
            ocr_lines = shared_ocr_result.get("lines", [r["text"] for r in shared_ocr_result.get("raw_lines", [])])
            raw_text = shared_ocr_result.get("raw_text", " ".join(ocr_lines))
        else:
            raw_text, ocr_lines = self._extract_text(cv_img)

        upper_text = raw_text.upper()

        def _wrap_res(d: Dict[str, Any]) -> Dict[str, Any]:
            d["ocr_result"] = shared_ocr_result
            return d

        # 4. Check for Explicitly Rejected Indian / Domestic Documents FIRST
        rejection_match = self._check_unsupported_patterns(upper_text, raw_text)
        if rejection_match:
            return _wrap_res({
                "verdict": "UNSUPPORTED_DOCUMENT",
                "detected_type": rejection_match["detected_type"],
                "is_supported": False,
                "confidence": rejection_match["confidence"],
                "indicators": rejection_match["indicators"],
                "message": self.REJECTION_MESSAGE,
                "raw_text": raw_text[:500]
            })

        # 5. Check for VISA & PASSPORT Indicators
        visa_match = self._check_visa_patterns(upper_text, ocr_lines)
        passport_match = self._check_passport_patterns(upper_text, ocr_lines, cv_img)

        # Check for genuine TD3 Passport MRZ (2 lines with heavy filler '<')
        has_genuine_passport_mrz = (
            passport_match.get("mrz_count", 0) >= 2
            and any(line.replace(" ", "").upper().startswith(("P<IND", "P<USA", "P<GBR", "P<CAN", "P<AUS", "P<")) for line in ocr_lines)
        )

        # Disambiguation:
        # Visas routinely reference the bearer's "Passport No", which can falsely trigger passport keywords.
        # But genuine Passports do not have Visa headers, Visa Categories, Stay Durations, or Entry conditions.
        if visa_match["detected"] and passport_match["detected"]:
            if has_genuine_passport_mrz and len(visa_match["indicators"]) < 3:
                return _wrap_res({
                    "verdict": "PASSPORT",
                    "detected_type": "PASSPORT",
                    "is_supported": True,
                    "confidence": passport_match["confidence"],
                    "indicators": passport_match["indicators"],
                    "message": "Valid passport layout detected.",
                    "raw_text": raw_text[:500]
                })
            else:
                return _wrap_res({
                    "verdict": "VISA",
                    "detected_type": "VISA",
                    "is_supported": True,
                    "confidence": visa_match["confidence"],
                    "indicators": visa_match["indicators"],
                    "message": "Valid visa vignette detected.",
                    "raw_text": raw_text[:500]
                })

        if passport_match["detected"]:
            return _wrap_res({
                "verdict": "PASSPORT",
                "detected_type": "PASSPORT",
                "is_supported": True,
                "confidence": passport_match["confidence"],
                "indicators": passport_match["indicators"],
                "message": "Valid passport layout detected.",
                "raw_text": raw_text[:500]
            })

        if visa_match["detected"]:
            return _wrap_res({
                "verdict": "VISA",
                "detected_type": "VISA",
                "is_supported": True,
                "confidence": visa_match["confidence"],
                "indicators": visa_match["indicators"],
                "message": "Valid visa vignette detected.",
                "raw_text": raw_text[:500]
            })

        # 7. If neither Passport nor Visa could be reliably established
        # If too little text was found or completely unrelated
        if len(ocr_lines) < 2 or len(upper_text.strip()) < 20:
            return _wrap_res({
                "verdict": "UNABLE_TO_CLASSIFY",
                "detected_type": "RANDOM_OR_UNREADABLE",
                "is_supported": False,
                "confidence": 0.2,
                "indicators": ["Insufficient readable textual or structural markers"],
                "message": self.UNABLE_TO_CLASSIFY_MESSAGE,
                "raw_text": raw_text[:500]
            })

        return _wrap_res({
            "verdict": "UNSUPPORTED_DOCUMENT",
            "detected_type": "OTHER_DOCUMENT",
            "is_supported": False,
            "confidence": 0.85,
            "indicators": ["Unrecognized document schema (not a Passport or Visa)"],
            "message": self.REJECTION_MESSAGE,
            "raw_text": raw_text[:500]
        })

    def _extract_text(self, cv_img: np.ndarray) -> tuple[str, List[str]]:
        """Fast text extraction using shared OCREngine with fallback."""
        if self._ocr_engine is not None:
            res = self._ocr_engine.process_image(cv_img)
            lines = res.get("lines", [r["text"] for r in res.get("raw_lines", [])])
            raw_text = res.get("raw_text", " ".join(lines))
            return raw_text, lines

        self._init_ocr()
        lines: List[str] = []

        if self._paddle_ocr:
            try:
                results = self._paddle_ocr.ocr(cv_img)
                if results and len(results) > 0 and results[0] is not None:
                    res0 = results[0]
                    if hasattr(res0, 'keys') and 'rec_texts' in res0:
                        lines = [str(t).strip() for t in res0.get('rec_texts', [])]
                    elif isinstance(res0, list):
                        for item in res0:
                            if isinstance(item, (list, tuple)) and len(item) >= 2:
                                t_entry = item[1]
                                if isinstance(t_entry, (list, tuple)) and len(t_entry) >= 1:
                                    lines.append(str(t_entry[0]).strip())
            except Exception:
                lines = []

        if not lines:
            try:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                t_str = pytesseract.image_to_string(gray)
                lines = [l.strip() for l in t_str.split("\n") if l.strip()]
            except Exception:
                lines = []

        raw_text = " ".join(lines)
        return raw_text, lines

    def _check_unsupported_patterns(self, upper_text: str, raw_text: str) -> Optional[Dict[str, Any]]:
        """Identifies rejected document types from text patterns."""
        # 1. Aadhaar Card
        aadhaar_indicators = []
        if re.search(r'\b(AADHAAR|AADHAR|UIDAI)\b', upper_text):
            aadhaar_indicators.append("Keyword 'AADHAAR' or 'UIDAI' found")
        if "MERA AADHAAR" in upper_text or "UNIQUE IDENTIFICATION" in upper_text:
            aadhaar_indicators.append("UIDAI slogan or authority string found")
        if re.search(r'\b\d{4}\s\d{4}\s\d{4}\b', raw_text):
            aadhaar_indicators.append("12-digit spaced Aadhaar number pattern found")
        if "ENROLMENT NO" in upper_text or "ENROLLMENT NO" in upper_text:
            aadhaar_indicators.append("Aadhaar enrollment indicator found")
        if aadhaar_indicators:
            return {
                "detected_type": "AADHAAR",
                "confidence": 0.98,
                "indicators": aadhaar_indicators
            }

        # 2. Permanent Account Number (PAN) Card
        pan_indicators = []
        if "INCOME TAX DEPARTMENT" in upper_text or "GOVT. OF INDIA" in upper_text and "PAN" in upper_text:
            pan_indicators.append("Income Tax Department header found")
        if "PERMANENT ACCOUNT NUMBER" in upper_text:
            pan_indicators.append("Permanent Account Number heading found")
        pan_regex = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', upper_text)
        if pan_regex and ("INCOME" in upper_text or "TAX" in upper_text or "FATHER" in upper_text or "PAN" in upper_text):
            pan_indicators.append(f"10-character PAN syntax found ({pan_regex.group(0)})")
        if pan_indicators:
            return {
                "detected_type": "PAN",
                "confidence": 0.98,
                "indicators": pan_indicators
            }

        # 3. Driving Licence
        dl_indicators = []
        if re.search(r'\b(DRIVING LICENCE|DRIVING LICENSE)\b', upper_text):
            dl_indicators.append("Driving Licence header found")
        if "MOTOR VEHICLES" in upper_text or "TRANSPORT DEPARTMENT" in upper_text or "FORM 7" in upper_text:
            dl_indicators.append("Transport Department or Form 7 reference found")
        if re.search(r'\bDL\s*(NO|NUM|\:)', upper_text) or re.search(r'\b[A-Z]{2}[0-9]{2}[0-9]{11}\b', upper_text):
            dl_indicators.append("Driving Licence number pattern found")
        if dl_indicators:
            return {
                "detected_type": "DRIVING_LICENCE",
                "confidence": 0.95,
                "indicators": dl_indicators
            }

        # 4. Voter ID / EPIC
        voter_indicators = []
        if "ELECTION COMMISSION" in upper_text or "ELECTOR PHOTO" in upper_text or "VOTER ID" in upper_text:
            voter_indicators.append("Election Commission of India / Elector Photo header found")
        if re.search(r'\b[A-Z]{3}[0-9]{7}\b', upper_text) and ("ELECT" in upper_text or "VOTER" in upper_text):
            voter_indicators.append("EPIC identifier syntax found")
        if voter_indicators:
            return {
                "detected_type": "VOTER_ID",
                "confidence": 0.96,
                "indicators": voter_indicators
            }

        # 5. Student / College / Employee ID
        id_indicators = []
        if re.search(r'\b(STUDENT ID|STUDENT IDENTITY|COLLEGE OF|UNIVERSITY|CAMPUS)\b', upper_text):
            id_indicators.append("Academic institution identifier found")
        if re.search(r'\b(EMPLOYEE ID|STAFF CARD|EMPLOYEE IDENTITY|STAFF ID)\b', upper_text):
            id_indicators.append("Corporate employee badge identifier found")
        if "ROLL NO" in upper_text or "ENROLLMENT NO" in upper_text and "SEMESTER" in upper_text:
            id_indicators.append("Student enrollment / semester marker found")
        if id_indicators:
            return {
                "detected_type": "STUDENT_OR_EMPLOYEE_ID",
                "confidence": 0.92,
                "indicators": id_indicators
            }

        # 6. National Identity Card / Residence Permit of other nations
        nid_indicators = []
        if "NATIONAL IDENTITY CARD" in upper_text or "CITIZEN CARD" in upper_text or "RESIDENCE PERMIT" in upper_text:
            nid_indicators.append("Generic national identity card / residence permit marker found")
        if nid_indicators:
            return {
                "detected_type": "NATIONAL_ID",
                "confidence": 0.90,
                "indicators": nid_indicators
            }

        return None

    def _check_passport_patterns(self, upper_text: str, lines: List[str], cv_img: np.ndarray) -> Dict[str, Any]:
        """Identifies TD3 Passport based on MRZ structure, headers, and standard layout."""
        indicators = []
        mrz_count = 0

        # Check for TD3 MRZ lines (starts with P< or has >= 4 '<' chars)
        for line in lines:
            t = line.replace(" ", "").upper()
            if (t.startswith("P<") or t.startswith("P0") or t.startswith("P«") or t.count("<") >= 4) and len(t) >= 25:
                mrz_count += 1

        if mrz_count >= 1:
            indicators.append(f"Detected {mrz_count} ICAO Doc 9303 MRZ candidate line(s)")

        if re.search(r'\b(PASSPORT|PASSEPORT|PASAPORTE)\b', upper_text):
            indicators.append("Passport document header keyword found")

        if "REPUBLIC OF INDIA" in upper_text or "UNION OF INDIA" in upper_text or "INDIAN PASSPORT" in upper_text:
            indicators.append("Issuing State passport authority string found")

        # Passport number pattern (e.g. Z1234567, P1234567, A12345678)
        doc_num_match = re.search(r'\b([A-Z][0-9]{7,8})\b', upper_text)
        if doc_num_match and ("PASSPORT" in upper_text or mrz_count >= 1):
            indicators.append(f"Standard passport identifier sequence found ({doc_num_match.group(1)})")

        if "TYPE P" in upper_text or re.search(r'\bTYPE\s*[\:\/]?\s*P\b', upper_text):
            indicators.append("ICAO Type 'P' travel document designation found")

        # Evidence evaluation:
        # A document qualifies as passport if:
        # 1. At least 1 MRZ line found AND (Passport keyword OR Doc num OR Type P)
        # 2. OR Passport keyword + Issuing state + Doc num
        is_passport = (
            (mrz_count >= 1 and len(indicators) >= 2) or
            (mrz_count >= 2) or
            ("PASSPORT" in upper_text and ("REPUBLIC" in upper_text or doc_num_match is not None))
        )

        confidence = 0.98 if mrz_count >= 2 else 0.90 if is_passport else 0.0
        return {
            "detected": is_passport,
            "confidence": confidence,
            "mrz_count": mrz_count,
            "indicators": indicators
        }

    def _check_visa_patterns(self, upper_text: str, lines: List[str]) -> Dict[str, Any]:
        """Identifies Visa vignette based on visa headers, category, validity, and entry info."""
        indicators = []

        if re.search(r'\b(VISA|VIZUM|VISA VIGNETTE)\b', upper_text):
            indicators.append("Visa document header keyword found")
        elif "VISA" in upper_text and any(k in upper_text for k in ["ENTRIES", "VALID FOR", "DURATION OF STAY"]):
            indicators.append("Visa header with entry conditions found")

        if re.search(r'\b(VISA TYPE|TYPE OF VISA|VISA CATEGORY|CATEGORY)\b', upper_text):
            indicators.append("Visa category indicator found")

        if re.search(r'\b(ENTRIES|NO OF ENTRIES|NUMBER OF ENTRIES|ENTRY)\b', upper_text):
            indicators.append("Visa entry allowance indicator found")

        if re.search(r'\b(DURATION OF STAY|PERIOD OF STAY|STAY FOR)\b', upper_text):
            indicators.append("Stay duration indicator found")

        if re.search(r'\b(VALID FROM|VALID UNTIL|DATE OF EXPIRY|EXPIRY DATE)\b', upper_text):
            indicators.append("Visa validity date range indicator found")

        visa_num = re.search(r'\b(VISA NO|VISA NUMBER|VIGNETTE NO)[\s\:\.]*([A-Z0-9]{6,12})\b', upper_text)
        if visa_num:
            indicators.append(f"Visa identifier found ({visa_num.group(2)})")

        is_visa = len(indicators) >= 2 and any("VISA" in ind.upper() for ind in indicators)
        confidence = 0.95 if len(indicators) >= 3 else 0.85 if is_visa else 0.0

        return {
            "detected": is_visa,
            "confidence": confidence,
            "indicators": indicators
        }


# Global singleton instance
document_classifier = DocumentClassifier()
