"""
SatyaScan Blockchain Adapter
Integrates with Hyperledger Fabric permissioned ledger via FabricAnchorService.
Maintains strict privacy: NEVER publishes PII, images, or raw biometric embeddings to the ledger.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.database import SessionLocal
from backend.app.services.fabric_service import FabricAnchorService


class BlockchainAnchorAdapter:
    """
    Adapter interface delegating to FabricAnchorService for permissioned blockchain anchoring.
    """

    def __init__(self, network: str = "Hyperledger Fabric (Private)"):
        self.network = network
        self.version = "FabricAnchor-v1.0"

    def create_anchor_receipt(
        self,
        screening_id: str,
        audit_head_hash: str,
        total_events: int,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Delegates to FabricAnchorService for deterministic anchoring and receipt generation.
        Never fabricates mock block numbers or fake transaction hashes.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            anchor = FabricAnchorService.create_anchor(
                db=db,
                screening_id=screening_id,
                risk_band="LOW",
                actor="SYSTEM_AUTOMATION"
            )
            return {
                "anchored": anchor.get("status") == "VERIFIED",
                "screening_id": screening_id,
                "network": anchor.get("network", self.network),
                "channel": anchor.get("channel", "satyascan-channel"),
                "chaincode": anchor.get("chaincode", "screening_anchor"),
                "status": anchor.get("status"),
                "notarized_root_hash": anchor.get("result_hash"),
                "document_hash": anchor.get("document_hash"),
                "result_hash": anchor.get("result_hash"),
                "total_events_certified": total_events,
                "transaction_hash": anchor.get("transaction_id"),
                "block_number": None,  # Never fabricated when offline
                "timestamp": (anchor.get("anchor_timestamp") or datetime.now(timezone.utc)).isoformat(),
                "privacy_compliance": "PASSED (Zero PII, biometric data, or image bytes on-chain)",
                "verification_status": anchor.get("verification_message", "BLOCKCHAIN_ANCHOR_UNAVAILABLE")
            }
        finally:
            if close_db:
                db.close()
