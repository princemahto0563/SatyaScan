# SatyaScan — AI-Based Fake Identity & Document Screening System

**SIH Problem Statement:** SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division  
**Category:** Software Prototype  
**Theme:** Blockchain & Cybersecurity · Artificial Intelligence · Border Security  
**Motto:** *Verify. Detect. Explain.*  
**Security Classification:** Security-Hardened SIH Prototype  

---

## 1. Connected Platform Architecture

SatyaScan delivers a unified, security-hardened pipeline connecting defensive cybersecurity, automated identity screening, tamper-evident auditing, and permissioned enterprise distributed ledger technology:

```
CYBERSECURITY LAYER ──► IDENTITY/DOCUMENT SCREENING ──► SHA-256 AUDIT ──► HYPERLEDGER FABRIC
```

```
                                 [ BORDER CHECKPOINT WORKSTATION ]
                                                │
               ┌────────────────────────────────┴────────────────────────────────┐
               ▼                                                                 ▼
     [ Physical Document ]                                              [ Live Webcam Selfie ]
               │                                                                 │
               ▼                                                                 ▼
   [ File & Image Security Gate ]                                      [ Quality Gate (Blur/Glare) ]
   - Magic bytes (\xFF\xD8\xFF, \x89PNG, RIFF)                                   │
   - Image decode verification                                                   │
   - Max 10MB, Max 5000px, 25M pixels                                            │
               │                                                                 │
               ▼                                                                 │
  [ Document Classifier Gate ] ──► Reject Aadhaar/PAN/DL/Voter ID               │
               │                   (Only Passport & Visa Accepted)               │
               ▼                                                                 │
    ┌──────────┴──────────┐                                                      │
    ▼                     ▼                                                      │
[ Passport Pipeline ]  [ Visa Pipeline ]                                         │
    │                     │                                                      │
    ├─ ICAO 9303 MRZ      ├─ Syntax Validation                                   │
    ├─ Checksum (7-3-1)   ├─ Date Range Rules                                    │
    ├─ OCR Extraction     ├─ Type Check                                          │
    └─ VIZ/MRZ Cross-Check└─ Passport Linkage                                    │
               │                     │                                           │
               └──────────┬──────────┘                                           │
                          ▼                                                      │
               [ Forensic Analysis ] ◄───────────────────────────────────────────┘
               ├─ Error Level Analysis (ELA)
               ├─ Noise Residual Analysis
               ├─ Copy-Move Clone Detection
               └─ Metadata Software Provenance
                          │
                          ▼
               [ Biometric Verification ] ◄──────────────────────────────────────┘
               ├─ Cosine Facial Similarity (Gabor-LBP)
               ├─ Appearance Variation Classification
               └─ FAISS Multi-Identity Watchlist Search
                          │
                          ▼
            [ Risk Engine & Recommendation ]
            (LOW, MEDIUM, HIGH, CRITICAL)
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
[ Local SHA-256 Audit Chain ]    [ Hyperledger Fabric Ledger ]
 (Unbroken Event Hash Chain)     (Private Consortium Anchor)
         │                                 │
         └────────────────┬────────────────┘
                          ▼
             [ Signed Forensic PDF Report ]
```

---

## 2. Core Security & Privacy Principles

1. **Zero Public Blockchains**: Built strictly on permissioned enterprise distributed ledger technology (**Hyperledger Fabric v2.5+**). Zero cryptocurrency tokens, gas fees, or exposure to public mempools.
2. **Evidence Stays Off-Chain; Cryptographic Proof Goes On-Chain**: Raw document imagery, passenger PII, names, passport numbers, and biometric face descriptors **never** touch the ledger. Only irreversible SHA-256 evidence digests are anchored on-chain.
3. **Server-Side Zero-Trust & Station Isolation**: Client-provided `document_type`, `checkpoint_id`, and roles are strictly untrusted. Station isolation (`check_checkpoint_access`) prevents IDOR attacks by restricting officers to their assigned checkpoint while granting supervisors authorized multi-station oversight.
4. **Transparent & Honest Reporting**: If the Hyperledger Fabric ledger peer is offline or unreachable, SatyaScan transparently reports `status: "UNAVAILABLE"` while maintaining unbroken local SHA-256 cryptographic audit logs. It **never fabricates** mock transaction hashes, block numbers, or confirmations.
5. **Local-First & Offline Capable**: Designed for zero-connectivity border outposts with completely local AI inference (PaddleOCR, OpenCV ELA, Cosine face verification, FAISS duplicate detection).

---

## 3. Permissioned Blockchain Audit Anchor (Hyperledger Fabric)

SatyaScan implements a dedicated permissioned blockchain anchoring layer using **Hyperledger Fabric v2.5+**:

