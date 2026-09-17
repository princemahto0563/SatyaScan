"""
SatyaScan Screening REST Endpoints
Handles document uploads, automated screening execution, media retrieval, and case inspection.
Protected by JWT authentication, RBAC, input validation, and rate limiting.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import json
import re

from backend.app.models.database import (
    get_db, Screening, ExtractedField, ValidationFinding,
    TamperFinding, FaceResult, IdentityMatch, AuditEvent, User
)
from backend.app.schemas.screening import ScreeningDetailResponse, ScreeningSummaryResponse
from backend.app.core.config import settings
from backend.app.core.security import (
    validate_uploaded_image_bytes, sanitize_filename, get_current_user
)
from backend.app.core.rate_limiter import rate_limit_screening
from backend.app.services.orchestrator import screening_orchestrator

router = APIRouter(prefix="/screenings", tags=["Screenings"])

ALLOWED_DOC_TYPES = {"PASSPORT", "VISA", "NATIONAL_ID"}
SCREENING_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_screening_id(screening_id: str) -> str:
    clean_id = screening_id.strip()
    if not SCREENING_ID_REGEX.match(clean_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid screening identifier format."
        )
    return clean_id


@router.post(
    "",
    response_model=ScreeningDetailResponse,
    dependencies=[Depends(rate_limit_screening)]
)
async def create_screening(
    document_file: UploadFile = File(...),
    live_selfie_file: Optional[UploadFile] = File(None),
    document_type: str = Form("PASSPORT"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes automated screening on uploaded travel document and optional live selfie.
    Requires authenticated officer session. Enforces file size, magic header,
    image decode validation, and rate limits.
    """
    # 1. Validate document type input
    norm_doc_type = document_type.strip().upper()
    if norm_doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported document type '{document_type}'. Allowed: {', '.join(ALLOWED_DOC_TYPES)}"
        )

    # 2. Validate and save document file
    doc_bytes = await document_file.read()
    validate_uploaded_image_bytes(doc_bytes, document_file.filename or "upload.jpg")

    clean_doc_name = sanitize_filename(document_file.filename or "doc.jpg")
    doc_ext = clean_doc_name.split('.')[-1].lower() if '.' in clean_doc_name else 'jpg'
    if doc_ext not in ["jpg", "jpeg", "png", "webp"]:
        doc_ext = "jpg"

    doc_filename = f"doc_{uuid.uuid4().hex}.{doc_ext}"
    doc_path = os.path.join(settings.UPLOAD_DIR, doc_filename)

    with open(doc_path, "wb") as f:
        f.write(doc_bytes)

    # 3. Validate and save live selfie if provided
    live_path = None
    if live_selfie_file and live_selfie_file.filename:
        live_bytes = await live_selfie_file.read()
        validate_uploaded_image_bytes(live_bytes, live_selfie_file.filename)

        clean_live_name = sanitize_filename(live_selfie_file.filename)
        live_ext = clean_live_name.split('.')[-1].lower() if '.' in clean_live_name else 'jpg'
        if live_ext not in ["jpg", "jpeg", "png", "webp"]:
            live_ext = "jpg"

        live_filename = f"live_{uuid.uuid4().hex}.{live_ext}"
        live_path = os.path.join(settings.UPLOAD_DIR, live_filename)
        with open(live_path, "wb") as f:
            f.write(live_bytes)

    # 4. Execute full screening pipeline with operator attribution
    result = screening_orchestrator.process_screening(
        db=db,
        doc_image_path=doc_path,
        live_image_path=live_path,
        operator_id=current_user.id,
        doc_type=norm_doc_type,
        checkpoint_id=getattr(current_user, "checkpoint_id", None),
        checkpoint_name=getattr(current_user, "checkpoint_name", None)
    )

    return result


