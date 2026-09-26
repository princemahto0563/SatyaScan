import assert from "node:assert/strict";
import { mapScreeningResponseToReportViewModel, normalizeDateForComparison } from "./adapter";
import { ScreeningDetail } from "./types";

function createBaseScreening(id: string): ScreeningDetail {
  return {
    id,
    screening_id: id,
    created_at: "2026-09-24T12:00:00Z",
    status: "COMPLETED",
    checkpoint_id: "CP-DEL-AIR",
    checkpoint_name: "Delhi Airport Checkpoint",
    document_type: "PASSPORT",
    masked_document_id: "Z12***67",
    risk_score: 12.0,
    risk_band: "LOW",
    recommendation: "Routine Clearance Permitted.",
    execution_latency_ms: 1200,
    ocr_engine: "Tesseract",
    ocr_status: "SUCCESS",
    doc_image_url: `/api/v1/screenings/media/${id}/doc`,
    live_image_url: `/api/v1/screenings/media/${id}/live`,
    ela_heatmap_url: `/api/v1/screenings/media/${id}/heatmap`,
    doc_face_url: `/api/v1/screenings/media/${id}/doc_face`,
    live_face_url: `/api/v1/screenings/media/${id}/live_face`,
    quality_assessment: {
      verdict: "GOOD",
      status_message: "High quality image",
      overall_score: 90,
      is_acceptable: true,
      reasons: [],
      metrics: {
        blur_score: 5000,
        glare_percentage: 2,
        contrast_score: 80,
        brightness_score: 180,
        resolution: { width: 1000, height: 700 },
        resolution_adequate: true,
      },
      gate_version: "1.0",
    },
    extracted_fields: [
      {
        field_name: "document_number",
        field_value: "Z1234567",
        visual_value: "Z1234567",
        mrz_value: "Z1234567",
        confidence: 0.98,
        match_status: "MATCH",
      },
      {
        field_name: "full_name",
        field_value: "ARJUN SHARMA",
        visual_value: "ARJUN SHARMA",
        mrz_value: "ARJUN SHARMA",
        confidence: 0.95,
        match_status: "MATCH",
      },
      {
        field_name: "nationality",
        field_value: "INDIAN",
        visual_value: "INDIAN",
        mrz_value: "IND",
        confidence: 0.95,
        match_status: "MATCH",
      },
      {
        field_name: "date_of_birth",
        field_value: "14/05/1992",
        visual_value: "14/05/1992",
        mrz_value: "1992-05-14",
        confidence: 0.96,
        match_status: "MATCH",
      },
      {
        field_name: "date_of_expiry",
        field_value: "13/05/2028",
        visual_value: "13/05/2028",
        mrz_value: "2028-05-13",
        confidence: 0.97,
        match_status: "MATCH",
      },
      {
        field_name: "sex",
        field_value: "MALE",
        visual_value: "MALE",
        mrz_value: "MALE",
        confidence: 0.99,
        match_status: "MATCH",
      },
    ],
    mrz_data: {
      parsed: true,
      document_code: "P",
      issuing_country: "IND",
      full_name: "ARJUN SHARMA",
      surname: "SHARMA",
      given_names: "ARJUN",
      document_number: "Z1234567",
      nationality: "IND",
      date_of_birth: "1992-05-14",
      raw_date_of_birth: "920514",
      sex: "MALE",
      date_of_expiry: "2028-05-13",
      raw_date_of_expiry: "280513",
      is_expired: false,
      raw_lines: [
        "P<INDSHARMA<<ARJUN<<<<<<<<<<<<<<<<<<<<<<<<<<",
        "Z1234567<1IND9205141M2805139<<<<<<<<<<<<<<<2",
      ],
      check_digits: {
        document_number: { observed: "1", expected: "1", valid: true },
        date_of_birth: { observed: "1", expected: "1", valid: true },
        date_of_expiry: { observed: "9", expected: "9", valid: true },
        composite: { observed: "2", expected: "2", valid: true },
      },
      all_checks_passed: true,
      status_message: "All ICAO Doc 9303 check digits verified.",
    },
    validation_findings: [],
    tamper_findings: [
      {
        technique: "ELA",
        severity: "LOW",
        score: 12.0,
        summary: "Normal compression",
        observation: "Uniform error level residual",
        interpretation: "No anomaly detected",
      },
    ],
    tamper_summary: {
      pipeline_version: "v1.0",
      composite_tamper_score: 12.0,
      verdict: "NO_TAMPERING_DETECTED",
      recommendation: "Pass",
      findings_count: 1,
      findings: [],
      signals: {
        ela: {
          technique: "ELA",
          anomaly_score: 12.0,
          observation: "Uniform",
          interpretation: "Uniform",
        },
        noise_residual: {
          technique: "Noise",
          anomaly_score: 15.0,
          observation: "Homogeneous",
          interpretation: "Homogeneous",
        },
        copy_move: {
          technique: "CopyMove",
          anomaly_score: 0.0,
          matches_found: 0,
        },
      },
    },
    face_result: {
      metric: "Cosine",
      similarity_score: 0.92,
      threshold: 0.68,
      verification_result: "VERIFIED MATCH",
      decision_state: "VERIFIED MATCH",
      appearance_level: "MINIMAL",
      observations: [],
      recommendation: "Biometric correspondence verified.",
      provider: "SFace-ResNet-128d-v1.0",
      quality_status: "GOOD",
      pad_status: "NOT_AVAILABLE",
      doc_face_crop_url: `/api/v1/screenings/media/${id}/doc_face`,
      live_face_crop_url: `/api/v1/screenings/media/${id}/live_face`,
    },
    risk_reasons: [],
    audit_trail: [
      {
        id: 1,
        timestamp: "2026-09-24T12:00:00Z",
        actor: "SYSTEM",
        event_type: "SCREENING_INITIATED",
        payload_hash: "hash0",
        event_hash: "genesis_hash",
      },
      {
        id: 2,
        timestamp: "2026-09-24T12:00:02Z",
        actor: "SYSTEM",
        event_type: "SCREENING_COMPLETED",
        payload_hash: "hash1",
        event_hash: "head_hash",
      },
    ],
  };
}

