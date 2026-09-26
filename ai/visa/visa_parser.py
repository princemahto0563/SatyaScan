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

    LABEL_STOPWORDS = {
        'SURNAME', 'NOM', 'NOW', 'GIVEN', 'NAMES', 'NAWES', 'PRENOM', 'PRENOMS', 'PRENOW', 'PRENOUS', 'PRENOWS',
        'NAME', 'FULL', 'HOLDER', 'PASSPORT', 'PASSEPORT', 'VISA', 'VIZUM', 'VIGNETTE',
        'REPUBLIC', 'OF', 'COUNTRY', 'TYPE', 'CATEGORY', 'NATIONALITY', 'NATIONALITE',
        'SEX', 'SEXE', 'GENDER', 'DATE', 'BIRTH', 'NAISSANCE', 'EXPIRY', 'VALID', 'UNTIL',
        'FROM', 'ENTRIES', 'DURATION', 'STAY', 'PLACE', 'ISSUE', 'MAT', 'MATRICULE', 'SIGNATURE',
        'TITULAIRE', 'OFFICER', 'REMARKS', 'REMARQUES', 'CONFERENCE', 'ATTENDANCE', 'PERMITTED',
        'GIVENNAMES', 'FULLNAME', 'MATNOM', 'SURNAMENOM', 'PASSPORTNO', 'DOCUMENTNO',
        'EXPIRATION', 'VALIDITY', 'DELIVRANCE', 'DELIVERY', 'AUTORITE', 'AUTHORITY',
        'BEARER', 'PAYS', 'CODE', 'ISSUING', 'POST', 'DELHI', 'INDIA', 'ISLANDS'
    }

    @classmethod
    def is_label_noise(cls, val_str: str) -> bool:
        """Determines if a field candidate consists solely of OCR label stopwords."""
        if not val_str or len(val_str.strip()) < 2:
            return True
        s = val_str.strip()
        # If it has 3+ digits (e.g. document number, date), it's not a pure label noise string
        if re.search(r'\d{3,}', s):
            return False
        tokens = re.findall(r'[A-Za-z]+', s.upper())
        if not tokens:
            return True
        return all(t in cls.LABEL_STOPWORDS for t in tokens)

    @classmethod
    def _clean_name_tokens(cls, raw_text: str) -> str:
        """Strips OCR noise, label prefixes, and label stopwords from name candidates."""
        if not raw_text:
            return ""
        # Strip leading label prefixes like "SURNAME/NOM:", "MAT /NOM:", "GIVEN NAMES:"
        stripped = re.sub(
            r'^(?:SURNAME|NOM|GIVEN|NAMES|PRENOM|PRENOMS|MAT|MATRICULE|NAME|FULL)[\s\:\./\-]+',
            '',
            raw_text.strip(),
            flags=re.IGNORECASE
        )
        clean = re.sub(r'[^A-Za-z\s]', ' ', stripped)
        tokens = clean.split()
        valid = []
        for t in tokens:
            up = t.upper()
            if len(up) < 2 or up in cls.LABEL_STOPWORDS:
                continue
            # Require at least one vowel for 2-letter words (rejects dk, qz, etc.)
            if len(up) == 2 and not any(v in up for v in ("A", "E", "I", "O", "U", "Y")):
                continue
            valid.append(up)
        result = ' '.join(valid).strip()
        if cls.is_label_noise(result):
            return ""
        return result

    @classmethod
    def parse_visa_fields(cls, raw_lines: List[Dict[str, Any]], ocr_engine_name: str = "Tesseract") -> Dict[str, Any]:
        """
        Parses visa fields from OCR token items with robust multi-line pairing,
        label-noise suppression, demographic block parsing, and truthful MRZ detection.
        """
        fields: Dict[str, Dict[str, Any]] = {
            "visa_number": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "visa_type": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "passport_number": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "surname": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "given_names": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "holder_name": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "nationality": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "date_of_birth": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "sex": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "issue_date": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "valid_from": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "valid_until": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "entries": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
            "stay_duration": {"value": None, "status": "NOT_FOUND", "confidence": None, "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "PENDING"},
        }

        # Check for ICAO Doc 9303 Part 7 MRV lines (MRVA: 44 chars or MRVB: 36 chars)
        for item in raw_lines:
            t_clean = item.get("text", "").replace(" ", "").upper()
            if t_clean.startswith("V<") and len(t_clean) >= 20:
                # Extract holder name from MRVA / MRVB Line 1 (V<CCC<SURNAME<<GIVEN<NAMES...)
                parts = t_clean[5:].split("<<")
                if len(parts) >= 2 and not fields["surname"]["value"]:
                    s_cand = parts[0].replace("<", " ").strip()
                    g_cand = parts[1].replace("<", " ").strip()
                    if s_cand and not cls.is_label_noise(s_cand):
                        fields["surname"] = {"value": s_cand, "status": "FOUND", "confidence": 0.95, "ocr_engine": ocr_engine_name, "bounding_box": item.get("box"), "validation": "VALID"}
                    if g_cand and not cls.is_label_noise(g_cand):
                        fields["given_names"] = {"value": g_cand, "status": "FOUND", "confidence": 0.95, "ocr_engine": ocr_engine_name, "bounding_box": item.get("box"), "validation": "VALID"}
            # Check MRV Line 2: starts with 9-char document number followed by check digit, 3-char nationality, 6-char DOB
            mrv_l2 = re.match(r'^([A-Z0-9]{7,10})\d([A-Z]{3})(\d{6})\d([MF<])(\d{6})', t_clean)
            if mrv_l2:
                v_num_mrv, nat_mrv, dob_mrv, sex_mrv, exp_mrv = mrv_l2.groups()
                if not fields["visa_number"]["value"]:
                    clean_vnum = v_num_mrv.replace("<", "").strip()
                    if clean_vnum and len(clean_vnum) >= 6:
                        fields["visa_number"] = {"value": clean_vnum, "status": "FOUND", "confidence": 0.96, "ocr_engine": ocr_engine_name, "bounding_box": item.get("box"), "validation": "VALID"}
                if not fields["nationality"]["value"] and nat_mrv:
                    fields["nationality"] = {"value": "INDIAN" if nat_mrv == "IND" else nat_mrv, "status": "FOUND", "confidence": 0.95, "ocr_engine": ocr_engine_name, "bounding_box": item.get("box"), "validation": "VALID"}
                if not fields["sex"]["value"] and sex_mrv in ("M", "F"):
                    fields["sex"] = {"value": "MALE" if sex_mrv == "M" else "FEMALE", "status": "FOUND", "confidence": 0.95, "ocr_engine": ocr_engine_name, "bounding_box": item.get("box"), "validation": "VALID"}

        for i, item in enumerate(raw_lines):
            raw = item.get("text", "").strip()
            text = raw.upper()
            conf = item.get("confidence") or 0.90
            box = item.get("box")

            lookahead = raw_lines[i + 1 : min(len(raw_lines), i + 4)]

            # Check Surname
            if not fields["surname"]["value"] and any(k in text for k in ["SURNAME", "NOM"]):
                cleaned = re.sub(r'.*(?:SURNAME|NOM)[\s\:\./\-]*', '', text).strip()
                cand = cls._clean_name_tokens(cleaned)
                if cand and not cls.is_label_noise(cand):
                    fields["surname"] = {"value": cand, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                else:
                    for la in lookahead:
                        la_cand = cls._clean_name_tokens(la.get("text", ""))
                        if la_cand and len(la_cand) >= 2 and not cls.is_label_noise(la_cand) and not any(k in la.get("text", "").upper() for k in ["GIVEN", "PRENOM", "SEX", "PASSPORT", "VISA"]):
                            fields["surname"] = {"value": la_cand, "status": "FOUND", "confidence": la.get("confidence") or conf, "ocr_engine": ocr_engine_name, "bounding_box": la.get("box"), "validation": "VALID"}
                            break

            # Check Given Names
            if not fields["given_names"]["value"] and any(k in text for k in ["GIVEN", "PRENOM"]):
                cleaned = re.sub(r'.*(?:GIVEN[\sA-Z]*|PRENOM[S]?)[\s\:\./\-]*', '', text).strip()
                cand = cls._clean_name_tokens(cleaned)
                if cand and not cls.is_label_noise(cand):
                    fields["given_names"] = {"value": cand, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                else:
                    for la in lookahead:
                        la_cand = cls._clean_name_tokens(la.get("text", ""))
                        if la_cand and len(la_cand) >= 2 and not cls.is_label_noise(la_cand) and not any(k in la.get("text", "").upper() for k in ["SURNAME", "NOM", "SEX", "PASSPORT", "VISA"]):
                            fields["given_names"] = {"value": la_cand, "status": "FOUND", "confidence": la.get("confidence") or conf, "ocr_engine": ocr_engine_name, "bounding_box": la.get("box"), "validation": "VALID"}
                            break

            # Check combined demographic line: [Sex] [DOB] [Nationality] [PassportNo]
            demo_match = re.search(r'([MFI]|\bMALE\b|\bFEMALE\b)?\s*(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})\s+([A-Za-z]+)\s+([A-Z0-9]{7,10})', text)
            if demo_match:
                s_code, d_str, n_str, p_str = demo_match.groups()
                if not fields["sex"]["value"] and s_code:
                    clean_s = "MALE" if s_code in ["M", "MALE", "I"] else "FEMALE"
                    fields["sex"] = {"value": clean_s, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                if not fields["date_of_birth"]["value"] and d_str:
                    fields["date_of_birth"] = {"value": d_str.strip(), "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                if not fields["nationality"]["value"] and n_str:
                    clean_n = "INDIAN" if n_str in ["INDIAN", "IND"] else n_str.strip()
                    if not cls.is_label_noise(clean_n):
                        fields["nationality"] = {"value": clean_n, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                if not fields["passport_number"]["value"] and p_str:
                    clean_p = p_str.strip()
                    if any(c.isdigit() for c in clean_p) and not cls.is_label_noise(clean_p):
                        fields["passport_number"] = {"value": clean_p, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # Check combined validity line: [VISA TYPE] [VALID FROM] [VALID UNTIL]
            val_match = re.search(r'\b(TOURIST|STUDENT|BUSINESS|TRANSIT|CONFERENCE|VISITOR|DIPLOMATIC)\b.*?(\d{1,2}\s*[A-Za-z0-9]{3,9}\s*\d{4})\s+(\d{1,2}\s*[A-Za-z0-9]{3,9}\s*\d{4})', text)
            if val_match:
                vtype, d1, d2 = val_match.groups()
                if not fields["visa_type"]["value"]:
                    fields["visa_type"] = {"value": vtype, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                if not fields["valid_from"]["value"]:
                    clean_d1 = d1.replace("0CT", "OCT").replace("0ct", "OCT")
                    m_d1 = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})', clean_d1)
                    val_d1 = m_d1.group(1) if m_d1 else clean_d1.strip()
                    fields["valid_from"] = {"value": val_d1, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                if not fields["valid_until"]["value"]:
                    clean_d2 = d2.replace("0CT", "OCT").replace("0ct", "OCT")
                    m_d2 = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})', clean_d2)
                    val_d2 = m_d2.group(1) if m_d2 else clean_d2.strip()
                    fields["valid_until"] = {"value": val_d2, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # Visa Number
            if not fields["visa_number"]["value"]:
                vnum_match = re.search(r'\b(?:VISA\s*(?:NO|NUMBER|NUM|#)?[\s\:\.]*|VIGNETTE\s*(?:NO|#)?[\s\:\.]*)([A-Z0-9]*\d[A-Z0-9]{5,11})\b', text)
                if vnum_match:
                    val = vnum_match.group(1)
                    if val not in ["VIGNETTE", "PASSPORT", "CATEGORY", "OFFICIAL"] and not cls.is_label_noise(val):
                        fields["visa_number"] = {"value": val, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                else:
                    vnum_gen = re.search(r'\b([A-Z]{1,3}\s*\d{7,8}|[A-Z]\d\s*\d{7})\b', text)
                    if vnum_gen:
                        cand_v = vnum_gen.group(1).strip()
                        if cand_v not in ["REPUBLIC", "PASSPORT", "CATEGORY", "OFFICIAL", "ISLANDS"] and not cls.is_label_noise(cand_v):
                            fields["visa_number"] = {"value": cand_v, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # Visa Type (standalone or combined)
            if not fields["visa_type"]["value"]:
                for vt in ["TOURIST", "STUDENT", "BUSINESS", "TRANSIT", "CONFERENCE", "VISITOR", "DIPLOMATIC", "OFFICIAL", "EMPLOYMENT", "ENTRY"]:
                    if re.search(r'\b' + vt + r'\b', text):
                        fields["visa_type"] = {"value": vt, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                        break

            # Entries
            if not fields["entries"]["value"]:
                if "MULT" in text or "MULTIPLE" in text:
                    fields["entries"] = {"value": "MULTIPLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                elif "SINGLE" in text or re.search(r'\b0?1\s*ENTRY\b', text):
                    fields["entries"] = {"value": "SINGLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                elif "DOUBLE" in text or re.search(r'\b0?2\s*ENTRIES\b', text):
                    fields["entries"] = {"value": "DOUBLE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # Stay duration
            if not fields["stay_duration"]["value"]:
                stay_match = re.search(r'\b(\d{1,3})\s*(DAYS|DAY|MONTHS|MONTH)\b', text)
                if stay_match:
                    fields["stay_duration"] = {"value": f"{stay_match.group(1)} {stay_match.group(2)}", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}

            # Standalone fallback date extractions
            if not fields["valid_from"]["value"] and any(k in text for k in ["VALID FROM", "VALIDE DU", "FROM", "DU:"]):
                d = cls._extract_date(raw)
                if d:
                    fields["valid_from"] = {"value": d, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
            if not fields["valid_until"]["value"] and any(k in text for k in ["VALID UNTIL", "VALIDE JUSQU", "UNTIL", "EXPIRY", "EXPIRATION"]):
                d = cls._extract_date(raw)
                if d:
                    fields["valid_until"] = {"value": d, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
            if not fields["date_of_birth"]["value"] and any(k in text for k in ["BIRTH", "DOB", "NAISSANCE"]):
                d = cls._extract_date(raw)
                if d:
                    fields["date_of_birth"] = {"value": d, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
            if not fields["sex"]["value"] and any(k in text for k in ["SEX", "SEXE", "GENDER"]):
                m_sex = re.search(r'\b(MALE|FEMALE|M|F)\b', text)
                if m_sex:
                    val_s = m_sex.group(1)
                    fields["sex"] = {"value": "MALE" if val_s in ("M", "MALE") else "FEMALE", "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
            if not fields["nationality"]["value"] and any(k in text for k in ["NATIONALITY", "CITIZENSHIP", "NATIONALITE"]):
                for nat in ["INDIAN", "IND", "USA", "GBR", "CAN", "AUS", "FRA", "DEU", "JPN", "SGP", "ARE"]:
                    if nat in text:
                        fields["nationality"] = {"value": "INDIAN" if nat in ["INDIAN", "IND"] else nat, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                        break
            if not fields["passport_number"]["value"] and any(k in text for k in ["PASSPORT", "DOC NO", "PPT NO", "PASSEPORT"]):
                cleaned_ppt = re.sub(r'.*(?:PASSPORT|DOC|PPT|PASSEPORT)[\s\:\./#]*(?:NO|NUMBER)?[\s\:\./]*', '', text).strip()
                p_match = re.search(r'\b([A-Z0-9]{7,10})\b', cleaned_ppt)
                if p_match:
                    cand_p = p_match.group(1)
                    if any(c.isdigit() for c in cand_p) and cand_p not in ["PASSPORT", "PASSEPORT", "REPUBLIC"] and not cls.is_label_noise(cand_p):
                        fields["passport_number"] = {"value": cand_p, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                else:
                    for token in re.findall(r'\b([A-Z0-9]{7,10})\b', text):
                        if any(c.isdigit() for c in token) and any(c.isalpha() for c in token) and token not in ["PASSPORT", "PASSEPORT", "REPUBLIC", "CATEGORY", "OFFICIAL"] and not cls.is_label_noise(token):
                            fields["passport_number"] = {"value": token, "status": "FOUND", "confidence": conf, "ocr_engine": ocr_engine_name, "bounding_box": box, "validation": "VALID"}
                            break

        # Synthesize Full Name / Holder Name
        g_val = fields["given_names"]["value"]
        s_val = fields["surname"]["value"]
        if g_val and s_val:
            fields["holder_name"] = {"value": f"{g_val} {s_val}".strip(), "status": "FOUND", "confidence": min(fields["given_names"]["confidence"] or 0.9, fields["surname"]["confidence"] or 0.9), "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "VALID"}
        elif s_val:
            fields["holder_name"] = {"value": s_val, "status": "FOUND", "confidence": fields["surname"]["confidence"], "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "VALID"}
        elif g_val:
            fields["holder_name"] = {"value": g_val, "status": "FOUND", "confidence": fields["given_names"]["confidence"], "ocr_engine": ocr_engine_name, "bounding_box": None, "validation": "VALID"}

        # Strict Label-Noise Suppression Gate: purge any remaining label tokens
        for fk in list(fields.keys()):
            val = fields[fk].get("value")
            if val is not None:
                val_str = str(val).strip()
                if cls.is_label_noise(val_str):
                    fields[fk]["value"] = None
                    fields[fk]["status"] = "NOT_FOUND"

        return fields

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
