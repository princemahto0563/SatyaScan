"""
SatyaScan Forensic PDF Report API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from backend.app.models.database import (
    get_db, Screening, ExtractedField, ValidationFinding,
    TamperFinding, FaceResult, AuditEvent
)
from backend.app.core.config import settings
from backend.app.services.report_generator import ReportGenerator
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{screening_id}/pdf")
@router.get("/{screening_id}/download")
def download_screening_pdf(screening_id: str, db: Session = Depends(get_db)):
    """
    Generates and downloads official ReportLab forensic screening PDF report.
    """
    screening = db.query(Screening).filter(Screening.id == screening_id).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Screening record not found")

    fields = db.query(ExtractedField).filter(ExtractedField.screening_id == screening_id).all()
    val_findings = db.query(ValidationFinding).filter(ValidationFinding.screening_id == screening_id).all()
    tamper_findings = db.query(TamperFinding).filter(TamperFinding.screening_id == screening_id).all()
    face_res = db.query(FaceResult).filter(FaceResult.screening_id == screening_id).first()
    audit_events = db.query(AuditEvent).filter(AuditEvent.screening_id == screening_id).order_by(AuditEvent.id.asc()).all()

    # Reconstruct data dictionary for ReportLab
    case_payload = {
        "id": screening.id,
        "created_at": str(screening.created_at),
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

    pdf_filename = f"SatyaScan_Case_{screening_id}.pdf"
    pdf_path = os.path.join(settings.REPORT_DIR, pdf_filename)

    ReportGenerator.generate_pdf(case_payload, pdf_path)

    # Record Audit Event for report generation
    AuditService.record_event(
        db, screening_id, "REPORT_GENERATED",
        {"report_format": "PDF", "file": pdf_filename}
    )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_filename
    )
