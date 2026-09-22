/**
 * SatyaScan TypeScript Data Models
 */

export interface ExtractedField {
  field_name: string;
  visual_value: string | null;
  mrz_value: string | null;
  confidence: number;
  match_status: "MATCH" | "MISMATCH" | "NOT_PRESENT";
  bounding_box?: number[][];
}

export interface ValidationFinding {
  rule_id: string;
  category: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  field?: string;
  expected?: string;
  observed?: string;
  message: string;
  classification: "OFFICIAL_STANDARD" | "PROTOTYPE_RULE";
}

export interface TamperFinding {
  technique: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  score: number;
  summary: string;
  observation?: string;
  interpretation?: string;
}

export interface FaceResult {
  metric: string;
  similarity_score: number;
  threshold: number;
  verification_result: "MATCH" | "BORDERLINE" | "MISMATCH" | "UNABLE_TO_VERIFY";
  appearance_level: "MINIMAL" | "MODERATE" | "SIGNIFICANT";
  observations: string[];
  recommendation?: string;
  provider?: string;
  quality_status?: string;
  quality_reasons?: string[];
  pad_status?: string;
  pad_reason?: string;
  disclaimer: string;
}

export interface BiometricVerification {
  status: "MATCH" | "BORDERLINE" | "MISMATCH" | "UNABLE_TO_VERIFY";
  provider: string;
  similarity: number;
  threshold: number;
  quality: {
    status: "GOOD" | "ACCEPTABLE" | "POOR" | "UNABLE_TO_VERIFY";
    reasons: string[];
    face_count?: number;
    sharpness?: number;
    brightness?: number;
    contrast?: number;
    face_size_ratio?: number;
  };
  presentation_attack: {
    status: "PASS" | "REVIEW" | "FAIL" | "NOT_AVAILABLE";
    reason: string;
  };
  appearance_variation: "MINIMAL" | "MODERATE" | "SIGNIFICANT";
  explanation: string;
  disclaimer: string;
}

export interface IdentityMatch {
  matched_document_id: string;
  matched_name: string;
  similarity: number;
  alert_message: string;
}

export interface AuditEvent {
  id: number;
  timestamp: string;
  actor: string;
  event_type: string;
  payload_hash: string;
  previous_hash: string;
  event_hash: string;
}

export interface ScreeningDetail {
  id: string;
  created_at: string;
  checkpoint_id?: string;
  checkpoint_name?: string;
  document_type: string;
  masked_document_id: string;
  status: string;
  risk_score: number;
  risk_band: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  recommendation?: string;
  execution_latency_ms: number;
  doc_image_url?: string;
  live_image_url?: string;
  ela_heatmap_url?: string;

  quality_assessment: {
    verdict: "GOOD" | "NEEDS_BETTER_IMAGE";
    overall_score: number;
    reasons: string[];
    metrics?: {
      blur_score: number;
      glare_percentage: number;
      contrast_score: number;
      brightness_score: number;
      resolution?: { width: number; height: number };
    };
  };

  extracted_fields: ExtractedField[];
  mrz_data?: {
    parsed: boolean;
    document_number?: string;
    full_name?: string;
    nationality?: string;
    date_of_birth?: string;
    date_of_expiry?: string;
    all_checks_passed: boolean;
    check_digits?: Record<string, { observed: string; expected: string; valid: boolean }>;
  };
  validation_findings: ValidationFinding[];
  tamper_findings: TamperFinding[];
  tamper_summary: {
    composite_tamper_score: number;
    findings_count: number;
    signals?: {
      ela?: { anomaly_score: number; observation: string; interpretation: string };
      noise_residual?: { anomaly_score: number; observation: string; interpretation: string };
      copy_move?: { anomaly_score: number; matches_found: number; observation: string };
      edge_analysis?: { anomaly_score: number; boundary_jump_ratio: number };
      metadata?: { anomaly_score: number; software_signature?: string };
    };
  };
  face_result?: FaceResult | null;
  biometric_verification?: BiometricVerification | null;
  identity_matches: IdentityMatch[];
  risk_reasons: Array<{
    category: string;
    severity: string;
    summary: string;
    detail: string;
    action: string;
  }>;
  signal_breakdown: Record<string, number>;
  audit_trail: AuditEvent[];
  blockchain_anchor?: BlockchainAnchor | null;
  reference_comparison?: FieldComparisonSummary | null;
  reference_baseline?: ReferenceBaselineInfo | null;
  passport_visa_linkage?: LinkageResult | null;
}

export interface FieldDiffItem {
  field: string;
  reference_value: string;
  observed_value: string;
  status: "MATCH" | "MISMATCH" | "UNKNOWN";
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  rationale: string;
}

export interface FieldComparisonSummary {
  document_type: string;
  total_compared_fields: number;
  matched_fields: number;
  mismatched_fields: number;
  unknown_fields: number;
  identity_critical_mismatches: number;
  document_control_mismatches: number;
  consistency_label: string;
  overall_severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  severity_note: string;
  diffs: FieldDiffItem[];
}

export interface ReferenceBaselineInfo {
  reference_id: string;
  document_type: string;
  reference_hash: string;
  observed_hash: string;
}

export interface LinkageFieldResult {
  field: string;
  label: string;
  passport_value: string;
  visa_value: string;
  status: "MATCH" | "MISMATCH" | "UNKNOWN";
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
}

export interface LinkageResult {
  overall_linkage_status: "MATCH" | "PARTIAL_MATCH" | "MISMATCH" | "UNABLE_TO_VERIFY";
  passport_number_linked: boolean;
  fields_compared: number;
  matched_fields: number;
  mismatched_fields: number;
  unknown_fields: number;
  biometric_linkage_status: string;
  biometric_similarity?: number | null;
  officer_summary: string;
  field_results: LinkageFieldResult[];
}

export interface BlockchainAnchor {
  id?: number;
  screening_id: string;
  document_hash: string;
  result_hash: string;
  transaction_id?: string | null;
  ledger_asset_id?: string | null;
  anchor_timestamp?: string | null;
  network: string;
  channel: string;
  chaincode: string;
  status: "PENDING" | "VERIFIED" | "UNAVAILABLE" | "FAILED" | "MISMATCH";
  verification_timestamp?: string | null;
  verification_message?: string | null;
  created_at?: string | null;
}

export interface BlockchainVerificationResponse {
  screening_id: string;
  is_verified: boolean;
  status: "VERIFIED" | "MISMATCH" | "UNAVAILABLE" | "FAILED";
  document_hash: string;
  result_hash: string;
  document_hash_matches: boolean;
  result_hash_matches: boolean;
  network: string;
  channel: string;
  chaincode: string;
  transaction_id?: string | null;
  ledger_asset_id?: string | null;
  anchor_timestamp?: string | null;
  verification_timestamp: string;
  status_message: string;
  privacy_compliance: string;
  on_chain_record?: Record<string, any> | null;
}

export interface CheckpointInfo {
  id: string;
  code: string;
  name: string;
  location: string;
  username: string;
  role: string;
  is_active: boolean;
}

export interface UserSession {
  id?: number;
  username: string;
  full_name: string;
  badge_number: string;
  role: string;
  checkpoint_id?: string | null;
  checkpoint_name?: string | null;
  location?: string | null;
  access_token: string;
}

export interface ScreeningSummary {
  id: string;
  created_at: string;
  checkpoint_id?: string;
  checkpoint_name?: string;
  document_type: string;
  masked_document_id: string;
  status: string;
  risk_score: number;
  risk_band: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  recommendation?: string;
  execution_latency_ms: number;
}
