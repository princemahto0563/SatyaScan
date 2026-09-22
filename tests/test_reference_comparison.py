"""
SatyaScan Field-Level Discrepancy & Reference Comparison Test Suite
Validates the 14 mandatory reference comparison requirements:
1. exact reference -> zero mismatches
2. changed name -> name mismatch
3. changed DOB -> DOB mismatch
4. changed passport number -> passport mismatch
5. changed visa number -> visa mismatch
6. changed visa expiry -> expiry mismatch
7. invalid MRZ digit -> MRZ failure
8. VIZ/MRZ discrepancy -> discrepancy detected
9. multiple changes -> correct mismatch count
10. unknown field -> UNKNOWN, not mismatch
11. exact image hash -> reference match
12. altered image hash -> reference differs
13. no raw PII in evaluation JSON
14. no raw images in git-tracked files
"""

import os
import json
import subprocess
import pytest
from ai.comparison.field_comparator import FieldComparator
from ai.comparison.linkage_checker import PassportVisaLinkageChecker
from ai.mrz.mrz_parser import MRZParser


# Baseline reference fixture for PERSON-001
REF_PASSPORT = {
    "name": "NAVNEET NEGI",
    "surname": "NEGI",
    "given_names": "NAVNEET",
    "passport_number": "N9876543",
    "nationality": "INDIAN",
    "date_of_birth": "2000-12-12",
    "sex": "M",
    "date_of_expiry": "2034-02-28"
}

REF_VISA = {
    "visa_number": "ABC1234567",
    "passport_number": "N9876543",
    "name": "NAVNEET NEGI",
    "date_of_birth": "2000-12-12",
    "sex": "M",
    "nationality": "INDIAN",
    "visa_type": "TOURIST - T1",
    "valid_from": "2024-04-15",
    "valid_until": "2024-10-14",
    "entries": "MULTIPLE",
    "duration_of_stay": "90 DAYS"
}


def test_01_exact_reference_zero_mismatches():
    """1. Exact reference matches -> zero mismatches."""
    observed = dict(REF_PASSPORT)
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    assert res["mismatched_fields"] == 0
    assert res["matched_fields"] == res["total_compared_fields"]
    assert res["consistency_label"] == f"Field Consistency: {res['total_compared_fields']}/{res['total_compared_fields']} matched"
    assert res["overall_severity"] == "LOW"


def test_02_changed_name_mismatch():
    """2. Changed name produces name mismatch with HIGH severity."""
    observed = dict(REF_PASSPORT)
    observed["name"] = "RAHUL KUMAR"
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    assert res["mismatched_fields"] == 1
    name_diff = next(d for d in res["diffs"] if d["field"] == "name")
    assert name_diff["status"] == "MISMATCH"
    assert name_diff["severity"] == "HIGH"
    assert name_diff["reference_value"] == "NAVNEET NEGI"
    assert name_diff["observed_value"] == "RAHUL KUMAR"


def test_03_changed_dob_mismatch():
    """3. Changed DOB produces DOB mismatch with normalized date comparison."""
    observed = dict(REF_PASSPORT)
    observed["date_of_birth"] = "20 JUL 2004"
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    dob_diff = next(d for d in res["diffs"] if d["field"] == "date_of_birth")
    assert dob_diff["status"] == "MISMATCH"
    assert dob_diff["severity"] == "HIGH"
    assert dob_diff["reference_value"] == "2000-12-12"
    assert dob_diff["observed_value"] == "2004-07-20"


def test_04_changed_passport_number_mismatch():
    """4. Changed passport number produces passport mismatch with CRITICAL severity."""
    observed = dict(REF_PASSPORT)
    observed["passport_number"] = "Z9999999"
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    p_diff = next(d for d in res["diffs"] if d["field"] == "passport_number")
    assert p_diff["status"] == "MISMATCH"
    assert p_diff["severity"] == "CRITICAL"


def test_05_changed_visa_number_mismatch():
    """5. Changed visa number produces visa mismatch with CRITICAL severity."""
    observed = dict(REF_VISA)
    observed["visa_number"] = "XYZ9876543"
    res = FieldComparator.compare_documents(REF_VISA, observed, doc_type="VISA")
    v_diff = next(d for d in res["diffs"] if d["field"] == "visa_number")
    assert v_diff["status"] == "MISMATCH"
    assert v_diff["severity"] == "CRITICAL"


def test_06_changed_visa_expiry_mismatch():
    """6. Changed visa expiry date produces valid_until mismatch."""
    observed = dict(REF_VISA)
    observed["valid_until"] = "14 DEC 2025"
    res = FieldComparator.compare_documents(REF_VISA, observed, doc_type="VISA")
    exp_diff = next(d for d in res["diffs"] if d["field"] == "valid_until")
    assert exp_diff["status"] == "MISMATCH"
    assert exp_diff["severity"] == "HIGH"
    assert exp_diff["reference_value"] == "2024-10-14"
    assert exp_diff["observed_value"] == "2025-12-14"


