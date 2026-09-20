"""
SatyaScan Tamper-Evident SHA-256 Audit Trail Service
Implements append-only cryptographic hash chaining for all screening lifecycle events.
Provides verification function to detect any retroactive tampering or data modification.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy.orm import Session

from backend.app.models.database import AuditEvent

GENESIS_HASH = "0" * 64


class AuditService:
    """
    Cryptographically chained audit trail manager.
    Each event links to the preceding event's SHA-256 hash digest, creating an immutable ledger.
    """

    @staticmethod
    def compute_sha256(data: str) -> str:
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    @classmethod
    def record_event(
        cls,
        db: Session,
        screening_id: str,
        event_type: str,
        payload_data: Any,
        actor: str = "SYSTEM_AUTOMATION"
    ) -> AuditEvent:
        """
        Appends a new cryptographically chained audit event.
        """
        # 1. Fetch latest event for this screening to get previous_hash
        last_event = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.desc())
            .first()
        )
        previous_hash = last_event.event_hash if last_event else GENESIS_HASH

        # 2. Hash payload
        payload_str = json.dumps(payload_data, sort_keys=True, default=str)
        payload_hash = cls.compute_sha256(payload_str)

        # 3. Calculate event hash
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        chain_string = f"{screening_id}|{previous_hash}|{timestamp_str}|{actor}|{event_type}|{payload_hash}"
        event_hash = cls.compute_sha256(chain_string)

        event = AuditEvent(
            screening_id=screening_id,
            timestamp=timestamp,
            actor=actor,
            event_type=event_type,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            event_hash=event_hash
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @classmethod
    def verify_audit_chain(cls, db: Session, screening_id: str) -> Dict[str, Any]:
        """
        Recomputes and verifies the integrity of the entire audit chain for a screening.
        Detects unauthorized payload alteration, insertion, or history deletion.
        """
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.screening_id == screening_id)
            .order_by(AuditEvent.id.asc())
            .all()
        )

        if not events:
            return {
                "screening_id": screening_id,
                "is_valid": True,
                "total_events": 0,
                "genesis_hash": GENESIS_HASH,
                "head_hash": GENESIS_HASH,
                "verified_at": datetime.now(timezone.utc),
                "status_message": "No audit records found for this screening."
            }

        expected_prev = GENESIS_HASH
        for i, ev in enumerate(events):
            # Verify previous_hash linkage
            if ev.previous_hash != expected_prev:
                return {
                    "screening_id": screening_id,
                    "is_valid": False,
                    "tampered_at_event_id": ev.id,
                    "event_type": ev.event_type,
                    "total_events": len(events),
                    "verified_at": datetime.now(timezone.utc),
                    "status_message": f"CRITICAL: Cryptographic chain discontinuity detected at event #{ev.id} ({ev.event_type}). Chain integrity compromised!"
                }

            # Recompute event hash
            ts_str = ev.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            chain_str = f"{ev.screening_id}|{ev.previous_hash}|{ts_str}|{ev.actor}|{ev.event_type}|{ev.payload_hash}"
            expected_hash = cls.compute_sha256(chain_str)

            if ev.event_hash != expected_hash:
                return {
                    "screening_id": screening_id,
                    "is_valid": False,
                    "tampered_at_event_id": ev.id,
                    "event_type": ev.event_type,
                    "total_events": len(events),
                    "verified_at": datetime.now(timezone.utc),
                    "status_message": f"CRITICAL: Event hash mismatch detected at event #{ev.id}. Record payload or signature was modified!"
                }

            expected_prev = ev.event_hash

        return {
            "screening_id": screening_id,
            "is_valid": True,
            "total_events": len(events),
            "genesis_hash": events[0].previous_hash,
            "head_hash": events[-1].event_hash,
            "verified_at": datetime.now(timezone.utc),
            "status_message": f"Cryptographic integrity verified. All {len(events)} events form an unbroken SHA-256 hash chain."
        }

    # Alias for convenience and test compatibility
    verify_chain = verify_audit_chain
