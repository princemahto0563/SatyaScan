# SatyaScan — Hyperledger Fabric Permissioned Blockchain Layer

**Theme:** Blockchain & Cybersecurity  
**SIH Problem Statement:** SIH26188 — AI Based Fake Identity & Document Screening  

---

## Core Architecture & Privacy Principle

> **"Evidence stays off-chain. Cryptographic proof goes on-chain."**

SatyaScan implements a **dual-layer audit architecture**:
1. **Local SHA-256 Chained Audit Ledger**: Every inspection stage is recorded sequentially in the SQLite database with cryptographic chaining from genesis to head hash.
2. **Permissioned Blockchain Anchor (Hyperledger Fabric)**: Minimal cryptographic digests (`document_hash` and `result_hash`) are anchored to an immutable private consortium ledger.

Public blockchains (such as Ethereum, Polygon, or Solana) are **strictly rejected** because:
- Public ledgers expose transactional timing and pattern analysis to untrusted entities.
- Public gas fees and variable block times are unsuitable for mission-critical border checkpoints.
- Regulatory compliance (GDPR, Digital Personal Data Protection Act) mandates that identity data and surveillance metadata must remain strictly within national sovereign jurisdiction.

---

## What is Stored On-Chain vs. Off-Chain

| Category | Storage Location | Specific Items Stored |
| :--- | :--- | :--- |
| **Sensitive Identity Data** | **OFF-CHAIN ONLY** (Memory / Local Encrypted Storage) | Passport / Visa image scans, live selfies, face crops, 512-D biometric descriptors, OCR raw text, full names, dates of birth, nationality, passport numbers, visa numbers. |
| **Forensic & Quality Signals** | **OFF-CHAIN ONLY** (Local SQLite DB) | ELA anomaly maps, ORB keypoint coordinates, blur variance metrics, detailed field-by-field discrepancies. |
| **Cryptographic Anchors** | **ON-CHAIN** (Hyperledger Fabric) | `screeningId`, `documentHash` (32-byte SHA-256), `resultHash` (32-byte SHA-256), `riskLevel` (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), `checkpointId`, `timestamp`, `pipelineVersion`, `anchorVersion`. |

---

## Chaincode Specification (`screening_anchor`)

* **Chaincode Path:** `blockchain/chaincode/screening_anchor/`
* **Language:** Go (Fabric Contract API v1.2.2)
* **Channel Name:** `satyascan-channel`
* **Contract Name:** `ScreeningAnchorContract`

### Transactions

1. **`CreateScreeningAnchor(screeningId, documentHash, resultHash, riskLevel, checkpointId, timestamp, pipelineVersion, anchorVersion)`**
   - Validates that hashes are exactly 64-character hexadecimal strings.
   - Rejects duplicate anchor submissions for the same `screeningId` (immutable once committed).
   - Writes asset to the ledger state and emits an `AnchorCreated` event.

2. **`GetScreeningAnchor(screeningId)`**
   - Retrieves the immutable anchor record for verification.

3. **`VerifyScreeningAnchor(screeningId, documentHash, resultHash)`**
   - Compares presented local document and result hashes against the on-chain asset.
   - Returns boolean match status and detailed discrepancy messages.

---

## Deterministic Hash Construction

To guarantee reproducibility across platforms and prevent key-ordering serialization issues, hashes are constructed deterministically:

1. **Document Integrity Hash**:
   $$\text{document\_hash} = \text{SHA-256}(\text{raw uploaded image bytes})$$

2. **Result Integrity Hash**:
   $$\text{canonical\_payload} = \text{screening\_id} \mathbin{\Vert} \text{document\_hash} \mathbin{\Vert} \text{risk\_band} \mathbin{\Vert} \text{checkpoint\_id} \mathbin{\Vert} \text{pipeline\_version}$$
   $$\text{result\_hash} = \text{SHA-256}(\text{canonical\_payload})$$

---

## Local Fabric Development Network Setup

To run a live Hyperledger Fabric test network on a machine with Docker and the Fabric CLI installed:

```bash
# 1. Clone fabric-samples (if not already present)
git clone https://github.com/hyperledger/fabric-samples.git
cd fabric-samples/test-network

# 2. Start the network with a Certificate Authority and create satyascan-channel
./network.sh up createChannel -c satyascan-channel -ca

# 3. Deploy the SatyaScan chaincode
cd /path/to/SatyaScan
chmod +x blockchain/deploy_chaincode.sh
./blockchain/deploy_chaincode.sh satyascan-channel screening_anchor 1.0 1

# 4. Enable Fabric in the backend configuration (.env)
FABRIC_ENABLED=true
FABRIC_GATEWAY_PEER=localhost:7051
FABRIC_CHANNEL=satyascan-channel
FABRIC_CHAINCODE=screening_anchor
FABRIC_MSP_ID=Org1MSP
```

---

## Offline & Air-Gapped Station Fallback

If an isolated border checkpoint loses connectivity to the private ledger nodes:
- The core screening pipeline **does not fail**.
- The local SHA-256 audit chain **remains 100% intact and valid**.
- The blockchain anchor status is cleanly recorded as:
  $$\text{status} = \text{BLOCKCHAIN\_ANCHOR\_UNAVAILABLE}$$
- The UI and PDF report clearly state:
  > *"Private ledger service is not reachable. Existing SHA-256 audit chain remains active."*
- When ledger connectivity is restored, pending screening records can be anchored retroactively via:
  $$\text{POST } /api/v1/blockchain/\{screening\_id\}/anchor$$
