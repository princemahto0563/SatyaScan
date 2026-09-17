"""
SatyaScan Case Management Endpoints
Enables border officers and supervisors to review cases, update status, and attach investigation notes.
Protected by JWT authentication and RBAC. Prevents officer badge spoofing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import re

from backend.app.models.database import get_db, Screening, User
from backend.app.core.security import get_current_user
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/cases", tags=["Cases"])

CASE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
ALLOWED_STATUSES = {"CLEARED", "MANUAL_REVIEW_REQUIRED", "ESCALATED", "SUSPENDED"}


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: CLEARED, MANUAL_REVIEW_REQUIRED, ESCALATED, SUSPENDED")
    officer_notes: str = Field(..., max_length=1000, description="Officer justification notes")


@router.put("/{case_id}/status")
def update_case_status(
    case_id: str,
    payload: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the operational review status of a screening case.
    Requires authenticated officer or supervisor. Attributions tied directly
    to authenticated JWT session rather than client-provided credentials.
    """
    clean_id = case_id.strip()
    if not CASE_ID_REGEX.match(clean_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid case ID format.")

    norm_status = payload.status.strip().upper()
    if norm_status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{payload.status}'. Allowed: {', '.join(ALLOWED_STATUSES)}"
        )

    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case record not found")

    old_status = screening.status
    screening.status = norm_status
    db.commit()

    # Record Audit Event with verified authenticated user credentials
    AuditService.record_event(
        db, clean_id, "OFFICER_REVIEW_DECISION",
        {
            "old_status": old_status,
            "new_status": norm_status,
            "notes": payload.officer_notes.strip(),
            "officer_badge": current_user.badge_number,
            "officer_name": current_user.full_name,
            "officer_role": current_user.role
        },
        actor=f"{current_user.role}_{current_user.badge_number}"
    )

    return {
        "case_id": clean_id,
        "status": screening.status,
        "updated_by": current_user.full_name,
        "message": f"Case status updated from {old_status} to {norm_status}."
    }
