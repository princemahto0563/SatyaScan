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