@router.post(
    "/preset/{case_num}",
    response_model=ScreeningDetailResponse,
    dependencies=[Depends(rate_limit_screening)]
)
def execute_preset_screening(
    case_num: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes automated screening directly on canonical demo preset case (01 to 09).
    Requires authenticated officer session.
    """
    preset_map = {
        "01": ("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "02": ("data/tampered/case02_expired_ravi.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "03": ("data/tampered/case03_tampered_dob.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "04": ("data/tampered/case04_photo_replaced.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "05": ("data/tampered/case05_copymove_stamp.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "06": ("data/genuine/case06_multi_identity.jpg", "data/selfies/case01_selfie_arjun.jpg", "PASSPORT"),
        "07": ("data/tampered/case07_blurry_fail.jpg", None, "PASSPORT"),
        "08": ("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case08_selfie_bearded_arjun.jpg", "PASSPORT"),
        "09": ("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case09_selfie_imposter.jpg", "PASSPORT"),
    }
    clean_num = case_num.strip().zfill(2)
    if clean_num not in preset_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset case '{case_num}' not found. Available presets: 01 to 09."
        )

    doc_rel, live_rel, doc_type = preset_map[clean_num]
    doc_path = os.path.join(settings.PROJECT_ROOT, doc_rel)
    live_path = os.path.join(settings.PROJECT_ROOT, live_rel) if live_rel else None

    if not os.path.exists(doc_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset document file not found: {doc_rel}"
        )

    result = screening_orchestrator.process_screening(
        db=db,
        doc_image_path=doc_path,
        live_image_path=live_path,
        operator_id=current_user.id,
        doc_type=doc_type,
        checkpoint_id=getattr(current_user, "checkpoint_id", None),
        checkpoint_name=getattr(current_user, "checkpoint_name", None)
    )
    return result


@router.get("", response_model=List[ScreeningSummaryResponse])
def list_screenings(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists recent screening records with pagination for authenticated officers.
    """
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    screenings = (
        db.query(Screening)
        .order_by(Screening.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )
    return screenings


@router.get("/{screening_id}", response_model=ScreeningDetailResponse)
def get_screening_detail(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves complete case dossier for a validated screening ID.
    Requires authentication.
    """
    clean_id = validate_screening_id(screening_id)
    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found")

    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.screening_id == clean_id)
        .all()
    )
    val_findings = (
        db.query(ValidationFinding)
        .filter(ValidationFinding.screening_id == clean_id)
        .all()
    )
    tamper_findings = (
        db.query(TamperFinding)
        .filter(TamperFinding.screening_id == clean_id)
        .all()
    )
    face_res = (
        db.query(FaceResult)
        .filter(FaceResult.screening_id == clean_id)
        .first()
    )
    id_matches = (
        db.query(IdentityMatch)
        .filter(IdentityMatch.screening_id == clean_id)
        .all()
    )
    audit_events = (
        db.query(AuditEvent)
        .filter(AuditEvent.screening_id == clean_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )

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
        "checkpoint_id": screening.checkpoint_id,
        "checkpoint_name": screening.checkpoint_name,
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
def get_screening_media(
    screening_id: str,
    media_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streams requested media asset (doc, live, heatmap) securely for authenticated officers.
    Replaces unsafe public static file mounts. Prevents directory traversal.
    """
    clean_id = validate_screening_id(screening_id)
    if media_type not in ["doc", "live", "heatmap"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid media type requested."
        )

    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found")

    file_path = None
    if media_type == "doc":
        file_path = screening.doc_image_path
    elif media_type == "live":
        file_path = screening.live_image_path
    elif media_type == "heatmap":
        file_path = screening.ela_heatmap_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Media asset '{media_type}' not available.")

    # Prevent path traversal outside allowed directories
    real_path = os.path.realpath(file_path)
    allowed_dirs = [os.path.realpath(settings.STORAGE_DIR), os.path.realpath(settings.DATA_DIR)]
    is_safe = any(real_path.startswith(d) for d in allowed_dirs)
    if not is_safe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to path denied.")

    # Determine media mime type
    mime = "image/jpeg"
    if file_path.endswith(".png"):
        mime = "image/png"
    elif file_path.endswith(".webp"):
        mime = "image/webp"

    return FileResponse(file_path, media_type=mime)
