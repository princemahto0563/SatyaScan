"""
SatyaScan Forensic PDF Report API Endpoints
Generates and downloads official ReportLab forensic screening PDF reports.
Protected by JWT authentication and path traversal safeguards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import re

from backend.app.models.database import (
    get_db, Screening, ExtractedField, ValidationFinding,
    TamperFinding, FaceResult, AuditEvent, User, BlockchainAnchor
)
from backend.app.core.config import settings
from backend.app.core.security import get_current_user, sanitize_filename
from backend.app.core.permissions import check_checkpoint_access
from backend.app.core.rate_limiter import rate_limit_reports
from backend.app.services.report_generator import ReportGenerator
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/reports", tags=["Reports"])

SCREENING_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_screening_id(screening_id: str) -> str:
    clean_id = screening_id.strip()
    if not SCREENING_ID_REGEX.match(clean_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid screening identifier format.")
    return clean_id


@router.get("/{screening_id}/pdf", dependencies=[Depends(rate_limit_reports)])
@router.get("/{screening_id}/download", dependencies=[Depends(rate_limit_reports)])
def download_screening_pdf(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates and downloads official ReportLab forensic screening PDF report.
    Requires authenticated officer session and checkpoint access authorization.
    Rate-limited against CPU resource exhaustion.
    """
    clean_id = validate_screening_id(screening_id)
    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found")

    # Enforce checkpoint isolation policy
    check_checkpoint_access(current_user, screening, db, resource_type="pdf_report")

    fields = db.query(ExtractedField).filter(ExtractedField.screening_id == clean_id).all()
    val_findings = db.query(ValidationFinding).filter(ValidationFinding.screening_id == clean_id).all()
    tamper_findings = db.query(TamperFinding).filter(TamperFinding.screening_id == clean_id).all()
    face_res = db.query(FaceResult).filter(FaceResult.screening_id == clean_id).first()
    audit_events = db.query(AuditEvent).filter(AuditEvent.screening_id == clean_id).order_by(AuditEvent.id.asc()).all()
    anchor = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == clean_id).first()
    anchor_dict = None
    if anchor:
        anchor_dict = {
            "document_hash": anchor.document_hash,
            "result_hash": anchor.result_hash,
            "transaction_id": anchor.transaction_id,
            "network": anchor.network,
            "channel": anchor.channel,
            "chaincode": anchor.chaincode,
            "status": anchor.status,
            "verification_message": anchor.verification_message
        }

    # Reconstruct data dictionary for ReportLab
    case_payload = {
        "id": screening.id,
        "created_at": str(screening.created_at),
        "blockchain_anchor": anchor_dict,
        "checkpoint_id": screening.checkpoint_id,
        "checkpoint_name": screening.checkpoint_name,
        "operator_name": screening.operator.full_name if screening.operator else "Authorized Screening Officer",
        "operator_badge": screening.operator.badge_number if screening.operator else None,
        "document_type": screening.document_type,
        "masked_document_id": screening.masked_document_id,
        "status": screening.status,
        "risk_score": screening.risk_score,
        "risk_band": screening.risk_band,
        "recommendation": screening.recommendation,
        "extracted_fields": [
            {
                "field_name": f.field_name,
                "visual_value": f.visual_value,
                "mrz_value": f.mrz_value,
                "confidence": f.confidence,
                "match_status": f.match_status
            }
            for f in fields
        ],
        "tamper_summary": {
            "composite_tamper_score": max([t.score for t in tamper_findings], default=0.0),
            "signals": {
                "ela": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "ELA"], default=0.0)},
                "noise_residual": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "NOISE_RESIDUAL"], default=0.0)},
                "copy_move": {"anomaly_score": max([t.score for t in tamper_findings if t.technique == "COPY_MOVE"], default=0.0)}
            }
        },
        "face_result": {
            "metric": face_res.metric if face_res else "Cosine Similarity",
            "similarity_score": face_res.similarity_score if face_res else 0.0,
            "threshold": face_res.threshold if face_res else 0.65,
            "verification_result": face_res.verification_result if face_res else "NOT_RUN",
            "recommendation": face_res.recommendation if face_res else "No live selfie provided"
        } if face_res else None,
        "risk_reasons": [
            {
                "category": v.category,
                "severity": v.severity,
                "summary": v.message,
                "action": "Manual review"
            }
            for v in val_findings
        ],
        "audit_trail": [
            {"event_hash": a.event_hash} for a in audit_events
        ]
    }

    safe_filename = sanitize_filename(f"SatyaScan_Case_{clean_id}.pdf")
    pdf_path = os.path.join(settings.REPORT_DIR, safe_filename)

    # Validate output path is inside REPORT_DIR
    real_pdf_path = os.path.realpath(pdf_path)
    real_report_dir = os.path.realpath(settings.REPORT_DIR)
    if not real_pdf_path.startswith(real_report_dir):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid destination path.")

    ReportGenerator.generate_pdf(case_payload, pdf_path)

    # Record Audit Event for report generation with authenticated officer attribution
    AuditService.record_event(
        db, clean_id, "REPORT_GENERATED",
        {
            "report_format": "PDF",
            "file": safe_filename,
            "requested_by": current_user.username
        },
        actor=f"{current_user.role}_{current_user.badge_number}"
    )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=safe_filename
    )
