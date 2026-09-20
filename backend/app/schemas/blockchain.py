"""
SatyaScan Blockchain Anchor Schemas
Pydantic models for Hyperledger Fabric permissioned blockchain anchoring and verification.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class BlockchainAnchorSchema(BaseModel):
    id: Optional[int] = None
    screening_id: str
    document_hash: str
    result_hash: str
    transaction_id: Optional[str] = None
    ledger_asset_id: Optional[str] = None
    anchor_timestamp: Optional[datetime] = None
    network: str = "Hyperledger Fabric (Private)"
    channel: str = "satyascan-channel"
    chaincode: str = "screening_anchor"
    status: str = "PENDING"  # PENDING, VERIFIED, UNAVAILABLE, FAILED
    verification_timestamp: Optional[datetime] = None
    verification_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BlockchainAnchorCreateRequest(BaseModel):
    screening_id: str


class BlockchainVerificationResponse(BaseModel):
    screening_id: str
    is_verified: bool
    status: str  # VERIFIED, MISMATCH, UNAVAILABLE, FAILED
    document_hash: str
    result_hash: str
    document_hash_matches: bool
    result_hash_matches: bool
    network: str = "Hyperledger Fabric (Private)"
    channel: str = "satyascan-channel"
    chaincode: str = "screening_anchor"
    transaction_id: Optional[str] = None
    ledger_asset_id: Optional[str] = None
    anchor_timestamp: Optional[datetime] = None
    verification_timestamp: datetime
    status_message: str
    privacy_compliance: str = "PASSED (Zero PII, biometric data, or image bytes on-chain)"
    on_chain_record: Optional[Dict[str, Any]] = None
