"""
SatyaScan Synthetic Reference Watchlist Endpoints
Manages simulated prototype reference entries (stolen travel documents, lookout circulars).
Explicitly labeled as SYNTHETIC REFERENCE DATA.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.models.database import get_db, ReferenceWatchlist
from backend.app.schemas.screening import WatchlistEntryCreate, WatchlistEntryResponse

router = APIRouter(prefix="/watchlist", tags=["Reference Watchlist"])


@router.get("", response_model=List[WatchlistEntryResponse])
def get_watchlist(limit: int = 50, db: Session = Depends(get_db)):
    """
    Returns list of synthetic demo watchlist records.
    """
    records = db.query(ReferenceWatchlist).limit(limit).all()
    return records


@router.post("", response_model=WatchlistEntryResponse)
def add_watchlist_entry(entry: WatchlistEntryCreate, db: Session = Depends(get_db)):
    """
    Adds a new synthetic reference watchlist entry.
    """
    clean_id = entry.document_id.replace(" ", "").upper()
    existing = db.query(ReferenceWatchlist).filter(ReferenceWatchlist.document_id == clean_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Record already exists in watchlist.")

    rec = ReferenceWatchlist(
        document_id=clean_id,
        full_name=entry.full_name.upper(),
        nationality=entry.nationality.upper(),
        reason=entry.reason,
        risk_category=entry.risk_category,
        status=entry.status,
        classification="SYNTHETIC_PROTOTYPE_RECORD"
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
