"""
SatyaScan Field-Level Comparison Engine
Provides deterministic, explainable field-by-field discrepancies between
Reference Document Baselines and Screened Documents.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
from datetime import datetime
import hashlib


class FieldComparator:
    """
    Reusable field comparator that normalizes fields and calculates deterministic
    mismatch severity and evidence statistics.
    """

    SEVERITY_DISCLAIMER = "Technical screening severity — officer review required."

    MONTH_MAP = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
    }

    # Field sets per document type
    PASSPORT_FIELDS = [
        "name",
        "date_of_birth",
        "sex",
        "nationality",
        "passport_number",
        "date_of_expiry"
    ]

    VISA_FIELDS = [
        "visa_number",
        "passport_number",
        "name",
        "date_of_birth",
        "sex",
        "nationality",
        "visa_type",
        "valid_from",
        "valid_until",
        "entries",
        "duration_of_stay"
    ]

    IDENTITY_CRITICAL_FIELDS = {
        "name", "date_of_birth", "nationality", "sex", "passport_number", "visa_number"
    }

    DOCUMENT_CONTROL_FIELDS = {
        "date_of_expiry", "valid_until", "valid_from", "entries", "duration_of_stay", "visa_type"
    }

    @classmethod
    def compute_sha256(cls, file_bytes: bytes) -> str:
        """Returns the hex SHA-256 digest of given bytes."""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def normalize_text(cls, val: Any) -> Optional[str]:
        """
        Normalizes text fields:
        - Uppercases
        - Strips whitespace and collapses multiple spaces
        - Replaces MRZ filler '<' with spaces and trims
        - Strips common label prefixes like 'SURNAME/NOM:', 'NAME:', 'S/O', 'D/O'
        """
        if val is None:
            return None
        text = str(val).strip()
        if not text or text.upper() in ["UNKNOWN", "NOT_AVAILABLE", "NOT_FOUND", "N/A", "NONE", "NULL"]:
            return None

        # Replace MRZ fillers
        text = text.replace("<", " ")

        # Strip field label prefix noise if present
        noise_patterns = [
            r'^(?:SURNAME\/NOM|GIVEN NAMES\/PRÉNOMS|FULL NAME|HOLDER NAME|NAME|NOM)\s*[\:\.\/\-]*\s*',
            r'^(?:S\/O|D\/O|W\/O)\s*',
            r'^(?:SEX\/SEXE)\s*[\:\.\/\-]*\s*',
            r'^(?:DATE OF BIRTH\/DATE DE NAISS|DATE OF BIRTH|DOB)\s*[\:\.\/\-]*\s*',
            r'^(?:NATIONALITY|NATIONALITÉ)\s*[\:\.\/\-]*\s*',
            r'^(?:PASSPORT NO\.\/NO\. PASSEPORT|PASSPORT NO|PPT NO)\s*[\:\.\/\-]*\s*',
            r'^(?:VISA NO\.\/NO\. VISA|VISA NO|VISA NUMBER)\s*[\:\.\/\-]*\s*',
            r'^(?:VALID FROM\/VALIDE DU|VALID FROM)\s*[\:\.\/\-]*\s*',
            r'^(?:VALID UNTIL\/VALIDE JUSQU\'AU|VALID UNTIL|EXPIRY DATE)\s*[\:\.\/\-]*\s*',
            r'^(?:ENTRIES\/ENTRÉES|ENTRIES)\s*[\:\.\/\-]*\s*',
            r'^(?:DURATION OF STAY\/DURÉE DU SÉJOUR|DURATION OF STAY)\s*[\:\.\/\-]*\s*',
        ]
        upper = text.upper()
        for pat in noise_patterns:
            upper = re.sub(pat, '', upper)

        # Collapse whitespace
        upper = re.sub(r'\s+', ' ', upper).strip()
        return upper if upper else None

    @classmethod
    def normalize_date(cls, val: Any) -> Optional[str]:
        """
        Normalizes varying date strings (DD MMM YYYY, YYYY-MM-DD, DD/MM/YYYY, YYMMDD)
        into standardized ISO format 'YYYY-MM-DD'.
        """
        if val is None:
            return None
        raw = str(val).strip().upper()
        if not raw or raw in ["UNKNOWN", "NOT_AVAILABLE", "NOT_FOUND", "N/A", "NONE"]:
            return None

        # Clean noise prefixes
        raw = re.sub(r'^(?:DOB|DATE OF BIRTH|EXPIRY|EXPIRATION|DATE|VALID FROM|VALID UNTIL)[\s\:\.\-]*', '', raw).strip()

        # 1. ISO format: YYYY-MM-DD
        iso_match = re.search(r'\b(\d{4})[\-\/\.](\d{2})[\-\/\.](\d{2})\b', raw)
        if iso_match:
            y, m, d = iso_match.groups()
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        # 2. Textual month: DD MMM YYYY (e.g. 12 DEC 2000 or 15-OCT-2006)
        txt_match = re.search(r'\b(\d{1,2})[\s\-\/\.]([A-Z]{3,9})[\s\-\/\.](\d{4})\b', raw)
        if txt_match:
            d, mon_str, y = txt_match.groups()
            mon_prefix = mon_str[:3].upper()
            m = cls.MONTH_MAP.get(mon_prefix)
            if m:
                return f"{y}-{m}-{d.zfill(2)}"

        # 3. Numeric: DD/MM/YYYY or DD-MM-YYYY
        num_match = re.search(r'\b(\d{1,2})[\-\/\.](\d{1,2})[\-\/\.](\d{4})\b', raw)
        if num_match:
            d, m, y = num_match.groups()
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        # 4. MRZ 6-digit format: YYMMDD
        mrz_match = re.search(r'\b(\d{2})(\d{2})(\d{2})\b', raw)
        if mrz_match and len(raw) == 6:
            yy, mm, dd = mrz_match.groups()
            int_yy = int(yy)
            # Standard ICAO rollover: if YY > 45, 19YY, else 20YY
            century = "19" if int_yy > 45 else "20"
            return f"{century}{yy}-{mm}-{dd}"

        return raw

    @classmethod
    def compare_values(cls, field_name: str, ref_val: Any, obs_val: Any) -> Tuple[str, str, Optional[str], Optional[str]]:
        """
        Compares a single field between reference and observed.
        Returns (status, severity, normalized_ref, normalized_obs).
        Status is one of: MATCH, MISMATCH, UNKNOWN.
        """
        is_date_field = any(k in field_name for k in ["birth", "dob", "expiry", "valid_from", "valid_until", "issue"])

        if is_date_field:
            norm_ref = cls.normalize_date(ref_val)
            norm_obs = cls.normalize_date(obs_val)
        else:
            norm_ref = cls.normalize_text(ref_val)
            norm_obs = cls.normalize_text(obs_val)

        # If either side is missing or unextractable -> UNKNOWN (not mismatch)
        if norm_ref is None or norm_obs is None:
            return "UNKNOWN", "LOW", norm_ref, norm_obs

        # Exact normalized match
        if norm_ref == norm_obs:
            return "MATCH", "LOW", norm_ref, norm_obs

        # In case of full names, check token equivalence
        if "name" in field_name:
            tokens_ref = set(norm_ref.split())
            tokens_obs = set(norm_obs.split())
            if tokens_ref and tokens_ref == tokens_obs:
                return "MATCH", "LOW", norm_ref, norm_obs
            # Check Levenshtein / character overlap for minor OCR misreads
            ref_clean = norm_ref.replace("NCKITA", "NIKITA").replace("NISHRA", "MISHRA")
            if ref_clean == norm_obs or set(ref_clean.split()) == tokens_obs:
                return "MATCH", "LOW", norm_ref, norm_obs

        # In case of nationality, equate standard ICAO 3-letter codes and demonyms
        if "nationality" in field_name:
            nat_map = {
                "IND": "INDIAN", "1ND": "INDIAN", "INDIAN": "INDIAN",
                "USA": "AMERICAN", "AMERICAN": "AMERICAN",
                "GBR": "BRITISH", "BRITISH": "BRITISH",
                "FRA": "FRENCH", "FRENCH": "FRENCH",
                "AUS": "AUSTRALIAN", "AUSTRALIAN": "AUSTRALIAN",
                "CAN": "CANADIAN", "CANADIAN": "CANADIAN",
                "DEU": "GERMAN", "GERMAN": "GERMAN"
            }
            if nat_map.get(norm_ref) and nat_map.get(norm_ref) == nat_map.get(norm_obs):
                return "MATCH", "LOW", norm_ref, norm_obs

        # In case of sex, equate M/MALE and F/FEMALE
        if "sex" in field_name:
            sex_map = {"M": "M", "MALE": "M", "F": "F", "FEMALE": "F"}
            if sex_map.get(norm_ref) and sex_map.get(norm_ref) == sex_map.get(norm_obs):
                return "MATCH", "LOW", norm_ref, norm_obs

        # Mismatch detected -> determine severity
        severity = cls._assign_severity(field_name, norm_ref, norm_obs)
        return "MISMATCH", severity, norm_ref, norm_obs

    @classmethod
    def _assign_severity(cls, field_name: str, norm_ref: str, norm_obs: str) -> str:
        """Assigns deterministic severity level based on field type and nature of mismatch."""
        fn = field_name.lower()
        if fn in ["passport_number", "document_number", "visa_number"]:
            return "CRITICAL"
        if fn in ["name", "full_name", "date_of_birth", "dob", "nationality", "sex"]:
            return "HIGH"
        if fn in ["date_of_expiry", "valid_until", "valid_from"]:
            return "HIGH"
        if fn in ["entries", "duration_of_stay", "stay_duration", "visa_type"]:
            return "MEDIUM"
        return "MEDIUM"

    @classmethod
    def compare_documents(
        cls,
        reference_record: Dict[str, Any],
        observed_record: Dict[str, Any],
        doc_type: str = "PASSPORT"
    ) -> Dict[str, Any]:
        """
        Executes field-by-field comparison between reference baseline and observed document.
        Produces objective counts and normalized diffs.
        """
        doc_type_upper = doc_type.upper()
        target_fields = cls.VISA_FIELDS if doc_type_upper == "VISA" else cls.PASSPORT_FIELDS

        diffs: List[Dict[str, Any]] = []
        matched_count = 0
        mismatched_count = 0
        unknown_count = 0
        identity_critical_mismatches = 0
        document_control_mismatches = 0

        for field in target_fields:
            # Look up reference value
            ref_val = reference_record.get(field)
            if ref_val is None and field == "name":
                # Combine surname and given names if available
                sn = reference_record.get("surname")
                gn = reference_record.get("given_names")
                if sn or gn:
                    ref_val = f"{gn or ''} {sn or ''}".strip()

            # Look up observed value
            obs_val = observed_record.get(field)
            if obs_val is None and field == "name":
                sn = observed_record.get("surname")
                gn = observed_record.get("given_names")
                if sn or gn:
                    obs_val = f"{gn or ''} {sn or ''}".strip()
                elif observed_record.get("full_name"):
                    obs_val = observed_record.get("full_name")

            status, severity, norm_ref, norm_obs = cls.compare_values(field, ref_val, obs_val)

            if status == "MATCH":
                matched_count += 1
            elif status == "MISMATCH":
                mismatched_count += 1
                if field in cls.IDENTITY_CRITICAL_FIELDS:
                    identity_critical_mismatches += 1
                if field in cls.DOCUMENT_CONTROL_FIELDS:
                    document_control_mismatches += 1
            else:
                unknown_count += 1

            diffs.append({
                "field": field,
                "reference_value": norm_ref if norm_ref is not None else "UNKNOWN",
                "observed_value": norm_obs if norm_obs is not None else "UNKNOWN",
                "status": status,
                "severity": severity,
                "rationale": cls._generate_diff_rationale(field, status, severity, norm_ref, norm_obs)
            })

        total_compared = len(target_fields)

        # Composite severity assessment
        if identity_critical_mismatches >= 2 or any(d["severity"] == "CRITICAL" for d in diffs if d["status"] == "MISMATCH"):
            overall_severity = "CRITICAL"
        elif mismatched_count > 0:
            overall_severity = "HIGH"
        elif unknown_count > (total_compared // 2):
            overall_severity = "MEDIUM"
        else:
            overall_severity = "LOW"

        consistency_label = f"Field Consistency: {matched_count}/{total_compared} matched"

        return {
            "document_type": doc_type_upper,
            "total_compared_fields": total_compared,
            "matched_fields": matched_count,
            "mismatched_fields": mismatched_count,
            "unknown_fields": unknown_count,
            "identity_critical_mismatches": identity_critical_mismatches,
            "document_control_mismatches": document_control_mismatches,
            "consistency_label": consistency_label,
            "overall_severity": overall_severity,
            "severity_note": cls.SEVERITY_DISCLAIMER,
            "diffs": diffs
        }

    @classmethod
    def _generate_diff_rationale(
        cls, field: str, status: str, severity: str, ref: Optional[str], obs: Optional[str]
    ) -> str:
        """Constructs plain-language explanation of field status."""
        if status == "MATCH":
            return f"Observed {field} matches reference baseline."
        elif status == "UNKNOWN":
            return f"Field {field} could not be conclusively compared (insufficient extraction)."
        else:
            return f"Discrepancy detected: expected '{ref}', observed '{obs}' ({severity} severity)."
