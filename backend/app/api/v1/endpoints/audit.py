"""
SatyaScan Audit Trail & Cryptographic Verification Endpoints
Provides endpoints for retrieving immutable audit logs, verifying SHA-256 hash chains,
and generating local cryptographic notarization receipts.
Protected by JWT authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import re

from backend.app.models.database import get_db, AuditEvent, User
from backend.app.schemas.screening import AuditEventSchema, AuditVerificationResult
from backend.app.core.security import get_current_user
from backend.app.services.audit_service import AuditService
from backend.app.services.blockchain_adapter import BlockchainAnchorAdapter

router = APIRouter(prefix="/audit", tags=["Audit Trail"])
blockchain_adapter = BlockchainAnchorAdapter()

SCREENING_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_screening_id(screening_id: str) -> str:
    clean_id = screening_id.strip()
    if not SCREENING_ID_REGEX.match(clean_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid screening identifier format.")
    return clean_id


@router.get("/{screening_id}", response_model=List[AuditEventSchema])
def get_audit_trail(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns ordered audit ledger entries for an authenticated inspection case.
    """
    clean_id = validate_screening_id(screening_id)
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.screening_id == clean_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )
    return events


@router.post("/{screening_id}/verify", response_model=AuditVerificationResult)
def verify_audit_trail(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cryptographically verifies the unbroken SHA-256 hash chain from genesis to head.
    Detects retroactive modifications or payload alteration.
    """
    clean_id = validate_screening_id(screening_id)
    result = AuditService.verify_audit_chain(db, clean_id)
    return result


@router.post("/{screening_id}/anchor")
def anchor_audit_to_blockchain(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Certifies the latest verified audit hash with the local cryptographic notarization adapter.
    """
    clean_id = validate_screening_id(screening_id)
    verification = AuditService.verify_audit_chain(db, clean_id)
    if not verification["is_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot notarize compromised audit trail."
        )

    receipt = blockchain_adapter.create_anchor_receipt(
        screening_id=clean_id,
        audit_head_hash=verification["head_hash"],
        total_events=verification["total_events"]
    )
    return receipt
