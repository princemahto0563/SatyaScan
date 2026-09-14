"""
SatyaScan Screening REST Endpoints
Handles document uploads, automated screening execution, media retrieval, and case inspection.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import json

from backend.app.models.database import (
    get_db, Screening, ExtractedField, ValidationFinding,
    TamperFinding, FaceResult, IdentityMatch, AuditEvent
)
from backend.app.schemas.screening import ScreeningDetailResponse, ScreeningSummaryResponse
from backend.app.core.config import settings
from backend.app.core.security import validate_uploaded_image_bytes
from backend.app.services.orchestrator import screening_orchestrator

router = APIRouter(prefix="/screenings", tags=["Screenings"])


@router.post("", response_model=ScreeningDetailResponse)
async def create_screening(
    document_file: UploadFile = File(...),
    live_selfie_file: Optional[UploadFile] = File(None),
    document_type: str = Form("PASSPORT"),
    db: Session = Depends(get_db)
):
    """
    Executes automated screening on uploaded travel document and optional live selfie.
    """
    # 1. Validate and save document file
    doc_bytes = await document_file.read()
    validate_uploaded_image_bytes(doc_bytes, document_file.filename)

    doc_ext = document_file.filename.split('.')[-1].lower() if '.' in document_file.filename else 'jpg'
    doc_filename = f"doc_{uuid.uuid4().hex}.{doc_ext}"
    doc_path = os.path.join(settings.UPLOAD_DIR, doc_filename)

    with open(doc_path, "wb") as f:
        f.write(doc_bytes)

    # 2. Validate and save live selfie if provided
    live_path = None
    if live_selfie_file and live_selfie_file.filename:
        live_bytes = await live_selfie_file.read()
        validate_uploaded_image_bytes(live_bytes, live_selfie_file.filename)
        live_ext = live_selfie_file.filename.split('.')[-1].lower() if '.' in live_selfie_file.filename else 'jpg'
        live_filename = f"live_{uuid.uuid4().hex}.{live_ext}"
        live_path = os.path.join(settings.UPLOAD_DIR, live_filename)
        with open(live_path, "wb") as f:
            f.write(live_bytes)

    # 3. Execute full screening pipeline
    result = screening_orchestrator.process_screening(
        db=db,
        doc_image_path=doc_path,
        live_image_path=live_path,
        doc_type=document_type
    )

    return result


@router.get("", response_model=List[ScreeningSummaryResponse])
def list_screenings(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """
    Lists recent screening records with pagination.
    """
    screenings = (
        db.query(Screening)
        .order_by(Screening.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return screenings


@router.get("/{screening_id}", response_model=ScreeningDetailResponse)
def get_screening_detail(screening_id: str, db: Session = Depends(get_db)):
    """
    Retrieves complete case file for a given screening ID.
    """
    screening = db.query(Screening).filter(Screening.id == screening_id).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Screening record not found")

    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.screening_id == screening_id)
        .all()
    )
    val_findings = (
        db.query(ValidationFinding)
        .filter(ValidationFinding.screening_id == screening_id)
        .all()
    )
    tamper_findings = (
        db.query(TamperFinding)
        .filter(TamperFinding.screening_id == screening_id)
        .all()
    )
    face_res = (
        db.query(FaceResult)
        .filter(FaceResult.screening_id == screening_id)
        .first()
    )
    id_matches = (
        db.query(IdentityMatch)
        .filter(IdentityMatch.screening_id == screening_id)
        .all()
    )
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.screening_id == screening_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )

    # Reconstruct extracted fields with bounding box
    reconstructed_fields = []
    for f in fields:
        bbox = json.loads(f.bounding_box_json) if f.bounding_box_json else None
        reconstructed_fields.append({
            "field_name": f.field_name,
            "visual_value": f.visual_value,
            "mrz_value": f.mrz_value,
            "confidence": f.confidence,
            "match_status": f.match_status,
            "bounding_box": bbox
        })

    # Reconstruct face result
    reconstructed_face = None
    if face_res:
        obs = json.loads(face_res.observations_json) if face_res.observations_json else []
        reconstructed_face = {
            "metric": face_res.metric,
            "similarity_score": face_res.similarity_score,
            "threshold": face_res.threshold,
            "verification_result": face_res.verification_result,
            "appearance_level": face_res.appearance_level,
            "observations": obs,
            "recommendation": face_res.recommendation
        }

    return {
        "id": screening.id,
        "created_at": screening.created_at,
        "document_type": screening.document_type,
        "masked_document_id": screening.masked_document_id,
        "status": screening.status,
        "risk_score": screening.risk_score,
        "risk_band": screening.risk_band,
        "recommendation": screening.recommendation,
        "execution_latency_ms": screening.execution_latency_ms,
        "doc_image_url": f"/api/v1/screenings/media/{screening.id}/doc",
        "live_image_url": f"/api/v1/screenings/media/{screening.id}/live" if screening.live_image_path else None,
        "ela_heatmap_url": f"/api/v1/screenings/media/{screening.id}/heatmap" if screening.ela_heatmap_path else None,
        "quality_assessment": {"verdict": "GOOD", "overall_score": 85.0},
        "extracted_fields": reconstructed_fields,
        "mrz_data": None,
        "validation_findings": val_findings,
        "tamper_findings": tamper_findings,
        "tamper_summary": {
            "composite_tamper_score": max([t.score for t in tamper_findings], default=0.0),
            "findings_count": len(tamper_findings)
        },
        "face_result": reconstructed_face,
        "identity_matches": id_matches,
        "risk_reasons": [],
        "signal_breakdown": {
            "mrz_integrity": 0.0,
            "tamper_forensics": max([t.score for t in tamper_findings], default=0.0),
            "face_verification": 10.0 if face_res and face_res.verification_result == "MATCH" else 80.0 if face_res else 0.0
        },
        "audit_trail": audit_events
    }


@router.get("/media/{screening_id}/{media_type}")
def get_screening_media(screening_id: str, media_type: str, db: Session = Depends(get_db)):
    """
    Streams requested media asset (doc, live, heatmap) securely.
    """
    screening = db.query(Screening).filter(Screening.id == screening_id).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Screening record not found")

    file_path = None
    if media_type == "doc":
        file_path = screening.doc_image_path
    elif media_type == "live":
        file_path = screening.live_image_path
    elif media_type == "heatmap":
        file_path = screening.ela_heatmap_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Media asset '{media_type}' not available.")

    # Determine media mime type
    mime = "image/jpeg"
    if file_path.endswith(".png"):
        mime = "image/png"
    elif file_path.endswith(".webp"):
        mime = "image/webp"

    return FileResponse(file_path, media_type=mime)
