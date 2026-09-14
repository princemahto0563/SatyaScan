"""
SatyaScan Case Management Endpoints
Enables border officers and supervisors to review cases, update status, and attach investigation notes.
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.models.database import get_db, Screening
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/cases", tags=["Cases"])


class StatusUpdateRequest(BaseModel):
    status: str  # CLEARED, MANUAL_REVIEW_REQUIRED, ESCALATED
    officer_notes: str
    officer_badge: str


@router.put("/{case_id}/status")
def update_case_status(case_id: str, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    screening = db.query(Screening).filter(Screening.id == case_id).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Case record not found")

    old_status = screening.status
    screening.status = payload.status
    db.commit()

    # Record Audit Event for status modification
    AuditService.record_event(
        db, case_id, "OFFICER_REVIEW_DECISION",
        {
            "old_status": old_status,
            "new_status": payload.status,
            "notes": payload.officer_notes,
            "officer_badge": payload.officer_badge
        },
        actor=f"OFFICER_{payload.officer_badge}"
    )

    return {
        "case_id": case_id,
        "status": screening.status,
        "message": f"Case status updated from {old_status} to {payload.status}."
    }