console.log("Starting Frontend Adapter Unit Tests (Phase K)...");

// Test 1: Complete valid passport response
{
  const data = createBaseScreening("SAT-001");
  const model = mapScreeningResponseToReportViewModel(data, "mock-jwt");

  assert.equal(model.screeningId, "SAT-001");
  assert.equal(model.document.type, "PASSPORT");
  assert.equal(model.document.fullName, "ARJUN SHARMA");
  assert.equal(model.document.number, "Z1234567");
  assert.equal(model.document.dob, "1992-05-14"); // Prioritized valid MRZ date
  assert.equal(model.document.nationality, "IND");
  assert.equal(model.document.expiry, "2028-05-13");
  assert.equal(model.document.sex, "MALE");
  assert.equal(model.document.ocrStatus, "SUCCESS");
  assert.ok(model.pdfDownloadUrl.includes("token=mock-jwt"));
  console.log("✓ Test 1: Complete valid passport response PASS");
}

// Test 2: Complete valid visa response
{
  const data = createBaseScreening("SAT-002");
  data.document_type = "VISA";
  data.mrz_data = null;
  const model = mapScreeningResponseToReportViewModel(data, "mock-jwt");

  assert.equal(model.document.type, "VISA");
  assert.equal(model.mrz.applicable, false);
  assert.equal(model.mrz.statusBadge, "NOT APPLICABLE");
  console.log("✓ Test 2: Complete valid visa response PASS");
}

// Test 3: Valid MRZ
{
  const data = createBaseScreening("SAT-003");
  const model = mapScreeningResponseToReportViewModel(data);

  assert.equal(model.mrz.applicable, true);
  assert.equal(model.mrz.parsed, true);
  assert.equal(model.mrz.allChecksPassed, true);
  assert.equal(model.mrz.statusBadge, "7-3-1 PASS");
  assert.ok(model.mrz.checkDigits["document_number"].valid);
  console.log("✓ Test 3: Valid MRZ PASS");
}