def test_07_invalid_mrz_digit_check():
    """7. Invalid MRZ check digit fails ICAO 7-3-1 validation."""
    line1 = "P<INDNEGI<<NAVNEET<<<<<<<<<<<<<<<<<<<<<<<<<<"
    # Exactly 44 characters: change document number check digit from 7 to 9
    line2_corrupted = "N9876543<9IND0012122M3402280<<<<<<<<<<<<<<24"
    assert len(line1) == 44
    assert len(line2_corrupted) == 44
    mrz_res = MRZParser.parse_td3(line1, line2_corrupted)
    assert mrz_res["parsed"] is True
    assert mrz_res["all_checks_passed"] is False
    assert mrz_res["check_digits"]["document_number"]["valid"] is False


def test_08_viz_mrz_discrepancy_detected():
    """8. VIZ/MRZ discrepancy is identified when visible and MRZ values conflict."""
    mrz_data = {
        "parsed": True,
        "document_number": "N9876543",
        "date_of_birth": "2000-12-12",
        "date_of_expiry": "2034-02-28",
        "surname": "NEGI",
        "given_names": "NAVNEET"
    }
    # VIZ has different DOB: 2004-07-20
    viz_fields = {
        "document_number": "N9876543",
        "date_of_birth": "20 JUL 2004",
        "date_of_expiry": "2034-02-28",
        "full_name": "NAVNEET NEGI"
    }
    findings = MRZParser.cross_validate_viz(mrz_data, viz_fields)
    assert len(findings) >= 1
    dob_finding = next(f for f in findings if f["field"] == "date_of_birth")
    assert dob_finding["severity"] in ["HIGH", "CRITICAL"]
    msg = dob_finding["message"].lower()
    assert "differs" in msg or "discrepancy" in msg or "mismatch" in msg


def test_09_multiple_changes_correct_mismatch_count():
    """9. Multiple changes produce accurate objective mismatch counts."""
    observed = dict(REF_PASSPORT)
    observed["name"] = "KUMAR RAHUL"
    observed["date_of_birth"] = "20 JUL 2004"
    observed["passport_number"] = "Z9999999"
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    assert res["mismatched_fields"] == 3
    assert res["identity_critical_mismatches"] == 3
    assert res["overall_severity"] == "CRITICAL"
    assert "3/6 matched" in res["consistency_label"]


def test_10_unknown_field_is_unknown_not_mismatch():
    """10. Unextracted/missing fields result in UNKNOWN, not MISMATCH."""
    observed = dict(REF_PASSPORT)
    observed["date_of_expiry"] = None
    res = FieldComparator.compare_documents(REF_PASSPORT, observed, doc_type="PASSPORT")
    exp_diff = next(d for d in res["diffs"] if d["field"] == "date_of_expiry")
    assert exp_diff["status"] == "UNKNOWN"
    assert res["mismatched_fields"] == 0
    assert res["unknown_fields"] == 1


def test_11_exact_image_hash_reference_match():
    """11. Exact image bytes produce matching SHA-256 hash."""
    data1 = b"REFERENCE_PASSPORT_IMAGE_BYTES_123"
    data2 = b"REFERENCE_PASSPORT_IMAGE_BYTES_123"
    h1 = FieldComparator.compute_sha256(data1)
    h2 = FieldComparator.compute_sha256(data2)
    assert h1 == h2


def test_12_altered_image_hash_reference_differs():
    """12. Altered image bytes produce distinct SHA-256 hash."""
    data1 = b"REFERENCE_PASSPORT_IMAGE_BYTES_123"
    data2 = b"ALTERED_PASSPORT_IMAGE_BYTES_456"
    h1 = FieldComparator.compute_sha256(data1)
    h2 = FieldComparator.compute_sha256(data2)
    assert h1 != h2


def test_13_no_raw_pii_in_evaluation_json():
    """13. Evaluation results JSON contains no unmasked PII."""
    eval_json_path = os.path.join("data", "metadata", "evaluation_results.json")
    if os.path.exists(eval_json_path):
        with open(eval_json_path, "r") as f:
            content = f.read()
            # Ensure no plain names or real identity numbers exist in keys or evaluation results
            assert "NAVNEET NEGI" not in content
            assert "RASHI GUPTA" not in content
            assert "PRINCE MAHTO" not in content


def test_14_no_raw_images_in_git_tracked_files():
    """14. Git does not track any raw evaluation or mutation images."""
    result = subprocess.run(
        ["git", "ls-files", "data/evaluation_input/", "data/reference/", "data/mutations/"],
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", f"Found git-tracked evaluation images: {result.stdout}"
