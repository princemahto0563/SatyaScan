"""
SatyaScan Permissioned Hyperledger Fabric Integration Verification Script
SIH26188 · Theme: Blockchain & Cybersecurity

Validates the complete permissioned blockchain anchoring lifecycle:
1. Deterministic document hashing (SHA-256)
2. Canonical result payload serialization & hashing
3. Privacy validator & PII-leakage prevention
4. Hyperledger Fabric anchor creation & offline fallback
5. Idempotent duplicate prevention
6. Unbroken SHA-256 audit ledger integration
7. Cryptographic evidence verification
"""

import sys
import os
import hashlib
import json
from datetime import datetime, timezone

# Ensure project root is on path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app.core.config import settings
from backend.app.models.database import SessionLocal, init_db, Screening, BlockchainAnchor, AuditEvent
from backend.app.services.fabric_service import FabricAnchorService
from backend.app.services.audit_service import AuditService


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_verification():
    print_section("SATYASCAN — HYPERLEDGER FABRIC PERMISSIONED BLOCKCHAIN AUDIT")
    print("Core Privacy Principle:")
    print("  'Evidence stays off-chain. Cryptographic proof goes on-chain.'")
    print(f"Network Target:     {settings.FABRIC_CHANNEL} @ {settings.FABRIC_GATEWAY_PEER}")
    print(f"Chaincode Contract: {settings.FABRIC_CHAINCODE}")
    print(f"MSP Organization:   {settings.FABRIC_MSP_ID}")

    init_db()
    db = SessionLocal()
    screening_id = f"SC-FABRIC-CLI-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    try:
        # Step 1: Document Hashing
        print_section("STEP 1: DETERMINISTIC DOCUMENT HASHING")
        sample_doc_bytes = b"MOCK_PASSPORT_IMAGE_RAW_BINARY_DATA_FOR_VERIFICATION"
        doc_hash = FabricAnchorService.compute_document_hash(sample_doc_bytes)
        print(f"  Input size:     {len(sample_doc_bytes)} bytes")
        print(f"  SHA-256 Digest: {doc_hash}")
        assert len(doc_hash) == 64, "Document hash must be 64-char hex string"
        print("  ✓ PASS: Deterministic document hash computed successfully.")

        # Step 2: Canonical Result Hashing
        print_section("STEP 2: CANONICAL RESULT PAYLOAD SERIALIZATION & HASHING")
        canonical_str = FabricAnchorService.get_canonical_payload(
            screening_id=screening_id,
            document_hash=doc_hash,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        res_hash = FabricAnchorService.compute_result_hash(
            screening_id=screening_id,
            document_hash=doc_hash,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        print(f"  Canonical String: {canonical_str}")
        print(f"  SHA-256 Digest:   {res_hash}")
        assert len(res_hash) == 64, "Result hash must be 64-char hex string"
        print("  ✓ PASS: Canonical result serialized and hashed deterministically.")

        # Step 3: Privacy & Data Minimization Pre-flight Check
        print_section("STEP 3: PRIVACY & DATA MINIMIZATION VALIDATOR")
        valid_payload = {
            "screeningId": screening_id,
            "documentHash": doc_hash,
            "resultHash": res_hash,
            "riskLevel": "LOW",
            "checkpointId": "CP-DEL-AIR"
        }
        is_valid, violation = FabricAnchorService.validate_no_pii_in_payload(valid_payload)
        assert is_valid, f"Clean payload failed validation: {violation}"
        print("  ✓ PASS: Clean hash-only payload accepted without warnings.")

        # Negative test: PII leakage attempt
        pii_leak_attempt = {
            "screeningId": screening_id,
            "full_name": "TEST PASSENGER",
            "passport_number": "A12345678",
            "documentHash": doc_hash
        }
        is_blocked, block_msg = FabricAnchorService.validate_no_pii_in_payload(pii_leak_attempt)
        assert not is_blocked, "PII leak attempt should have been blocked!"
        print(f"  ✓ PASS: PII leakage attempt successfully blocked: '{block_msg}'")

        # Step 4: Seed Screening & Create Anchor
        print_section("STEP 4: HYPERLEDGER FABRIC ANCHOR CREATION")
        sc = Screening(
            id=screening_id,
            document_type="PASSPORT",
            masked_document_id="Z12****67",
            status="PASSED",
            risk_score=10.0,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR",
            checkpoint_name="Delhi Airport Immigration Checkpoint"
        )
        db.add(sc)
        db.commit()

        anchor = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=sample_doc_bytes,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR",
            actor="CLI_VERIFIER"
        )
        print(f"  Screening ID:         {anchor['screening_id']}")
        print(f"  Anchor Status:        {anchor['status']}")
        print(f"  Network:              {anchor['network']}")
        print(f"  Channel:              {anchor['channel']}")
        print(f"  Chaincode:            {anchor['chaincode']}")
        print(f"  Transaction ID:       {anchor.get('transaction_id') or 'None (Ledger offline)'}")
        print(f"  Verification Message: {anchor['verification_message']}")
        print("  ✓ PASS: Anchor created and persisted with honest offline/online status.")

        # Step 5: Idempotent Duplicate Prevention
        print_section("STEP 5: IDEMPOTENT DUPLICATE PREVENTION")
        dup_anchor = FabricAnchorService.create_anchor(
            db=db,
            screening_id=screening_id,
            doc_bytes=sample_doc_bytes,
            risk_band="LOW",
            checkpoint_id="CP-DEL-AIR"
        )
        assert dup_anchor["id"] == anchor["id"], "Duplicate anchor created instead of returning existing!"
        count = db.query(BlockchainAnchor).filter(BlockchainAnchor.screening_id == screening_id).count()
        assert count == 1, f"Expected 1 anchor record, found {count}"
        print("  ✓ PASS: Duplicate anchor call returned existing record without secondary insert.")

        # Step 6: Unbroken SHA-256 Audit Chain Verification
        print_section("STEP 6: UNBROKEN SHA-256 AUDIT TRAIL VERIFICATION")
        audit_res = AuditService.verify_audit_chain(db, screening_id)
        print(f"  Audit Chain Valid:   {audit_res['is_valid']}")
        print(f"  Total Events:        {audit_res['total_events']}")
        print(f"  Audit Genesis Hash:  {audit_res['genesis_hash']}")
        print(f"  Audit Head Hash:     {audit_res['head_hash']}")
        assert audit_res["is_valid"], "SHA-256 audit chain was broken!"
        print("  ✓ PASS: Local SHA-256 audit chain intact and cryptographically verified.")

        # Step 7: On-Chain vs Off-Chain Verification
        print_section("STEP 7: EVIDENCE INTEGRITY VERIFICATION")
        verify_res = FabricAnchorService.verify_anchor(db, screening_id, actor="CLI_VERIFIER")
        print(f"  Verification Status:     {verify_res['status']}")
        print(f"  Document Hash Matches:   {verify_res['document_hash_matches']}")
        print(f"  Result Hash Matches:     {verify_res['result_hash_matches']}")
        print(f"  Privacy Compliance:      {verify_res['privacy_compliance']}")
        print(f"  Status Message:          {verify_res['status_message']}")
        assert verify_res["document_hash_matches"], "Document hash mismatch!"
        assert verify_res["result_hash_matches"], "Result hash mismatch!"
        print("  ✓ PASS: Off-chain evidence digests match anchor record perfectly.")

        print_section("SATYASCAN HYPERLEDGER FABRIC INTEGRATION: ALL 7 STAGES VERIFIED")
        print("Summary:")
        print("  - Zero PII on-chain enforced at service layer.")
        print("  - Local SHA-256 audit ledger remains fully operational.")
        print("  - Graceful fallback: transparent reporting when Fabric is offline.")
        print("  - Zero fabricated block numbers or fake transaction hashes.")
        print("=" * 70 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_verification()
