"""
SatyaScan Dedicated Visa Parser and Validation Engine
Extracts Visual Inspection Zone (VIZ) fields from Visa vignettes,
enforces visa category rules, date range logic, stay duration constraints,
and cross-references linked passport numbers.
"""

from typing import Dict, Any, List, Optional
import re
from datetime import datetime
import json
import os


class VisaParser:
    """
    Dedicated Visa Vignette parser and compliance engine.
    Follows ICAO Doc 9303 Part 7 (Machine Readable Visas) and national visa standards.
    """

    DATE_PATTERNS = [
        re.compile(r'\b(\d{1,2}[\/\-\s][A-Za-z]{3,9}[\/\-\s]\d{4})\b'),
        re.compile(r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})\b'),
        re.compile(r'\b(\d{4}[\/\-]\d{2}[\/\-]\d{2})\b'),
    ]

    MONTH_MAP = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
        "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
    }

    @classmethod
    def parse_visa_fields(cls, raw_lines: List[Dict[str, Any]], ocr_engine_name: str = "PaddleOCR") -> Dict[str, Any]:
        """
        Parses visa fields from OCR token items.
        Status for each field: FOUND | NOT_FOUND | LOW_CONFIDENCE | INVALID
        """
        fields: Dict[str, Dict[str, Any]] = {
            "visa_number": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "visa_type": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "passport_number": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "holder_name": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "nationality": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "date_of_birth": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "issue_date": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "valid_from": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "valid_until": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "entries": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "stay_duration": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
        }

        # Scan lines
        for item in raw_lines:
            raw = item.get("text", "").strip()
            text = raw.upper()
            conf = item.get("confidence")
            box = item.get("box")

            # 1. Visa Number (Ensure number contains digits and does not capture keywords)
            if not fields["visa_number"]["value"]:
                vnum_match = re.search(r'\b(?:VISA\s*(?:NO|NUMBER|NUM|#)?[\s\:\.]*|VIGNETTE\s*(?:NO|#)?[\s\:\.]*)([A-Z0-9]*\d[A-Z0-9]{5,11})\b', text)
                if vnum_match:
                    val = vnum_match.group(1)
                    if val not in ["VIGNETTE", "PASSPORT", "CATEGORY", "OFFICIAL"]:
                        st = "FOUND" if conf is None or conf >= 0.60 else "LOW_CONFIDENCE"
                        fields["visa_number"] = {
                            "value": val, "status": st, "confidence": conf,
                            "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                        }

            # 2. Visa Type / Category
            if not fields["visa_type"]["value"]:
                if any(k in text for k in ["TYPE", "CATEGORY"]):
                    for cat in ["TOURIST", "BUSINESS", "TRANSIT", "DIPLOMATIC", "OFFICIAL", "STUDENT", "EMPLOYMENT", "CONFERENCE", "MEDICAL", "VISITOR"]:
                        if cat in text:
                            st = "FOUND" if conf is None or conf >= 0.60 else "LOW_CONFIDENCE"
                            fields["visa_type"] = {
                                "value": cat, "status": st, "confidence": conf,
                                "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                            }
                            break

            # 3. Passport Number Linkage
            if not fields["passport_number"]["value"]:
                if any(k in text for k in ["PASSPORT", "DOC NO", "PPT NO", "TRAVEL DOC"]):
                    p_match = re.search(r'\b([A-Z][0-9]{7,8})\b', text)
                    if p_match:
                        st = "FOUND" if conf is None or conf >= 0.60 else "LOW_CONFIDENCE"
                        fields["passport_number"] = {
                            "value": p_match.group(1), "status": st, "confidence": conf,
                            "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                        }

            # 4. Valid From / Valid Until dates
            if "FROM" in text or "VALID FROM" in text:
                d = cls._extract_date(raw)
                if d and not fields["valid_from"]["value"]:
                    st = "FOUND" if conf is None or conf >= 0.60 else "LOW_CONFIDENCE"
                    fields["valid_from"] = {
                        "value": d, "status": st, "confidence": conf,
                        "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                    }

            if any(k in text for k in ["UNTIL", "VALID UNTIL", "EXPIRY", "EXPIRATION"]):
                d = cls._extract_date(raw)
                if d and not fields["valid_until"]["value"]:
                    st = "FOUND" if conf is None or conf >= 0.60 else "LOW_CONFIDENCE"
                    fields["valid_until"] = {
                        "value": d, "status": st, "confidence": conf,
                        "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                    }

            # 5. Number of Entries
            if not fields["entries"]["value"]:
                if "MULT" in text or "MULTIPLE" in text:
                    fields["entries"] = {"value": "MULTIPLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                elif "SINGLE" in text or re.search(r'\b0?1\s*ENTRY\b', text):
                    fields["entries"] = {"value": "SINGLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                elif "DOUBLE" in text or re.search(r'\b0?2\s*ENTRIES\b', text):
                    fields["entries"] = {"value": "DOUBLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # 6. Duration of stay
            if not fields["stay_duration"]["value"]:
                stay_match = re.search(r'\b(\d{1,3})\s*(DAYS|DAY|MONTHS|MONTH)\b', text)
                if stay_match:
                    fields["stay_duration"] = {
                        "value": f"{stay_match.group(1)} {stay_match.group(2)}",
                        "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name,
                        "bounding_box": box, "validation": "VALID"
                    }

            # 7. Nationality
            if not fields["nationality"]["value"] and any(k in text for k in ["NATIONALITY", "CITIZENSHIP"]):
                for nat in ["IND", "INDIAN", "USA", "GBR", "CAN", "AUS", "FRA", "DEU", "JPN", "SGP", "ARE"]:
                    if nat in text:
                        fields["nationality"] = {
                            "value": nat, "status": "FOUND", "confidence": conf,
                            "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                        }
                        break

            # 8. Holder Name
            if not fields["holder_name"]["value"] and any(k in text for k in ["NAME", "HOLDER", "SURNAME"]):
                cleaned = re.sub(r'(NAME|HOLDER|SURNAME|OF HOLDER|FULL NAME)[\s\:\.]*', '', text).strip()
                if len(cleaned) > 3 and not re.search(r'\d', cleaned):
                    fields["holder_name"] = {
                        "value": cleaned, "status": "FOUND", "confidence": conf,
                        "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"
                    }

        return fields

    @classmethod
    def validate_visa_rules(
        cls,
        fields: Dict[str, Any],
        presented_passport_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Validates extracted visa fields against standards and returns explainable findings.
        """
        findings: List[Dict[str, Any]] = []

        # 1. VISA_NUMBER_FORMAT check
        v_num_entry = fields.get("visa_number", {})
        v_num = v_num_entry.get("value")
        if not v_num:
            findings.append({
                "rule_id": "VISA_NUMBER_FORMAT",
                "category": "SYNTAX",
                "severity": "HIGH",
                "field": "visa_number",
                "expected": "Standard Alphanumeric Identifier (6-12 chars)",
                "observed": "NOT_FOUND",
                "message": "Visa number was not detected on the vignette.",
                "classification": "PROTOTYPE_RULE"
            })
        elif len(v_num) < 6 or not re.match(r'^[A-Z0-9]+$', v_num):
            v_num_entry["validation"] = "INVALID"
            v_num_entry["status"] = "INVALID"
            findings.append({
                "rule_id": "VISA_NUMBER_FORMAT",
                "category": "SYNTAX",
                "severity": "HIGH",
                "field": "visa_number",
                "expected": "Standard Alphanumeric Identifier (6-12 chars)",
                "observed": v_num,
                "message": f"Visa identifier '{v_num}' violates standard format specification.",
                "classification": "PROTOTYPE_RULE"
            })

        # 2. VISA_EXPIRY_CHECK
        valid_until_entry = fields.get("valid_until", {})
        valid_from_entry = fields.get("valid_from", {})
        until_str = valid_until_entry.get("value")
        from_str = valid_from_entry.get("value")

        dt_until = cls._parse_date_to_datetime(until_str) if until_str else None
        dt_from = cls._parse_date_to_datetime(from_str) if from_str else None

        if dt_until:
            now = datetime.now()
            if dt_until < now:
                valid_until_entry["validation"] = "INVALID"
                valid_until_entry["status"] = "INVALID"
                findings.append({
                    "rule_id": "VISA_EXPIRY_CHECK",
                    "category": "VALIDITY",
                    "severity": "CRITICAL",
                    "field": "valid_until",
                    "expected": "Future Date",
                    "observed": dt_until.strftime("%Y-%m-%d"),
                    "message": f"Visa expired on {dt_until.strftime('%Y-%m-%d')}. Document is invalid for entry.",
                    "classification": "OFFICIAL_STANDARD"
                })

        if dt_from and dt_until:
            if dt_from > dt_until:
                valid_from_entry["validation"] = "INVALID"
                valid_until_entry["validation"] = "INVALID"
                findings.append({
                    "rule_id": "VISA_DATE_RANGE_INVALID",
                    "category": "VALIDITY",
                    "severity": "CRITICAL",
                    "field": "valid_from",
                    "expected": "Valid From <= Valid Until",
                    "observed": f"From: {dt_from.strftime('%Y-%m-%d')} > Until: {dt_until.strftime('%Y-%m-%d')}",
                    "message": "Visa validity start date occurs after expiry date.",
                    "classification": "OFFICIAL_STANDARD"
                })

        # 3. VISA_STAY_DURATION check
        stay_entry = fields.get("stay_duration", {})
        stay_val = stay_entry.get("value")
        visa_type_val = fields.get("visa_type", {}).get("value") or "TOURIST"

        if stay_val:
            match_days = re.search(r'(\d+)\s*DAY', stay_val)
            if match_days:
                days = int(match_days.group(1))
                if visa_type_val in ["TOURIST", "TRANSIT"] and days > 180:
                    stay_entry["validation"] = "SUSPICIOUS"
                    findings.append({
                        "rule_id": "VISA_STAY_DURATION",
                        "category": "VALIDITY",
                        "severity": "MEDIUM",
                        "field": "stay_duration",
                        "expected": "<= 180 Days for declared category",
                        "observed": f"{days} Days ({visa_type_val})",
                        "message": f"Authorized stay duration of {days} days exceeds typical limit for {visa_type_val} visa.",
                        "classification": "PROTOTYPE_RULE"
                    })

        # 4. VISA_PASSPORT_CROSS_CHECK
        visa_ppt = fields.get("passport_number", {}).get("value")
        if visa_ppt and presented_passport_number:
            clean_v = visa_ppt.replace(" ", "").upper()
            clean_p = presented_passport_number.replace(" ", "").upper()
            if clean_v != clean_p:
                findings.append({
                    "rule_id": "VISA_PASSPORT_CROSS_CHECK",
                    "category": "CROSS_CHECK",
                    "severity": "CRITICAL",
                    "field": "passport_number",
                    "expected": clean_p,
                    "observed": clean_v,
                    "message": f"Visa passport reference ({clean_v}) does not match physical passport presented ({clean_p}).",
                    "classification": "OFFICIAL_STANDARD"
                })

        return findings

    @classmethod
    def _extract_date(cls, text: str) -> Optional[str]:
        for pat in cls.DATE_PATTERNS:
            m = pat.search(text)
            if m:
                return m.group(1)
        return None

    @classmethod
    def _parse_date_to_datetime(cls, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        clean = date_str.strip()
        # Try ISO
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]:
            try:
                return datetime.strptime(clean, fmt)
            except Exception:
                pass
        # Try DD Mon YYYY
        parts = re.split(r'[\s\/\-\.]+', clean)
        if len(parts) == 3:
            d, m_str, y = parts[0], parts[1].upper()[:3], parts[2]
            if m_str in cls.MONTH_MAP and len(y) == 4 and d.isdigit():
                try:
                    return datetime(int(y), int(cls.MONTH_MAP[m_str]), int(d))
                except Exception:
                    pass
        return None