// Test 4: No MRZ / MRZ not applicable / unparsed
{
  const data = createBaseScreening("SAT-004");
  data.mrz_data = { parsed: false, status_message: "No MRZ found" };
  const model = mapScreeningResponseToReportViewModel(data);

  assert.equal(model.mrz.parsed, false);
  assert.equal(model.mrz.statusBadge, "UNPARSED");
  console.log("✓ Test 4: No MRZ / MRZ unparsed PASS");
}

// Test 5: VIZ = MRZ match (including date format normalization DD/MM/YYYY vs YYYY-MM-DD)
{
  const data = createBaseScreening("SAT-005");
  const model = mapScreeningResponseToReportViewModel(data);

  // Document Number match
  const docNumRow = model.crossCheckRows.find((r) => r.fieldName === "document_number");
  assert.ok(docNumRow);
  assert.equal(docNumRow.status, "MATCH");
  assert.equal(docNumRow.statusLabel, "Match");

  // Date of Birth match (VIZ: 14/05/1992 vs MRZ: 1992-05-14)
  const dobRow = model.crossCheckRows.find((r) => r.fieldName === "date_of_birth");
  assert.ok(dobRow);
  assert.equal(dobRow.status, "MATCH");
  assert.equal(dobRow.statusLabel, "Match");
  assert.equal(dobRow.visualValue, "14/05/1992");
  assert.equal(dobRow.mrzValue, "1992-05-14");

  // Date of Expiry match (VIZ: 13/05/2028 vs MRZ: 2028-05-13)
  const expiryRow = model.crossCheckRows.find((r) => r.fieldName === "date_of_expiry");
  assert.ok(expiryRow);
  assert.equal(expiryRow.status, "MATCH");
  assert.equal(expiryRow.statusLabel, "Match");
  assert.equal(expiryRow.visualValue, "13/05/2028");
  assert.equal(expiryRow.mrzValue, "2028-05-13");

  console.log("✓ Test 5: VIZ = MRZ match (including 14/05/1992 = 1992-05-14 and 13/05/2028 = 2028-05-13) PASS");
}

// Test 6: VIZ/MRZ mismatch (document number altered and actual calendar date mismatch 14/05/1992 vs 1992-05-15)
{
  const data = createBaseScreening("SAT-006");
  const docNumField = data.extracted_fields.find((f) => f.field_name === "document_number");
  if (docNumField) docNumField.visual_value = "A9999999"; // Alter visual value

  // Alter visual date of birth to 14/05/1992 while MRZ is 1992-05-15 (differing day)
  const dobField = data.extracted_fields.find((f) => f.field_name === "date_of_birth");
  if (dobField) dobField.visual_value = "14/05/1992";
  if (data.mrz_data) data.mrz_data.date_of_birth = "1992-05-15";

  const model = mapScreeningResponseToReportViewModel(data);

  const docNumRow = model.crossCheckRows.find((r) => r.fieldName === "document_number");
  assert.ok(docNumRow);
  assert.equal(docNumRow.status, "MISMATCH");
  assert.equal(docNumRow.statusLabel, "Discrepancy");

  const dobRow = model.crossCheckRows.find((r) => r.fieldName === "date_of_birth");
  assert.ok(dobRow);
  assert.equal(dobRow.status, "MISMATCH");
  assert.equal(dobRow.statusLabel, "Discrepancy");
  assert.equal(dobRow.visualValue, "14/05/1992");
  assert.equal(dobRow.mrzValue, "1992-05-15");

  console.log("✓ Test 6: VIZ/MRZ mismatch (including 14/05/1992 vs 1992-05-15 => MISMATCH) PASS");
}

// Test 7: Missing optional fields (Truthful unavailable state, NO fake defaults)
{
  const data = createBaseScreening("SAT-007");
  data.extracted_fields = [];
  data.mrz_data = null;
  data.masked_document_id = "M12***99";

  const model = mapScreeningResponseToReportViewModel(data);
  assert.equal(model.document.fullName, "Not available");
  assert.equal(model.document.nationality, "Not available");
  assert.equal(model.document.sex, "Not available");
  assert.equal(model.document.number, "M12***99 (Masked)");
  console.log("✓ Test 7: Missing optional fields truthful handling PASS");
}

