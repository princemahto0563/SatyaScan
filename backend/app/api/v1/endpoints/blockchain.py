"""
SatyaScan Hyperledger Fabric Blockchain Anchor Endpoints
SIH26188 · Theme: Blockchain & Cybersecurity

Provides REST API endpoints to:
1. Anchor screening cryptographic evidence hashes to Hyperledger Fabric.
2. Query immutable anchor metadata from ledger and local state.
3. Cryptographically verify off-chain evidence hashes against on-chain records.
Protected by JWT authentication and checkpoint-level RBAC.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import os
import re

from backend.app.models.database import get_db, BlockchainAnchor, Screening, User
from backend.app.schemas.blockchain import (
    BlockchainAnchorSchema,
    BlockchainVerificationResponse
)
from backend.app.core.security import get_current_user
from backend.app.services.fabric_service import FabricAnchorService

router = APIRouter(prefix="/blockchain", tags=["Blockchain Anchor"])

SCREENING_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def validate_screening_id(screening_id: str) -> str:
    clean_id = screening_id.strip()
    if not SCREENING_ID_REGEX.match(clean_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid screening identifier format."
        )
    return clean_id


from backend.app.core.permissions import check_checkpoint_access


def check_screening_access(screening: Screening, current_user: User, db: Optional[Session] = None):
    """
    Enforces checkpoint authorization scoping and records ACCESS_DENIED on violations.
    Officers can only access screenings originating from their assigned checkpoint.
    Supervisors and Admins have global inspection authority.
    """
    check_checkpoint_access(current_user, screening, db, resource_type="blockchain_anchor")


@router.post("/{screening_id}/anchor", response_model=BlockchainAnchorSchema)
def anchor_screening_to_blockchain(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Anchors SHA-256 evidence digests (document hash and canonical result hash)
    to the permissioned Hyperledger Fabric ledger.
    Zero PII or raw images are transmitted to the ledger.
    """
    clean_id = validate_screening_id(screening_id)
    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening '{clean_id}' not found."
        )

    check_screening_access(screening, current_user)

    # Idempotent: return existing anchor if already recorded
    existing_anchor = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == clean_id).first()
    if existing_anchor:
        return existing_anchor

    doc_bytes: Optional[bytes] = None
    if screening.doc_image_path and os.path.exists(screening.doc_image_path):
        try:
            with open(screening.doc_image_path, "rb") as f:
                doc_bytes = f.read()
        except Exception:
            doc_bytes = None

    anchor_data = FabricAnchorService.create_anchor(
        db=db,
        screening_id=clean_id,
        doc_bytes=doc_bytes,
        risk_band=screening.risk_band or "LOW",
        checkpoint_id=screening.checkpoint_id or (current_user.checkpoint_id or "CP-DEL-AIR"),
        actor=current_user.badge_number or current_user.username
    )
    return anchor_data


@router.get("/{screening_id}", response_model=BlockchainAnchorSchema)
def get_blockchain_anchor(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the permissioned Hyperledger Fabric anchor record for a screening.
    """
    clean_id = validate_screening_id(screening_id)
    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if screening:
        check_screening_access(screening, current_user)

    anchor = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == clean_id).first()
    if not anchor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blockchain anchor found for screening '{clean_id}'."
        )
    return anchor


@router.post("/{screening_id}/verify", response_model=BlockchainVerificationResponse)
def verify_blockchain_anchor(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifies local screening evidence hashes against the permissioned ledger anchor.
    Detects any discrepancy between local storage and ledger state.
    """
    clean_id = validate_screening_id(screening_id)
    screening = db.query(Screening).filter(Screening.id == clean_id).first()
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening '{clean_id}' not found."
        )

    check_screening_access(screening, current_user)

    anchor = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == clean_id).first()
    if not anchor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blockchain anchor exists for screening '{clean_id}' to verify."
        )

    result = FabricAnchorService.verify_anchor(
        db=db,
        screening_id=clean_id,
        actor=current_user.badge_number or current_user.username
    )
    return result
