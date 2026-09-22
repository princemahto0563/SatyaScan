"""
SatyaScan Passport <-> Visa Linkage Engine
Cross-verifies identity and document linkages between an applicant's
passport and visa records.
"""

from typing import Dict, Any, List, Optional
from ai.comparison.field_comparator import FieldComparator


class PassportVisaLinkageChecker:
    """
    Evaluates cross-document consistency between Passport and Visa records.
    """

    LINKAGE_FIELDS = [
        ("passport_number", "Passport Number Linkage"),
        ("name", "Applicant Name"),
        ("date_of_birth", "Date of Birth"),
        ("nationality", "Nationality"),
        ("sex", "Sex")
    ]

    @classmethod
    def verify_linkage(
        cls,
        passport_record: Dict[str, Any],
        visa_record: Dict[str, Any],
        face_similarity: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Cross-validates linkage between a passport and a visa.
        Returns detailed check results, linkage status, and officer guidance.
        """
        field_results: List[Dict[str, Any]] = []
        matches = 0
        mismatches = 0
        unknowns = 0
        passport_number_match = False

        for field, label in cls.LINKAGE_FIELDS:
            p_val = passport_record.get(field)
            if p_val is None and field == "name":
                sn = passport_record.get("surname")
                gn = passport_record.get("given_names")
                if sn or gn:
                    p_val = f"{gn or ''} {sn or ''}".strip()

            v_val = visa_record.get(field)
            if v_val is None and field == "name":
                sn = visa_record.get("surname")
                gn = visa_record.get("given_names")
                if sn or gn:
                    v_val = f"{gn or ''} {sn or ''}".strip()
                elif visa_record.get("holder_name"):
                    v_val = visa_record.get("holder_name")

            status, severity, norm_p, norm_v = FieldComparator.compare_values(field, p_val, v_val)

            if status == "MATCH":
                matches += 1
                if field == "passport_number":
                    passport_number_match = True
            elif status == "MISMATCH":
                mismatches += 1
            else:
                unknowns += 1

            field_results.append({
                "field": field,
                "label": label,
                "passport_value": norm_p if norm_p is not None else "UNKNOWN",
                "visa_value": norm_v if norm_v is not None else "UNKNOWN",
                "status": status,
                "severity": "CRITICAL" if field == "passport_number" and status == "MISMATCH" else severity
            })

        # Biometric Linkage
        face_status = "UNKNOWN"
        if face_similarity is not None:
            if face_similarity >= 0.65:
                face_status = "MATCH"
            elif face_similarity >= 0.50:
                face_status = "BORDERLINE"
            else:
                face_status = "MISMATCH"

        # Overall Linkage Status determination
        if mismatches == 0 and matches >= 3 and passport_number_match:
            overall_status = "MATCH"
            officer_summary = "Passport and Visa exhibit complete identity and document number consistency."
        elif not passport_number_match and any(r["field"] == "passport_number" and r["status"] == "MISMATCH" for r in field_results):
            overall_status = "MISMATCH"
            officer_summary = "CRITICAL LINKAGE ERROR: Visa links to a different passport number than presented passport."
        elif mismatches > 0:
            overall_status = "MISMATCH"
            officer_summary = f"Linkage discrepancy detected: {mismatches} field(s) differ between Passport and Visa."
        elif matches >= 1:
            overall_status = "PARTIAL_MATCH"
            officer_summary = "Partial linkage established; secondary field verification required."
        else:
            overall_status = "UNABLE_TO_VERIFY"
            officer_summary = "Insufficient common fields to establish conclusive Passport-Visa linkage."

        return {
            "overall_linkage_status": overall_status,
            "passport_number_linked": passport_number_match,
            "fields_compared": len(cls.LINKAGE_FIELDS),
            "matched_fields": matches,
            "mismatched_fields": mismatches,
            "unknown_fields": unknowns,
            "biometric_linkage_status": face_status,
            "biometric_similarity": face_similarity,
            "officer_summary": officer_summary,
            "field_results": field_results
        }
