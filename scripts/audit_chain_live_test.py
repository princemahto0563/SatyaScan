import os
import sys
from backend.app.models.database import SessionLocal, AuditEvent
from backend.app.services.audit_service import AuditService

print("==================================================")
print("AUDIT CHAIN LIVE INTEGRITY & TAMPER DETECTION TEST")
print("==================================================")

db = SessionLocal()
test_id = "SAT-LIVE-AUDIT-HARDENING-999"

try:
    # Clean up previous test runs if any
    db.query(AuditEvent).filter(AuditEvent.screening_id == test_id).delete()
    db.commit()

    # Step A: Record full 7-stage screening audit sequence
    stages = [
        ("UPLOAD_RECORDED", {"filename": "passport_test.jpg", "size": 1048576, "mime": "image/jpeg"}),
        ("OCR_COMPLETED", {"engine": "PaddleOCR", "raw_lines_extracted": 24, "mrz_found": True}),
        ("VALIDATION_COMPLETED", {"icao_rules_checked": 5, "mrz_check_digits_valid": True, "viz_consistent": True}),
        ("TAMPER_ANALYSIS_COMPLETED", {"ela_score": 14.2, "noise_score": 18.5, "copy_move_detected": False}),
        ("FACE_VERIFICATION_COMPLETED", {"similarity": 0.949, "metric": "Cosine Similarity", "appearance": "LOW"}),
        ("RISK_FUSION_COMPLETED", {"risk_score": 12.0, "risk_band": "LOW", "factors": []}),
        ("DECISION_ISSUED", {"verdict": "CLEAR", "recommendation": "Routine Clearance Permitted"}),
    ]

    for i, (event_type, payload) in enumerate(stages):
        ev = AuditService.record_event(db, test_id, event_type, payload)
        print(f"  [Recorded] Event #{i+1:02d}: {event_type:<28} -> Hash: {ev.event_hash[:16]}...")

    # Verification 1: Chain must PASS
    v1 = AuditService.verify_audit_chain(db, test_id)
    print(f"\n[Test 1: Initial Integrity Check]")
    print(f"  -> Valid: {v1['is_valid']}")
    print(f"  -> Status: {v1['status_message']}")
    assert v1["is_valid"] is True, "Initial chain must be valid!"

    # Step B: Tamper with historical Event #3 (TAMPER_ANALYSIS_COMPLETED)
    all_events = db.query(AuditEvent).filter(
        AuditEvent.screening_id == test_id
    ).order_by(AuditEvent.id.asc()).all()
    ev_to_tamper = all_events[3]
    original_payload_hash = ev_to_tamper.payload_hash

    # Simulate malicious attacker altering payload hash in SQLite
    ev_to_tamper.payload_hash = "0000000000000000deadbeefcafebabedeadbeefcafebabe0000000000000000"
    db.commit()
    print(f"\n[Malicious Breach Injected]: Event #03 payload altered to corrupted hash.")

    # Verification 2: Chain must FAIL
    v2 = AuditService.verify_audit_chain(db, test_id)
    print(f"\n[Test 2: Post-Tampering Verification]")
    print(f"  -> Valid: {v2['is_valid']}")
    print(f"  -> Status: {v2['status_message']}")
    assert v2["is_valid"] is False, "Chain MUST detect retroactive modification!"
    assert "mismatch" in v2["status_message"].lower() or "tamper" in v2["status_message"].lower()

    # Step C: Restore historical event
    ev_to_tamper.payload_hash = original_payload_hash
    db.commit()
    print(f"\n[Database Restored]: Event #03 payload restored to authentic hash.")

    # Verification 3: Chain must PASS again
    v3 = AuditService.verify_audit_chain(db, test_id)
    print(f"\n[Test 3: Post-Restoration Verification]")
    print(f"  -> Valid: {v3['is_valid']}")
    print(f"  -> Status: {v3['status_message']}")
    assert v3["is_valid"] is True, "Restored chain must be valid again!"

    print("\n==================================================")
    print("ALL 3 STAGES OF AUDIT INTEGRITY TEST PASSED CLEANLY!")
    print("==================================================")

finally:
    # Clean up test records
    db.query(AuditEvent).filter(AuditEvent.screening_id == test_id).delete()
    db.commit()
    db.close()