// Test 8: Face MATCH
{
  const data = createBaseScreening("SAT-008");
  data.face_result = {
    similarity_score: 0.88,
    threshold: 0.68,
    verification_result: "VERIFIED MATCH",
    decision_state: "VERIFIED MATCH",
    provider: "SFace-ResNet-128d-v1.0",
  };
  const model = mapScreeningResponseToReportViewModel(data);
  assert.equal(model.face.result, "VERIFIED MATCH");
  assert.equal(model.face.decisionState, "VERIFIED MATCH");
  assert.equal(model.face.similarity, 0.88);
  console.log("✓ Test 8: Face MATCH PASS");
}

// Test 9: Face MISMATCH
{
  const data = createBaseScreening("SAT-009");
  data.face_result = {
    similarity_score: 0.35,
    threshold: 0.68,
    verification_result: "VERIFIED MISMATCH",
    decision_state: "VERIFIED MISMATCH",
    provider: "SFace-ResNet-128d-v1.0",
  };
  const model = mapScreeningResponseToReportViewModel(data);
  assert.equal(model.face.result, "VERIFIED MISMATCH");
  assert.equal(model.face.decisionState, "VERIFIED MISMATCH");
  assert.equal(model.face.similarity, 0.35);
  console.log("✓ Test 9: Face MISMATCH PASS");
}

// Test 10: Missing image asset handling
{
  const data = createBaseScreening("SAT-010");
  data.doc_face_url = undefined;
  data.live_face_url = undefined;
  data.ela_heatmap_url = undefined;
  data.face_result = undefined;
  data.live_image_url = undefined;

  const model = mapScreeningResponseToReportViewModel(data);
  assert.equal(model.face.result, "NO LIVE CAPTURE");
  assert.equal(model.face.presentedFaceUrl, null);
  assert.ok(model.face.documentPortraitUrl); // fallback asset URL constructed safely
  console.log("✓ Test 10: Missing image asset handling PASS");
}

// Test 11: Screening A vs Screening B isolation
{
  const dataA = createBaseScreening("SAT-AAA");
  dataA.extracted_fields = [
    { field_name: "full_name", visual_value: "ALICE WONDER", mrz_value: "ALICE WONDER", confidence: 0.9 },
  ];
  dataA.mrz_data = { parsed: true, full_name: "ALICE WONDER", all_checks_passed: true, check_digits: {} };

  const dataB = createBaseScreening("SAT-BBB");
  dataB.extracted_fields = [
    { field_name: "full_name", visual_value: "BOB BUILDER", mrz_value: "BOB BUILDER", confidence: 0.9 },
  ];
  dataB.mrz_data = { parsed: true, full_name: "BOB BUILDER", all_checks_passed: true, check_digits: {} };

  const modelA = mapScreeningResponseToReportViewModel(dataA);
  const modelB = mapScreeningResponseToReportViewModel(dataB);

  assert.equal(modelA.screeningId, "SAT-AAA");
  assert.equal(modelB.screeningId, "SAT-BBB");
  assert.equal(modelA.document.fullName, "ALICE WONDER");
  assert.equal(modelB.document.fullName, "BOB BUILDER");
  assert.notEqual(modelA.face.documentPortraitUrl, modelB.face.documentPortraitUrl);
  console.log("✓ Test 11: Screening A vs Screening B isolation PASS");
}

// Test 12: Canonical date normalization helper (DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, DD.MM.YYYY, invalid dates)
{
  // DD/MM/YYYY
  assert.equal(normalizeDateForComparison("14/05/1992"), "1992-05-14");
  assert.equal(normalizeDateForComparison("13/05/2028"), "2028-05-13");
  
  // YYYY-MM-DD
  assert.equal(normalizeDateForComparison("1992-05-14"), "1992-05-14");
  assert.equal(normalizeDateForComparison("2028-05-13"), "2028-05-13");

  // DD-MM-YYYY
  assert.equal(normalizeDateForComparison("14-05-1992"), "1992-05-14");

  // DD.MM.YYYY
  assert.equal(normalizeDateForComparison("14.05.1992"), "1992-05-14");

  // ICAO raw 6 digits YYMMDD
  assert.equal(normalizeDateForComparison("920514"), "1992-05-14");
  assert.equal(normalizeDateForComparison("280513"), "2028-05-13");

  // Invalid calendar dates -> null
  assert.equal(normalizeDateForComparison("31/02/1992"), null); // Feb 31 does not exist
  assert.equal(normalizeDateForComparison("14/13/1992"), null); // Month 13 invalid
  assert.equal(normalizeDateForComparison("32/05/1992"), null); // Day 32 invalid
  assert.equal(normalizeDateForComparison("not-a-date"), null);
  assert.equal(normalizeDateForComparison(""), null);
  assert.equal(normalizeDateForComparison("-"), null);
  assert.equal(normalizeDateForComparison(null), null);

  console.log("✓ Test 12: Canonical date normalization and invalid date rejection PASS");
}

