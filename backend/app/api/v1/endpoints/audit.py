"""
SatyaScan Audit Trail & Cryptographic Verification Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.models.database import get_db, AuditEvent
from backend.app.schemas.screening import AuditEventSchema, AuditVerificationResult
from backend.app.services.audit_service import AuditService
from backend.app.services.blockchain_adapter import BlockchainAnchorAdapter

router = APIRouter(prefix="/audit", tags=["Audit Trail"])
blockchain_adapter = BlockchainAnchorAdapter()


@router.get("/{screening_id}", response_model=List[AuditEventSchema])
def get_audit_trail(screening_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.screening_id == screening_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )
    return events


@router.post("/{screening_id}/verify", response_model=AuditVerificationResult)
def verify_audit_trail(screening_id: str, db: Session = Depends(get_db)):
    """
    Cryptographically verifies the unbroken SHA-256 hash chain from genesis to head.
    Detects retroactive modifications.
    """
    result = AuditService.verify_audit_chain(db, screening_id)
    return result


@router.post("/{screening_id}/anchor")
def anchor_audit_to_blockchain(screening_id: str, db: Session = Depends(get_db)):
    """
    Notarizes the latest audit hash to the blockchain notarization adapter.
    """
    verification = AuditService.verify_audit_chain(db, screening_id)
    if not verification["is_valid"]:
        raise HTTPException(status_code=400, detail="Cannot anchor compromised audit trail.")

    receipt = blockchain_adapter.create_anchor_receipt(
        screening_id=screening_id,
        audit_head_hash=verification["head_hash"],
        total_events=verification["total_events"]
    )
    return receipt