- **Channel:** `satyascan-channel`
- **Chaincode Contract:** `screening_anchor` ([`blockchain/chaincode/screening_anchor/screening_anchor.go`](file:///Users/princemahto/Downloads/SatyaScan/blockchain/chaincode/screening_anchor/screening_anchor.go))
- **Endorsement Policy:** `AND('Org1MSP.peer')`
- **Asset ID Scheme:** `ANCHOR_{screening_id}`

### Data Minimization Matrix

| Data Element | Storage Location | On-Chain State | Privacy / Protection |
| :--- | :--- | :--- | :--- |
| **Uploaded Document Image** | Local Workstation Disk | **NEVER** | UUID-isolated, authenticated API only |
| **Live Webcam Selfie** | In-Memory Workstation | **NEVER** | Purged after session; excluded from browser cache |
| **Passenger Name, DOB, Doc #** | Local SQLite Database | **NEVER** | Masked in public UI (`A****N S****A`, `Z12****67`) |
| **Raw OCR Text / MRZ Lines** | Local SQLite Database | **NEVER** | Blocked by service-level PII validator |
| **Biometric Face Vectors** | Local FAISS Index | **NEVER** | 128-dimensional vectors stored locally only |
| **Document SHA-256 Digest** | Local DB + Fabric Ledger | **YES** | Deterministic 64-character lowercase hex digest |
| **Canonical Result Digest** | Local DB + Fabric Ledger | **YES** | SHA-256 of `screening_id\|doc_hash\|risk\|cp_id\|v1.0.0` |
| **Screening ID & Checkpoint** | Local DB + Fabric Ledger | **YES** | Audit trail reference and checkpoint code |

---

## 4. REST API Endpoints

### Authentication & Checkpoint Binding
- `POST /api/v1/auth/login`: Authenticate checkpoint officer with JWT Bearer token (`HS256`).
- `GET /api/v1/auth/checkpoints`: List all 8 canonical border checkpoints.
- `GET /api/v1/auth/me`: Retrieve current authenticated officer profile and station identity.

### Document Screening & Case Management
- `POST /api/v1/screenings`: Submit document upload and optional selfie for automated inspection.
- `GET /api/v1/screenings`: List recent screening summaries for authenticated checkpoint.
- `GET /api/v1/screenings/{id}`: Retrieve comprehensive screening dossier (includes `blockchain_anchor`).
- `GET /api/v1/screenings/media/{id}/{type}`: Stream secure media assets (`doc`, `live`, `heatmap`).
- `PUT /api/v1/cases/{id}/status`: Update review status (RBAC protected, checkpoint scoped).

### Hyperledger Fabric Blockchain Anchor
- `POST /api/v1/blockchain/{id}/anchor`: Anchor document and result digests to Hyperledger Fabric.
- `GET /api/v1/blockchain/{id}`: Retrieve immutable ledger anchor record for a screening.
- `POST /api/v1/blockchain/{id}/verify`: Cryptographically verify off-chain evidence against on-chain anchor.

### Audit & Reports
- `GET /api/v1/audit/{id}`: Retrieve unbroken SHA-256 audit ledger entries.
- `POST /api/v1/audit/{id}/verify`: Verify mathematical integrity of audit chain from genesis to head.
- `GET /api/v1/reports/{id}/pdf`: Generate official signed forensic PDF report.

---

## 5. Quickstart & Verification

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- (Optional for live ledger) Docker & Docker Compose

### 1. Install Dependencies
```bash
# Python backend
pip install -r requirements.txt

# Next.js frontend
cd frontend && npm install && cd ..
```

### 2. Run Comprehensive Automated Test Suites (154 Tests)
```bash
# Cybersecurity Hardening Test Suite (42 tests covering T-01 to T-15)
pytest tests/test_cybersecurity_hardening.py -v

# Hyperledger Fabric Anchor Test Suite (19 tests)
pytest tests/test_blockchain_anchor.py -v

# Canonical Border Checkpoint & Auth Suite (17 tests)
pytest tests/test_checkpoint_auth.py -v

# Strict Document Pipeline & Classifier Suite (42 tests)
pytest tests/test_strict_pipeline.py -v

# Full Regression Suite (154 tests across all modules)
pytest tests/ -v

# End-to-End Real Document QA Suite (17 verification phases)
python3 -m scripts.e2e_backend_qa_suite

# Hyperledger Fabric Integration CLI Verifier
python3 scripts/test_blockchain_integration.py
```

### 3. Build & Run Application
```bash
# Build Frontend
npm --prefix frontend run build

# Start Backend Server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Frontend Dev Server
npm --prefix frontend run dev
```

---

## 6. Security Documentation

For an exhaustive audit of all security controls, 15-threat matrix, cryptographic chaining formulas, and compliance guarantees, see [`SECURITY.md`](file:///Users/princemahto/Downloads/SatyaScan/SECURITY.md).