// Test 13: Label noise suppression (MAT /NOM:, SURNAME, GIVEN NAMES are rejected as identity values)
{
  const data = createBaseScreening("SAT-013");
  data.extracted_fields = [
    { field_name: "full_name", visual_value: "MAT /NOM:", mrz_value: null, confidence: 0.8 },
    { field_name: "surname", visual_value: "SURNAME / NOM", mrz_value: null, confidence: 0.8 },
  ];
  data.mrz_data = null;
  const model = mapScreeningResponseToReportViewModel(data);

  assert.equal(model.document.fullName, "Not available");
  assert.equal(model.document.surname, "Not available");
  console.log("✓ Test 13: Label noise suppression PASS");
}

// Test 14: Equivalence matching in VIZ ↔ MRZ Cross-Check (INDIAN vs IND, PASSPORT vs P, MALE vs M)
{
  const data = createBaseScreening("SAT-014");
  data.extracted_fields = [
    { field_name: "nationality", visual_value: "INDIAN", mrz_value: "IND", confidence: 0.9 },
    { field_name: "document_type", visual_value: "PASSPORT", mrz_value: "P", confidence: 0.9 },
    { field_name: "sex", visual_value: "MALE", mrz_value: "M", confidence: 0.9 },
  ];
  const model = mapScreeningResponseToReportViewModel(data);

  const natRow = model.crossCheckRows.find(r => r.fieldName === "nationality");
  assert.ok(natRow);
  assert.equal(natRow.status, "MATCH");

  const docRow = model.crossCheckRows.find(r => r.fieldName === "document_type");
  assert.ok(docRow);
  assert.equal(docRow.status, "MATCH");

  const sexRow = model.crossCheckRows.find(r => r.fieldName === "sex");
  assert.ok(sexRow);
  assert.equal(sexRow.status, "MATCH");
  console.log("✓ Test 14: Equivalence matching in VIZ ↔ MRZ Cross-Check PASS");
}

// Test 15: Passport Cover detection and truthful MRZ / portrait state
{
  const data = createBaseScreening("SAT-015");
  data.document_type = "PASSPORT";
  (data as any).page_type = "PASSPORT_COVER";
  (data as any).is_identity_page = false;
  (data as any).identity_page_message = "Identity Page Not Detected — recapture required. Upload the passport biodata/identity page containing portrait and machine-readable information.";
  (data as any).mrz_status = "MRZ_INPUT_INSUFFICIENT";
  data.mrz_data = { parsed: false, status_message: "Identity Page Not Detected — recapture required" };
  data.extracted_fields = [
    { field_name: "document_type", visual_value: "PASSPORT", mrz_value: null, confidence: 0.9 },
    { field_name: "document_number", visual_value: "Z1234567", mrz_value: null, confidence: 0.8 },
  ];
  data.face_result.status = "INPUT_FAILURE";
  data.face_result.decision_state = "INPUT_FAILURE";
  data.face_result.match_score = 0.0;
  data.face_result.reason = "Usable identity portrait not detected in submitted document image.";

  const model = mapScreeningResponseToReportViewModel(data);

  assert.equal(model.document.pageType, "PASSPORT_COVER");
  assert.equal(model.document.isIdentityPage, false);
  assert.equal(model.mrz.statusBadge, "INPUT INSUFFICIENT");
  assert.equal(model.face.result, "INPUT FAILURE");
  
  // Cross check rows must show "Identity page required"
  const mrzDocNumRow = model.crossCheckRows.find(r => r.fieldName === "document_number");
  assert.ok(mrzDocNumRow);
  assert.equal(mrzDocNumRow.mrzValue, "Identity page required");
  assert.equal(mrzDocNumRow.status, "VIZ_ONLY");
  console.log("✓ Test 15: Passport Cover detection and truthful MRZ / portrait state PASS");
}

