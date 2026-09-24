import assert from "node:assert/strict";
import { mapScreeningResponseToReportViewModel } from "./adapter";
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

// Test 5: VIZ = MRZ match
{
  const data = createBaseScreening("SAT-005");
  const model = mapScreeningResponseToReportViewModel(data);

  const docNumRow = model.crossCheckRows.find((r) => r.fieldName === "document_number");
  assert.ok(docNumRow);
  assert.equal(docNumRow.status, "MATCH");
  assert.equal(docNumRow.statusLabel, "Match");
  console.log("✓ Test 5: VIZ = MRZ match PASS");
}

// Test 6: VIZ/MRZ mismatch
{
  const data = createBaseScreening("SAT-006");
  const docNumField = data.extracted_fields.find((f) => f.field_name === "document_number");
  if (docNumField) docNumField.visual_value = "A9999999"; // Alter visual value

  const model = mapScreeningResponseToReportViewModel(data);
  const docNumRow = model.crossCheckRows.find((r) => r.fieldName === "document_number");
  assert.ok(docNumRow);
  assert.equal(docNumRow.status, "MISMATCH");
  assert.equal(docNumRow.statusLabel, "Discrepancy");
  console.log("✓ Test 6: VIZ/MRZ mismatch PASS");
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

console.log("\nALL 11 FRONTEND ADAPTER UNIT TESTS PASSED SUCCESSFULLY!");
