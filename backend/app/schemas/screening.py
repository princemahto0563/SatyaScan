"""
SatyaScan Pydantic Schemas
Defines request and response schemas for all API endpoints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# --- Auth Schemas ---

class UserLogin(BaseModel):
    username: str
    password: str
    checkpoint_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    full_name: str
    badge_number: str
    checkpoint_id: Optional[str] = None
    checkpoint_name: Optional[str] = None
    user: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    full_name: str
    badge_number: str
    checkpoint_id: Optional[str] = None
    checkpoint_name: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CheckpointResponse(BaseModel):
    id: str
    code: str
    name: str
    location: str
    username: str
    role: str = "OFFICER"
    is_active: bool = True

    class Config:
        from_attributes = True


# --- Screening Component Schemas ---

class ExtractedFieldSchema(BaseModel):
    field_name: str
    field_value: Optional[str] = None
    visual_value: Optional[str] = None
    mrz_value: Optional[str] = None
    confidence: Optional[float] = None
    ocr_engine: Optional[str] = None
    validation: Optional[str] = "VALID"
    match_status: str
    bounding_box: Optional[List[List[int]]] = None


class ValidationFindingSchema(BaseModel):
    rule_id: str
    category: str = "STANDARDS_COMPLIANCE"
    severity: str
    field: Optional[str] = None
    expected: Optional[str] = None
    observed: Optional[str] = None
    message: str
    classification: str = "OFFICIAL_STANDARD"


class TamperFindingSchema(BaseModel):
    technique: str
    severity: str
    score: float
    summary: str
    observation: Optional[str] = None
    interpretation: Optional[str] = None


class FaceResultSchema(BaseModel):
    metric: str = "Cosine Similarity"
    similarity_score: float
    threshold: float = 0.65
    verification_result: str
    appearance_level: str = "MINIMAL"
    observations: List[str] = []
    recommendation: Optional[str] = None
    provider: Optional[str] = "SFace-ResNet-128d-v1.0"
    quality_status: Optional[str] = None
    quality_reasons: List[str] = []
    pad_status: Optional[str] = "NOT_AVAILABLE"
    pad_reason: Optional[str] = None
    doc_face_crop_url: Optional[str] = None
    live_face_crop_url: Optional[str] = None
    disclaimer: str = "Similarity score is a model-derived metric, not a probability."


class BiometricQualitySchema(BaseModel):
    status: str = "GOOD"
    reasons: List[str] = []
    face_count: int = 1
    sharpness: Optional[float] = None
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    face_size_ratio: Optional[float] = None


class BiometricPADSchema(BaseModel):
    status: str = "NOT_AVAILABLE"
    reason: str = "Presentation-attack detection is not enabled in this prototype."


class BiometricVerificationSchema(BaseModel):
    status: str
    provider: str
    similarity: float
    threshold: float
    quality: BiometricQualitySchema
    presentation_attack: BiometricPADSchema
    appearance_variation: str = "MINIMAL"
    explanation: str
    disclaimer: str = "Biometric similarity is a model-derived metric, not a certified identity probability."


class IdentityMatchSchema(BaseModel):
    matched_document_id: str
    matched_name: str
    similarity: float
    alert_message: str


class AuditEventSchema(BaseModel):
    id: int
    timestamp: datetime
    actor: str
    event_type: str
    payload_hash: str
    previous_hash: str
    event_hash: str

    class Config:
        from_attributes = True


class AuditVerificationResult(BaseModel):
    screening_id: str
    is_valid: bool
    total_events: int
    genesis_hash: str
    head_hash: str
    verified_at: datetime
    status_message: str


# --- Reference Comparison & Discrepancy Schemas ---

class FieldDiffItemSchema(BaseModel):
    field: str
    reference_value: str
    observed_value: str
    status: str
    severity: str
    rationale: str


class FieldComparisonSummarySchema(BaseModel):
    document_type: str
    total_compared_fields: int
    matched_fields: int
    mismatched_fields: int
    unknown_fields: int
    identity_critical_mismatches: int
    document_control_mismatches: int
    consistency_label: str
    overall_severity: str
    severity_note: str
    diffs: List[FieldDiffItemSchema]


class ReferenceBaselineInfoSchema(BaseModel):
    reference_id: str
    document_type: str
    reference_hash: str
    observed_hash: str


class LinkageResultSchema(BaseModel):
    overall_linkage_status: str
    passport_number_linked: bool
    fields_compared: int
    matched_fields: int
    mismatched_fields: int
    unknown_fields: int
    biometric_linkage_status: str
    biometric_similarity: Optional[float] = None
    officer_summary: str
    field_results: List[Dict[str, Any]]


# --- Screening Response Schemas ---

class ScreeningSummaryResponse(BaseModel):
    id: str
    screening_id: Optional[str] = None
    created_at: datetime
    checkpoint_id: Optional[str] = None
    checkpoint_name: Optional[str] = None
    document_type: str
    masked_document_id: str
    status: str
    risk_score: float
    risk_band: str
    recommendation: Optional[str] = None
    ocr_engine: Optional[str] = None
    execution_latency_ms: float

    class Config:
        from_attributes = True


class ScreeningDetailResponse(BaseModel):
    id: str
    screening_id: Optional[str] = None
    created_at: datetime
    checkpoint_id: Optional[str] = None
    checkpoint_name: Optional[str] = None
    document_type: str
    masked_document_id: str
    status: str
    risk_score: float
    risk_band: str
    recommendation: Optional[str] = None
    ocr_engine: Optional[str] = None
    execution_latency_ms: float
    doc_image_url: Optional[str] = None
    live_image_url: Optional[str] = None
    doc_face_url: Optional[str] = None
    live_face_url: Optional[str] = None
    ela_heatmap_url: Optional[str] = None

    quality_assessment: Dict[str, Any]
    extracted_fields: List[ExtractedFieldSchema]
    mrz_data: Optional[Dict[str, Any]] = None
    validation_findings: List[ValidationFindingSchema]
    tamper_findings: List[TamperFindingSchema]
    tamper_summary: Dict[str, Any]
    face_result: Optional[FaceResultSchema] = None
    biometric_verification: Optional[BiometricVerificationSchema] = None
    identity_matches: List[IdentityMatchSchema]
    risk_reasons: List[Dict[str, Any]]
    signal_breakdown: Dict[str, float]
    audit_trail: List[AuditEventSchema]
    blockchain_anchor: Optional[Dict[str, Any]] = None

    page_type: Optional[str] = None
    is_identity_page: Optional[bool] = None
    identity_page_detected: Optional[bool] = None
    identity_page_message: Optional[str] = None
    mrz_status: Optional[str] = None
    ocr_status: Optional[str] = None
    ocr_reason: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "allow"


class UnsupportedDocumentResponse(BaseModel):
    status: str = "UNSUPPORTED_DOCUMENT"
    message: str = "Unsupported document type. SatyaScan currently supports Passport and Visa only. Please upload a valid Passport or Visa."
    supported_types: List[str] = ["PASSPORT", "VISA"]
    detected_type: Optional[str] = None
    indicators: Optional[List[str]] = None


class InconclusiveDocumentResponse(BaseModel):
    status: str = "UNABLE_TO_VERIFY"
    message: str = "The submitted document could not be reliably verified. Please provide a clearer image of a valid Passport or Visa."
    supported_types: List[str] = ["PASSPORT", "VISA"]


# --- Watchlist Schemas ---

class WatchlistEntryCreate(BaseModel):
    document_id: str
    full_name: str
    nationality: str = "IND"
    reason: str
    risk_category: str = "STOLEN_PASSPORT"
    status: str = "ACTIVE"


class WatchlistEntryResponse(BaseModel):
    id: int
    document_id: str
    full_name: str
    nationality: str
    reason: str
    risk_category: str
    status: str
    classification: str
    created_at: datetime

    class Config:
        from_attributes = True
