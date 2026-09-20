"""
SatyaScan Synthetic Reference Watchlist Endpoints
Manages simulated prototype reference entries (stolen travel documents, lookout circulars).
Protected by JWT authentication and RBAC (Supervisor / Admin role required for modifications).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import re

from backend.app.models.database import get_db, ReferenceWatchlist, User
from backend.app.schemas.screening import WatchlistEntryCreate, WatchlistEntryResponse
from backend.app.core.security import get_current_user, require_role
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/watchlist", tags=["Reference Watchlist"])


@router.get("", response_model=List[WatchlistEntryResponse])
def get_watchlist(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns list of synthetic demo watchlist records for authenticated officers.
    """
    safe_limit = max(1, min(limit, 100))
    records = db.query(ReferenceWatchlist).limit(safe_limit).all()
    return records


@router.post("", response_model=WatchlistEntryResponse)
def add_watchlist_entry(
    entry: WatchlistEntryCreate,
    current_user: User = Depends(require_role(["SUPERVISOR", "ADMIN"])),
    db: Session = Depends(get_db)
):
    """
    Adds a new synthetic reference watchlist entry.
    RBAC Protected: Requires SUPERVISOR or ADMIN role.
    Appends WATCHLIST_CHANGE event to cryptographic audit ledger.
    """
    clean_id = re.sub(r'[^A-Za-z0-9_-]', '', entry.document_id).upper()
    if not clean_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document ID format.")

    existing = db.query(ReferenceWatchlist).filter(ReferenceWatchlist.document_id == clean_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Record already exists in watchlist.")

    rec = ReferenceWatchlist(
        document_id=clean_id,
        full_name=entry.full_name.strip().upper()[:100],
        nationality=entry.nationality.strip().upper()[:10],
        reason=entry.reason.strip()[:500],
        risk_category=entry.risk_category.strip().upper()[:30],
        status=entry.status.strip().upper()[:20],
        classification="SYNTHETIC_PROTOTYPE_RECORD"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Cryptographic Audit Ledger Entry
    try:
        AuditService.record_event(
            db=db,
            screening_id=f"WATCHLIST-{clean_id}",
            event_type="WATCHLIST_CHANGE",
            payload_data={
                "action": "ADD_ENTRY",
                "document_id": clean_id,
                "risk_category": rec.risk_category,
                "reason": rec.reason,
                "added_by": current_user.username,
                "role": current_user.role
            },
            actor=f"{current_user.role}:{current_user.username}"
        )
    except Exception:
        pass

    return rec
