"""
SatyaScan ICAO Doc 9303 TD3 MRZ Parser & Validator
Implements official ICAO 7-3-1 check digit calculation, field parsing,
and Visual Inspection Zone (VIZ) cross-validation.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re


class MRZParser:
    """
    Parser and mathematical validator for ICAO Doc 9303 TD3 Machine Readable Travel Documents.
    TD3 standard specifies 2 lines of exactly 44 alphanumeric characters.
    """

    WEIGHTS = [7, 3, 1]

    def __init__(self):
        self.version = "Doc9303-TD3-v1.0"

    @staticmethod
    def char_to_value(char: str) -> int:
        """Converts an MRZ character to its ICAO Doc 9303 numerical value."""
        char = char.upper()
        if '0' <= char <= '9':
            return int(char)
        elif 'A' <= char <= 'Z':
            return ord(char) - ord('A') + 10
        elif char == '<':
            return 0
        return 0

    @classmethod
    def calculate_check_digit(cls, data_string: str) -> str:
        """
        Calculates the ICAO 7-3-1 modulus 10 check digit for a given string.
        """
        total = 0
        for i, char in enumerate(data_string):
            val = cls.char_to_value(char)
            weight = cls.WEIGHTS[i % 3]
            total += val * weight
        return str(total % 10)

    @classmethod
    def verify_check_digit(cls, data_string: str, observed_digit: str) -> Tuple[bool, str]:
        """
        Compares observed check digit against calculated check digit.
        Returns (is_valid, expected_digit).
        """
        expected = cls.calculate_check_digit(data_string)
        return (observed_digit == expected, expected)

    @classmethod
    def normalize_mrz_line(cls, line: Any, is_line1: bool = True) -> str:
        """Clean and normalize potential OCR noise in MRZ line to exact 44 TD3 chars."""
        if not line:
            return ""
        if isinstance(line, dict):
            line = line.get("text", "")
        line = str(line).strip().upper()
        # Replace common OCR misreads in MRZ filler
        line = re.sub(r'[\s«»\-_/]+', '<', line)
        line = re.sub(r'[^A-Z0-9<]', '<', line)

        # Align Line 1 to start at P< if possible
        if is_line1:
            idx = line.find("P<")
            if idx == -1:
                # Check for common P0 or P(
                m = re.search(r'P[<0A-Z]', line)
                if m:
                    idx = m.start()
            if idx > 0:
                line = line[idx:]
            # Normalize common OCR confusions in issuing country code (e.g. dropped 'I' in 'IND')
            if line.startswith("P<ND"):
                line = "P<IND" + line[4:]
            elif line.startswith("P<1ND") or line.startswith("P<TND") or line.startswith("P<LND"):
                line = "P<IND" + line[5:]
            # Clean trailing K misread as chevron directly following given names and preceding filler chevrons
            line = re.sub(r'<<([A-Z0-9]+)K<', r'<<\1<<', line)
            # After primary and secondary identifiers, clean trailing filler noise (K, E, X, C)
            parts = line.split("<<")
            if len(parts) >= 2:
                # Keep up to second part and clean trailing chevrons
                prefix = "<<".join(parts[:2])
                suffix = "<<" + "<<".join(parts[2:]) if len(parts) > 2 else ""
                suffix_clean = re.sub(r'[KEXC<]', '<', suffix)
                line = prefix + suffix_clean
        else:
            # Line 2: find start of 9-char document number followed by digit check
            m = re.search(r'[A-Z0-9<]{9}[0-9]', line)
            if m and m.start() > 0:
                line = line[m.start():]
            # In line 2, positions 28..42 (optional data filler) often misread chevrons as C, K, E, X
            if len(line) >= 30:
                prefix = line[:28]
                if len(line) >= 44:
                    mid = re.sub(r'[KEXC<]', '<', line[28:42])
                    end = line[42:]
                    line = prefix + mid + end
                else:
                    mid = re.sub(r'[KEXC<]', '<', line[28:])
                    line = prefix + mid

        # Truncate or pad to exactly 44 characters (only pad if line has reasonable length >= 35)
        if len(line) > 44:
            line = line[:44]
        elif len(line) >= 35:
            line = line.ljust(44, '<')

        return line

    @classmethod
    def parse_td3(cls, line1: Any, line2: Any) -> Dict[str, Any]:
        """
        Parses 2 lines of TD3 MRZ and verifies all internal check digits.
        Normalizes OCR variations and ensures 44-character line lengths.
        Auto-swaps lines if line2 is the header line or line1 is the data line.
        """
        s1 = line1.get("text", "") if isinstance(line1, dict) else str(line1 or "")
        s2 = line2.get("text", "") if isinstance(line2, dict) else str(line2 or "")

        # Auto-detect if line order is reversed
        s1_clean = s1.replace(" ", "").upper()
        s2_clean = s2.replace(" ", "").upper()
        if not s1_clean.startswith(("P<", "P0", "V<")) and s2_clean.startswith(("P<", "P0", "V<")):
            s1, s2 = s2, s1

        l1 = cls.normalize_mrz_line(s1, is_line1=True)
        l2 = cls.normalize_mrz_line(s2, is_line1=False)

        if len(l1) != 44 or len(l2) != 44:
            return {
                "parsed": False,
                "error": "MRZ_PARSE_FAILED",
                "message": f"TD3 MRZ line length mismatch: Line 1={len(l1)} chars, Line 2={len(l2)} chars. Exactly 44 characters required."
            }

        # Line 1 Breakdown:
        # Pos 0-1: Document code (P<, P, etc.)
        doc_code = l1[0:2].replace('<', '')
        # Pos 2-5: Issuing State (3 chars)
        issuing_country = l1[2:5].replace('<', '')
        if issuing_country in ["1ND", "TND", "LND"]:
            issuing_country = "IND"

        # Pos 5-44: Name (Primary identifier << Secondary identifier)
        name_section = l1[5:44]
        # Normalize digits in name section to letters (common OCR confusions)
        name_clean = (
            name_section
            .replace('0', 'O')
            .replace('1', 'I')
            .replace('5', 'S')
            .replace('8', 'B')
        )
        name_parts = name_clean.split('<<')
        surname = name_parts[0].replace('<', ' ').strip() if len(name_parts) > 0 else ""
        given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""
        full_name = f"{given_names} {surname}".strip() if given_names else surname

        # Line 2 Breakdown:
        # Pos 0-9: Document Number (9 chars)
        raw_doc_number = l2[0:9]
        doc_number = raw_doc_number.replace('<', '')
        doc_num_check = l2[9]

        # Pos 10-13: Nationality (3 chars)
        nationality = l2[10:13].replace('<', '')
        if nationality in ["1ND", "TND", "LND"]:
            nationality = "IND"

        # Helper to clean digit fields where OCR read letters instead of numbers
        def clean_digit_str(s: str) -> str:
            trans = str.maketrans("ODQILZS", "0001125")
            return s.translate(trans)

        # Pos 13-19: Date of Birth (YYMMDD)
        raw_dob = clean_digit_str(l2[13:19])
        dob_check = clean_digit_str(l2[19]) if len(l2) > 19 else ""

        # Pos 20: Sex (M/F/<) - with resilient alignment for dropped/inserted OCR chars
        sex_pos = 20
        for cand_idx in [20, 21, 19, 22]:
            if cand_idx < len(l2) and l2[cand_idx] in ['M', 'F']:
                sex_pos = cand_idx
                break

        sex_code = l2[sex_pos] if sex_pos < len(l2) else "<"
        sex = "MALE" if sex_code == 'M' else "FEMALE" if sex_code == 'F' else "UNSPECIFIED"

        # Expiry is 6 digits immediately following Sex
        raw_expiry = clean_digit_str(l2[sex_pos + 1 : sex_pos + 7])
        expiry_check = clean_digit_str(l2[sex_pos + 7]) if len(l2) > sex_pos + 7 else ""

        # Pos 28-42: Optional Personal Number
        opt_start = sex_pos + 8
        raw_optional = l2[opt_start : opt_start + 14] if len(l2) >= opt_start + 14 else l2[28:42]
        optional_data = raw_optional.replace('<', '')
        optional_check = clean_digit_str(l2[opt_start + 14]) if len(l2) > opt_start + 14 else ""

        # Pos 43: Overall Composite Check Digit
        composite_check = clean_digit_str(l2[43]) if len(l2) > 43 else ""

        # Verify Check Digits
        valid_doc_num, exp_doc_num = cls.verify_check_digit(raw_doc_number, doc_num_check)
        valid_dob, exp_dob = cls.verify_check_digit(raw_dob, dob_check)
        valid_expiry, exp_expiry = cls.verify_check_digit(raw_expiry, expiry_check)

        # Optional check digit (only if optional data is non-empty)
        valid_optional = True
        exp_optional = optional_check
        if optional_data and optional_check.isdigit():
            valid_optional, exp_optional = cls.verify_check_digit(raw_optional, optional_check)

        # Composite check digit (covers doc_number + check + dob + check + expiry + check + optional + check)
        composite_payload = raw_doc_number + doc_num_check + raw_dob + dob_check + raw_expiry + expiry_check + raw_optional + (optional_check or "0")
        valid_composite, exp_composite = cls.verify_check_digit(composite_payload, composite_check)

        all_checks_passed = all([valid_doc_num, valid_dob, valid_expiry, valid_composite])

        # Date normalization helpers (pivot year 50: >50 is 19XX, <=50 is 20XX)
        def parse_yymmdd(yymmdd_str: str, is_expiry: bool = False) -> Optional[str]:
            if len(yymmdd_str) != 6 or not yymmdd_str.isdigit():
                return None
            yy = int(yymmdd_str[0:2])
            mm = int(yymmdd_str[2:4])
            dd = int(yymmdd_str[4:6])
            if not (1 <= mm <= 12 and 1 <= dd <= 31):
                return None
            current_year_last2 = datetime.now().year % 100
            if is_expiry:
                # Expiry is usually in current century
                century = 2000 if yy <= current_year_last2 + 40 else 1900
            else:
                # DOB pivot
                century = 2000 if yy <= current_year_last2 else 1900
            year = century + yy
            return f"{year:04d}-{mm:02d}-{dd:02d}"

        iso_dob = parse_yymmdd(raw_dob, is_expiry=False)
        iso_expiry = parse_yymmdd(raw_expiry, is_expiry=True)

        is_expired = False
        if iso_expiry:
            try:
                exp_dt = datetime.strptime(iso_expiry, "%Y-%m-%d")
                is_expired = exp_dt < datetime.now()
            except Exception:
                pass

        return {
            "parsed": True,
            "document_code": doc_code,
            "issuing_country": issuing_country,
            "full_name": full_name,
            "surname": surname,
            "given_names": given_names,
            "document_number": doc_number,
            "nationality": nationality,
            "date_of_birth": iso_dob,
            "raw_date_of_birth": raw_dob,
            "sex": sex,
            "date_of_expiry": iso_expiry,
            "raw_date_of_expiry": raw_expiry,
            "is_expired": is_expired,
            "optional_data": optional_data,
            "raw_lines": [l1, l2],
            "check_digits": {
                "document_number": {
                    "observed": doc_num_check,
                    "expected": exp_doc_num,
                    "valid": valid_doc_num
                },
                "date_of_birth": {
                    "observed": dob_check,
                    "expected": exp_dob,
                    "valid": valid_dob
                },
                "date_of_expiry": {
                    "observed": expiry_check,
                    "expected": exp_expiry,
                    "valid": valid_expiry
                },
                "optional_data": {
                    "observed": optional_check,
                    "expected": exp_optional,
                    "valid": valid_optional
                },
                "composite": {
                    "observed": composite_check,
                    "expected": exp_composite,
                    "valid": valid_composite
                }
            },
            "all_checks_passed": all_checks_passed,
            "status_message": "All ICAO Doc 9303 check digits verified." if all_checks_passed else "MRZ integrity check failed — manual verification required."
        }

    @classmethod
    def cross_validate_viz(cls, mrz_data: Dict[str, Any], viz_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Cross-validates Visual Inspection Zone (VIZ) extracted fields against MRZ decoded fields.
        Returns a list of finding dictionaries with severity, field, expected, observed, message.
        """
        findings: List[Dict[str, Any]] = []

        if not mrz_data.get("parsed"):
            return findings

        # 1. Cross-check Document Number
        viz_doc_num = (viz_fields.get("document_number") or viz_fields.get("passport_number") or "").replace(" ", "").upper()
        mrz_doc_num = (mrz_data.get("document_number") or "").replace(" ", "").upper()

        if viz_doc_num and mrz_doc_num:
            if viz_doc_num != mrz_doc_num:
                findings.append({
                    "rule_id": "VIZ_MRZ_DOC_NUM_MATCH",
                    "severity": "CRITICAL",
                    "field": "document_number",
                    "expected": mrz_doc_num,
                    "observed": viz_doc_num,
                    "message": f"Visual document number '{viz_doc_num}' does not match MRZ document number '{mrz_doc_num}'.",
                    "classification": "OFFICIAL_STANDARD"
                })

        # 2. Cross-check Date of Birth
        viz_dob = (viz_fields.get("date_of_birth") or viz_fields.get("dob") or "").strip()
        mrz_dob = (mrz_data.get("date_of_birth") or "").strip()

        if viz_dob and mrz_dob:
            # Normalize viz_dob if formatted as DD/MM/YYYY or DD-MM-YYYY
            viz_dob_norm = cls._normalize_date_string(viz_dob)
            if viz_dob_norm and viz_dob_norm != mrz_dob:
                findings.append({
                    "rule_id": "VIZ_MRZ_DOB_MATCH",
                    "severity": "CRITICAL",
                    "field": "date_of_birth",
                    "expected": mrz_dob,
                    "observed": viz_dob,
                    "message": f"Visual Date of Birth '{viz_dob}' differs from MRZ Date of Birth '{mrz_dob}'. Potential date manipulation.",
                    "classification": "OFFICIAL_STANDARD"
                })

        # 3. Cross-check Date of Expiry
        viz_exp = (viz_fields.get("date_of_expiry") or viz_fields.get("expiry") or "").strip()
        mrz_exp = (mrz_data.get("date_of_expiry") or "").strip()

        if viz_exp and mrz_exp:
            viz_exp_norm = cls._normalize_date_string(viz_exp)
            if viz_exp_norm and viz_exp_norm != mrz_exp:
                findings.append({
                    "rule_id": "VIZ_MRZ_EXPIRY_MATCH",
                    "severity": "HIGH",
                    "field": "date_of_expiry",
                    "expected": mrz_exp,
                    "observed": viz_exp,
                    "message": f"Visual Expiry Date '{viz_exp}' differs from MRZ Expiry Date '{mrz_exp}'.",
                    "classification": "OFFICIAL_STANDARD"
                })

        # 4. Cross-check Name
        viz_name = (viz_fields.get("full_name") or viz_fields.get("name") or "").upper().replace(".", " ").strip()
        mrz_name = (mrz_data.get("full_name") or "").upper().strip()

        if viz_name and mrz_name:
            # Check token overlap between visual name and MRZ name
            viz_tokens = set(re.findall(r'[A-Z]+', viz_name))
            mrz_tokens = set(re.findall(r'[A-Z]+', mrz_name))
            common = viz_tokens.intersection(mrz_tokens)
            if len(common) == 0 and len(viz_tokens) > 0 and len(mrz_tokens) > 0:
                findings.append({
                    "rule_id": "VIZ_MRZ_NAME_MATCH",
                    "severity": "HIGH",
                    "field": "full_name",
                    "expected": mrz_name,
                    "observed": viz_name,
                    "message": f"Visual name '{viz_name}' does not correlate with MRZ name '{mrz_name}'.",
                    "classification": "OFFICIAL_STANDARD"
                })

        return findings

    @staticmethod
    def _normalize_date_string(date_str: str) -> Optional[str]:
        """Normalize various human date representations (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.) to YYYY-MM-DD."""
        date_str = date_str.strip()
        patterns = [
            ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
            ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
            ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
            ("%d %b %Y", r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$"),
            ("%d %B %Y", r"^\d{1,2}\s+[A-Za-z]+\s+\d{4}$"),
        ]
        for fmt, regex in patterns:
            if re.match(regex, date_str):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        return None

    @classmethod
    def determine_mrz_state(
        cls,
        doc_type: str,
        page_type: str = "PASSPORT_IDENTITY_PAGE",
        candidate_lines: Optional[List[str]] = None,
        mrz_data: Optional[Dict[str, Any]] = None,
        is_identity_page: bool = True
    ) -> str:
        """
        Explicit 6-State MRZ State Machine (Phase 5):
        - MRZ_VALID: parsed = true, all_checks_passed = true
        - MRZ_INVALID: parsed = true, all_checks_passed = false (checksum failure)
        - MRZ_NOT_APPLICABLE: document/page genuinely does not use MRZ (e.g. Visa without MRZ)
        - MRZ_NOT_DETECTED: document type requires MRZ (e.g. Passport identity page), but 0 MRZ lines found
        - MRZ_UNPARSED: MRZ candidate lines detected, but parser failed Doc 9303 syntax/structure
        - MRZ_INPUT_INSUFFICIENT: Passport cover / address page / degraded image
        """
        doc_upper = (doc_type or "PASSPORT").upper()
        page_upper = (page_type or "").upper()
        candidates = candidate_lines or []

        if page_upper == "PASSPORT_COVER" or not is_identity_page:
            return "MRZ_INPUT_INSUFFICIENT"

        if mrz_data and mrz_data.get("parsed"):
            if mrz_data.get("all_checks_passed"):
                return "MRZ_VALID"
            else:
                return "MRZ_INVALID"

        if doc_upper == "VISA":
            has_mrz_line = any(
                l.replace(" ", "").upper().startswith(("V<", "P<")) or l.replace(" ", "").count("<") >= 4
                for l in candidates
            )
            if not has_mrz_line:
                return "MRZ_NOT_APPLICABLE"
            else:
                return "MRZ_UNPARSED"

        if not candidates or len(candidates) == 0:
            return "MRZ_NOT_DETECTED"

        return "MRZ_UNPARSED"