// Test 16: Visa without MRZ (MRZ_NOT_APPLICABLE)
{
  const data = createBaseScreening("SAT-016");
  data.document_type = "VISA";
  (data as any).page_type = "VISA_VIGNETTE";
  (data as any).is_identity_page = true;
  (data as any).mrz_status = "MRZ_NOT_APPLICABLE";
  data.mrz_data = { parsed: false, status_message: "MRZ Not Applicable for this document type" };
  data.extracted_fields = [
    { field_name: "document_type", visual_value: "VISA", mrz_value: null, confidence: 0.9 },
    { field_name: "document_number", visual_value: "V1234567", mrz_value: null, confidence: 0.8 },
  ];

  const model = mapScreeningResponseToReportViewModel(data);

  assert.equal(model.mrz.statusBadge, "NOT APPLICABLE");
  assert.equal(model.mrz.applicable, false);

  const mrzDocNumRow = model.crossCheckRows.find(r => r.fieldName === "document_number");
  assert.ok(mrzDocNumRow);
  assert.equal(mrzDocNumRow.mrzValue, "Not applicable");
  assert.equal(mrzDocNumRow.status, "NOT_APPLICABLE");
  console.log("✓ Test 16: Visa without MRZ (MRZ_NOT_APPLICABLE) PASS");
}

// Test 17: True Mismatches remain MISMATCH
{
  const data = createBaseScreening("SAT-017");
  data.extracted_fields = [
    { field_name: "full_name", visual_value: "JOHN DOE", mrz_value: "JANE SMITH", confidence: 0.9 },
    { field_name: "document_number", visual_value: "A1234567", mrz_value: "B9876543", confidence: 0.9 },
    { field_name: "date_of_birth", visual_value: "1990-01-01", mrz_value: "1995-05-05", confidence: 0.9 },
  ];
  const model = mapScreeningResponseToReportViewModel(data);

  const nameRow = model.crossCheckRows.find(r => r.fieldName === "full_name");
  assert.ok(nameRow);
  assert.equal(nameRow.status, "MISMATCH");

  const numRow = model.crossCheckRows.find(r => r.fieldName === "document_number");
  assert.ok(numRow);
  assert.equal(numRow.status, "MISMATCH");

  const dobRow = model.crossCheckRows.find(r => r.fieldName === "date_of_birth");
  assert.ok(dobRow);
  assert.equal(dobRow.status, "MISMATCH");
  console.log("✓ Test 17: True Mismatches remain MISMATCH PASS");
}

// Test 18: Regression test for VIZ/MRZ document number match and mismatch
{
  const matchScreening = createBaseScreening("SAT-018-MATCH");
  matchScreening.extracted_fields = [
    { field_name: "document_number", visual_value: "Z1234567", mrz_value: "Z1234567", confidence: 0.98 },
  ];
  const modelMatch = mapScreeningResponseToReportViewModel(matchScreening);
  const rowMatch = modelMatch.crossCheckRows.find(r => r.fieldName === "document_number");
  assert.ok(rowMatch);
  assert.equal(rowMatch.status, "MATCH");

  const mismatchScreening = createBaseScreening("SAT-018-MISMATCH");
  mismatchScreening.extracted_fields = [
    { field_name: "document_number", visual_value: "21234567", mrz_value: "Z1234567", confidence: 0.98 },
  ];
  const modelMismatch = mapScreeningResponseToReportViewModel(mismatchScreening);
  const rowMismatch = modelMismatch.crossCheckRows.find(r => r.fieldName === "document_number");
  assert.ok(rowMismatch);
  assert.equal(rowMismatch.status, "MISMATCH");

  console.log("✓ Test 18: Regression VIZ Z1234567 + MRZ Z1234567 => MATCH and 21234567 + Z1234567 => MISMATCH PASS");
}

console.log("\nALL 18 FRONTEND ADAPTER UNIT TESTS PASSED SUCCESSFULLY!");

