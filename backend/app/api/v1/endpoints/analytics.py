"""
SatyaScan Checkpoint Operational Analytics Endpoints
Provides real aggregated statistics computed from the screening database.
NO random fabricated numbers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from backend.app.models.database import (
    get_db, Screening, TamperFinding, IdentityMatch, ValidationFinding, User
)
from backend.app.core.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("")
def get_checkpoint_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Computes genuine operational metrics from screening history.
    """
    total_screenings = db.query(Screening).count()
    
    # Risk band distribution
    bands = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    band_counts = (
        db.query(Screening.risk_band, func.count(Screening.id))
        .group_by(Screening.risk_band)
        .all()
    )
    for band, count in band_counts:
        if band in bands:
            bands[band] = count

    # Manual reviews count
    manual_reviews = db.query(Screening).filter(
        Screening.status.in_(["MANUAL_REVIEW_REQUIRED", "MANUAL_REVIEW"])
    ).count()

    # Latency average
    avg_latency = db.query(func.avg(Screening.execution_latency_ms)).scalar() or 0.0

    # Tampering technique breakdown
    tamper_counts = (
        db.query(TamperFinding.technique, func.count(TamperFinding.id))
        .group_by(TamperFinding.technique)
        .all()
    )
    tamper_breakdown = {t: count for t, count in tamper_counts}

    # Document type breakdown
    doc_counts = (
        db.query(Screening.document_type, func.count(Screening.id))
        .group_by(Screening.document_type)
        .all()
    )
    doc_distribution = {d: count for d, count in doc_counts}

    # Top validation failures
    val_counts = (
        db.query(ValidationFinding.rule_id, func.count(ValidationFinding.id))
        .group_by(ValidationFinding.rule_id)
        .order_by(func.count(ValidationFinding.id).desc())
        .limit(5)
        .all()
    )
    top_failures = [{"rule_id": r, "count": c} for r, c in val_counts]

    # Multi-identity reuse alerts
    identity_alerts = db.query(IdentityMatch).count()

    return {
        "summary": {
            "total_screenings": total_screenings,
            "manual_reviews_required": manual_reviews,
            "manual_review_rate_pct": round((manual_reviews / max(total_screenings, 1)) * 100, 1),
            "average_latency_ms": round(avg_latency, 1),
            "identity_reuse_alerts": identity_alerts
        },
        "risk_distribution": [
            {"band": "LOW", "count": bands["LOW"], "color": "#10B981"},
            {"band": "MEDIUM", "count": bands["MEDIUM"], "color": "#F59E0B"},
            {"band": "HIGH", "count": bands["HIGH"], "color": "#EF4444"},
            {"band": "CRITICAL", "count": bands["CRITICAL"], "color": "#991B1B"}
        ],
        "document_distribution": doc_distribution,
        "tamper_breakdown": tamper_breakdown,
        "top_validation_failures": top_failures,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
