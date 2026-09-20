# SatyaScan — Formal Security Policy & Threat Model Architecture Dossier
**Problem Statement:** SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division  
**Theme:** Blockchain & Cybersecurity  
**System Name:** SatyaScan Document Integrity & Identity Verification Workstation  
**Classification:** Security-Hardened SIH Prototype  
**Philosophy:** Zero-Trust · Secure by Default · Privacy by Design · Defense-in-Depth · Cryptographically Auditable  

---

## Connected Platform Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       CYBERSECURITY LAYER                                         │
│  - Strict JWT (HS256) with Header Verification (alg=none & RS256 confusion rejected)             │
│  - Centralized RBAC (OFFICER, SUPERVISOR, ADMIN) + Fine-Grained Permissions (permissions.py)      │
│  - Server-Side Station Scoping: Station Isolation & IDOR Defense (check_checkpoint_access)        │
│  - Magic Bytes, Image Decode Integrity, and Decompression Bomb Defense (5000px / 25M px limit)    │
│  - HTTP Defense Headers (nosniff, DENY, referrer-policy) + Whitelisted CORS (No Wildcard)        │
│  - Thread-Safe Sliding Window Rate Limiting (Login: 10/min, Screening: 20/min, Reports: 30/min)  │
└────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                 │ Authenticated & Authorized Session
                                                 ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   DOCUMENT & IDENTITY SCREENING                                   │
│  - Input Validation & Anti-Spoofing: Client document_type and checkpoint_id strictly untrusted    │
│  - Classifier Gate: Real image classification (Passport/Visa only; Aadhaar/PAN/DL rejected)       │
│  - Classical Forensics: Error Level Analysis (ELA), Noise Residual, Copy-Move Cloned Region       │
│  - OCR Extraction & MRZ Verification: ICAO 9303 Doc 9303 TD3 7-3-1 Checksum & Cross-Validation   │
│  - Classical Face Verification: Gabor-LBP Cosine Similarity + FAISS Multi-Identity Re-use Search │
│  - Calibrated Risk Engine: Deterministic weighted risk score [0..100] and Recommendation Gate     │
└────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                 │ Evidence Serialization & Hashing
                                                 ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               LOCAL SHA-256 TAMPER-EVIDENT AUDIT                                  │
│  - Append-Only Cryptographically Chained Ledger (previous_hash || timestamp || payload_hash)      │
│  - Immutable Audit Events: DOC_UPLOAD, OCR_DONE, RISK_EVAL, ACCESS_DENIED, LOGIN_FAILURE, ...    │
│  - Retroactive Tamper Detection: verify_audit_chain detects altered rows, hashes, or payload edits│
└────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                 │ Cryptographic Digests (Zero PII)
                                                 ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        PERMISSIONED BLOCKCHAIN ANCHOR (HYPERLEDGER FABRIC)                        │
│  - Private Consortium Ledger: satyascan-channel @ Org1MSP (Chaincode: screening_anchor.go)       │
│  - Core Privacy Principle: "Evidence stays off-chain. Cryptographic proof goes on-chain."         │
│  - On-Chain Anchors: Irreversible SHA-256 Document Hash + Canonical Result Hash (Zero PII)       │
│  - Honest Offline Detection: Returns status "UNAVAILABLE" when peer is unreachable (No fakes)    │
│  - Cross-Verification: verify_anchor compares local evidence digests against on-chain records     │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Executive Summary of Implemented Security Controls

| Security Domain | Implemented Prototype Control | Concrete Code Reference | Automated Test Suite |
| :--- | :--- | :--- | :--- |
| **Authentication** | JWT Bearer (`HS256`) with strict header inspection. Explicitly rejects `alg=none`, RS256/asymmetric confusion, expired tokens, and missing claims. Client uses in-memory closure tokens. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L45-L120) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L140-L215) (T-01, T-02) |
| **Password Security** | Direct `bcrypt` with explicit work factor 12. 72-byte truncation prevents memory exhaustion. Zero passwords/hashes returned in responses or logs. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L30-L44) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L525-L560) (T-10) |
| **Authorization / RBAC** | Centralized permissions framework (`backend/app/core/permissions.py`) with roles (`OFFICER`, `SUPERVISOR`, `ADMIN`). Strict privilege boundaries on watchlists and cases. | [`backend/app/core/permissions.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/permissions.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L220-L265) (T-03) |
| **Station Isolation (IDOR)** | Server-side checkpoint scoping via `check_checkpoint_access`. Officers strictly bound to own checkpoint; cross-station access forbidden (HTTP 403) and logged as `ACCESS_DENIED`. Supervisors possess multi-station oversight. | [`backend/app/core/permissions.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/permissions.py#L85-L141), [`backend/app/api/v1/endpoints/screenings.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/api/v1/endpoints/screenings.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L270-L370) (T-04) |
| **File Upload Defense** | 10MB payload cap, magic header byte verification (`JPEG`, `PNG`, `WEBP`), PIL/OpenCV structural decode check, and dimension ceilings (`<= 5000px`, 25M pixels) for decompression bomb defense. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L190-L267) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L375-L435) (T-05) |
| **Filesystem Isolation** | Directory traversal sequences stripped via `sanitize_filename`. User filenames replaced with randomized UUID paths (`doc_{uuid}.jpg`). Public static `/storage` route completely removed. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L180-L190), [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L170-L177) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L440-L465) (T-06, T-15) |
| **Rate Limiting (DoS)** | Thread-safe in-memory sliding window rate limiter on logins (10/min), screenings (20/min), and reports (30/min). Protects against credential stuffing and CPU exhaustion. | [`backend/app/core/rate_limiter.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/rate_limiter.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L470-L485) (T-07) |
| **Input Validation & SQLi** | Pydantic v2 schemas and strict regex validation (`^[A-Za-z0-9_-]{3,64}$`) on IDs; SQLAlchemy ORM parameterized queries prevent SQL injection. | [`backend/app/api/v1/endpoints/screenings.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/api/v1/endpoints/screenings.py#L34-L45) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L490-L505) (T-08) |
| **XSS & PDF Escaping** | Full HTML/XML entity sanitization (`html.escape()`) across all dynamic fields, risk notes, and officer attributions in ReportLab PDF generation. | [`backend/app/services/report_generator.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/report_generator.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L510-L540) (T-09) |
| **CORS & Network** | Explicit CORS whitelist without wildcard credentials. Disallows `*` when credentials are required. | [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L129-L137) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L565-L575) (T-11) |
| **Privacy & PII Protection** | PII masking (`mask_document_number`, `mask_full_name`, `mask_date_of_birth`). Service worker explicitly excludes sensitive media, reports, and API caches. Automated pre-blockchain PII validator. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L135-L173), [`backend/app/services/fabric_service.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/fabric_service.py#L90-L116) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L580-L605) (T-12) |
| **Audit Integrity** | SHA-256 cryptographically chained ledger linking every event to the preceding event's hash. Verifies integrity from genesis to head. Audits `LOGIN_FAILURE`, `ACCESS_DENIED`, `WATCHLIST_CHANGE`. | [`backend/app/services/audit_service.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/audit_service.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L610-L660) (T-13) |
| **Permissioned Blockchain** | Hyperledger Fabric Go contract (`screening_anchor.go`) and Python gateway. Anchors deterministic document hash and result hash. Discrepancy detector flags alterations. Transparent offline fallback. | [`blockchain/chaincode/screening_anchor/screening_anchor.go`](file:///Users/princemahto/Downloads/SatyaScan/blockchain/chaincode/screening_anchor/screening_anchor.go), [`backend/app/services/fabric_service.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/fabric_service.py) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L665-L705) (T-14) |
| **HTTP Defense Headers** | Custom ASGI middleware injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`. | [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L116-L127) | [`tests/test_cybersecurity_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_cybersecurity_hardening.py#L710-L725) (T-15) |
| **Error Handling & Traceback** | Global exception handlers log server-side diagnostics securely while returning standardized, non-leaking JSON error details to callers. | [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L140-L147) | [`tests/test_security_hardening.py`](file:///Users/princemahto/Downloads/SatyaScan/tests/test_security_hardening.py) |

---

## 2. Threat Model Matrix (T-01 to T-15)

The formal threat model analyzes each attack vector, attack surface, implemented defense, automated verification test, and residual risk:

| Threat ID | Threat Category | Attack Vector & Surface | Implemented Defense & Architecture | Automated Verification Test | Residual Risk & Production Hardening |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T-01** | Authentication Bypass | Direct API access without Bearer token or with forged header. | Strict mode (`STRICT_AUTH=True`) mandates valid Bearer tokens for all protected routes; prototype fallback strictly limited to evaluation. | `test_t01_strict_auth_rejects_missing_token`, `test_t01_malformed_bearer_token_rejected` | Low. Production uses PKI smart cards or enterprise IdP. |
| **T-02** | JWT Algorithm Confusion / Tampering | Attacker strips signature (`alg="none"`) or uses public key for HMAC confusion. | Strict pre-decode header inspection requires `alg == "HS256"`. Rejects `none`, RS256, and mismatched algorithms before decoding. | `test_t02_jwt_alg_none_rejected`, `test_t02_jwt_algorithm_confusion_rejected`, `test_t02_jwt_signature_tampering_rejected` | Negligible. Header inspection prevents library-level algorithm confusion. |
| **T-03** | Privilege Escalation | Border officer attempts to add/modify watchlist entries or tamper with system roles. | Centralized Role-Based Access Control (`require_role(["SUPERVISOR", "ADMIN"])`). Officer receives immediate HTTP 403. | `test_t03_rbac_officer_cannot_add_watchlist`, `test_t03_rbac_supervisor_can_add_watchlist` | Negligible. Permissions enforced server-side. |
| **T-04** | Insecure Direct Object Reference (IDOR) | Delhi Officer queries or updates Raxaul border screening dossier, media asset, or PDF. | Server-side checkpoint scoping (`check_checkpoint_access`). Verifies `user.checkpoint_id == screening.checkpoint_id`. Mismatch raises HTTP 403 and records `ACCESS_DENIED` in audit ledger. | `test_t04_delhi_officer_denied_raxaul_screening_detail`, `test_t04_delhi_officer_denied_raxaul_media_asset`, `test_t04_station_isolation_logs_access_denied_audit` | Negligible. Strict station isolation enforced on all entity lookups. |
| **T-05** | Malicious Upload & Polyglots | Attacker uploads malicious script disguised as JPEG, or 100MB file, or 50,000px decompression bomb. | 10MB size cap, magic bytes inspection (`\xFF\xD8\xFF`, `\x89PNG`, `RIFF...WEBP`), PIL decode verification, and 5000px / 25M pixel dimension ceilings. | `test_t05_upload_fake_mime_polyglot_rejected`, `test_t05_upload_corrupt_image_bytes_rejected`, `test_t05_upload_decompression_bomb_rejected` | Low. Antivirus scanning container recommended for enterprise multi-tenant scale. |
| **T-06** | Directory & Path Traversal | Filename containing `../../../../etc/passwd` in upload or media streaming route. | `sanitize_filename` strips path characters; disk files saved as random UUIDs (`doc_{uuid}.jpg`); realpath check restricts access to storage directory. | `test_t06_path_traversal_filename_sanitized`, `test_t06_media_path_traversal_prevented` | Negligible. UUID filenames completely decouple upload names from disk. |
| **T-07** | Denial of Service (DoS) | Attacker floods login or screening endpoint to exhaust CPU or OCR worker resources. | In-memory thread-safe sliding window rate limiting (Login: 10/min, Screening: 20/min, Reports: 30/min). HTTP 429 returned on breach. | `test_t07_rate_limiter_blocks_excessive_login_attempts` | Medium. For multi-replica Kubernetes clusters, swap in-memory limiter with Redis sliding window. |
| **T-08** | SQL Injection | Attacker supplies `' OR '1'='1` in screening ID or query parameters. | Strict regex validation (`^[A-Za-z0-9_-]{3,64}$`) on IDs; all queries use SQLAlchemy ORM parameterized statements. | `test_t08_sql_injection_in_screening_id_handled` | Negligible. Parameterized ORM prevents query injection. |
| **T-09** | XSS / Template Injection | Attacker crafts MRZ/visual name with `<script>` tags to execute during PDF generation or UI render. | ReportLab generator explicitly escapes all dynamic text with `html.escape()`. React escapes JSX text bindings by default. | `test_t09_xss_and_xml_in_pdf_report_sanitized` | Negligible. Complete escaping verified in PDF test. |
| **T-10** | Password Cracking | Brute-force credential stuffing or offline hash cracking via rainbow tables. | Direct `bcrypt` with cost factor 12 ($2^{12}$ iterations). Timing-safe generic error responses prevent username enumeration. | `test_t10_bcrypt_work_factor_12`, `test_t10_timing_safe_error_messages` | Low. Multi-factor authentication (MFA) recommended for production border officers. |
| **T-11** | CORS Misconfiguration | Attacker website initiates cross-origin authenticated requests from browser. | Explicit whitelist of allowed origins (`http://localhost:3000`, `http://127.0.0.1:3000`). Wildcard `*` strictly disallowed with credentials. | `test_t11_cors_disallows_wildcard_with_credentials` | Negligible. Strict origin matching enforced by FastAPI CORS middleware. |
| **T-12** | PII & Biometric Leakage | Passenger names, DOBs, passport numbers, or raw face crops leaked to logs or blockchain. | Masking functions for UI/logs (`Z12***67`, `A***N S****A`). Automated validator blocks PII keys from blockchain anchor payloads. | `test_t12_pii_masking_utilities`, `test_t12_zero_pii_in_fabric_anchor_payload` | Low. Ensure encrypted at-rest storage for primary database in production. |
| **T-13** | Audit Trail Tampering | Malicious insider alters database rows, changes timestamps, or deletes flagged screenings. | Cryptographically chained SHA-256 ledger. Each block links to previous hash. Verification algorithm detects any retroactively altered row or payload. | `test_t13_audit_trail_tamper_detection`, `test_t13_login_failure_event_recorded` | Low. Dual-notarization with Hyperledger Fabric seals hashes off-workstation. |
| **T-14** | Blockchain Anchor Forgery | Corrupt operator claims document was verified on-chain when evidence was tampered. | Hyperledger Fabric anchor stores deterministic SHA-256 document and result hashes. Verification detects discrepancy between local and ledger records. | `test_t14_blockchain_verification_detects_discrepancy` | Low. Requires consensus endorsement from peer organization. |
| **T-15** | Information Disclosure | Unhandled exception dumps Python tracebacks, module paths, or SQL queries to client. | Global ASGI exception handler catches unhandled exceptions, logs diagnostics securely, and returns standardized generic JSON error response. | `test_t15_security_headers_present`, `test_t15_static_storage_mount_closed` | Negligible. Diagnostic detail suppressed from public responses. |

---

## 3. Station Isolation & Checkpoint Binding Architecture

Border security requires that officer credentials and workstation activity are strictly scoped to their assigned station. SatyaScan enforces **server-side checkpoint isolation**:

### 1. Canonical Border Checkpoints
The SIH prototype configures 8 canonical operational stations representing key border posts and international immigration gates:

| Code | Checkpoint Name | Location | Default Operator Username |
| :--- | :--- | :--- | :--- |
| `CP-DEL-AIR` | Delhi Airport Immigration Checkpoint | Delhi Airport (IGI) | `delhi_airport` |
| `CP-ATTARI` | Attari Border Checkpoint | Attari, Punjab (Indo-Pak) | `attari_border` |
| `CP-RAXAUL` | Raxaul Land Customs Station | Raxaul, Bihar (Indo-Nepal) | `raxaul_border` |
| `CP-JOGBANI` | Jogbani Border Checkpoint | Jogbani, Bihar (Indo-Nepal) | `jogbani_border` |
| `CP-SUNAULI` | Sunauli Border Checkpoint | Sunauli, UP (Indo-Nepal) | `sunauli_border` |
| `CP-RUPAIDIHA`| Rupaidiha Border Checkpoint | Rupaidiha, UP (Indo-Nepal) | `rupaidiha_border` |
| `CP-PANITANKI`| Panitanki Border Checkpoint | Panitanki, WB (Indo-Nepal) | `panitanki_border` |
| `CP-PETRAPOLE`| Petrapole Integrated Check Post | Petrapole, WB (Indo-Bangladesh) | `petrapole_border` |

### 2. Strict Checkpoint-User Binding on Login
When authenticating at `/api/v1/auth/login`:
- If `checkpoint_id` is supplied, the system verifies that `user.checkpoint_id == checkpoint.id`.
- Mismatched logins are rejected with `HTTP 401 Unauthorized` and record a `LOGIN_FAILURE` audit ledger event.
- The verified `checkpoint_id` and `checkpoint_name` are sealed in the signed JWT payload.

### 3. Server-Side Checkpoint Isolation (`check_checkpoint_access`)
Every protected entity route (`GET /screenings/{id}`, `GET /screenings/media/{id}/{type}`, `GET /reports/{id}/pdf`, `GET /audit/{id}`, `PUT /cases/{id}/status`, `POST /blockchain/{id}/anchor`) invokes `check_checkpoint_access`:
- **For OFFICER**: The officer's `checkpoint_id` must match the screening's `checkpoint_id`. If an officer at Delhi attempts to access a dossier originating from Raxaul, the server raises `HTTP 403 Forbidden` and appends an `ACCESS_DENIED` audit event with the officer's badge, username, and attempted resource.
- **For SUPERVISOR / ADMIN**: Supervisory and administrative personnel possess authorized multi-station operational visibility across all checkpoints for oversight and escalation reviews.

---

## 4. Centralized Role-Based Access Control (RBAC)

Defined in [`backend/app/core/permissions.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/permissions.py):

```python
# Fine-Grained Permissions
PERM_SCREENING_CREATE = "screening:create"
PERM_SCREENING_VIEW = "screening:view"
PERM_CASE_REVIEW = "case:review"
PERM_MEDIA_ACCESS = "media:access"
PERM_REPORT_DOWNLOAD = "report:download"
PERM_AUDIT_VIEW = "audit:view"
PERM_AUDIT_VERIFY = "audit:verify"
PERM_BLOCKCHAIN_ANCHOR = "blockchain:anchor"
PERM_BLOCKCHAIN_VERIFY = "blockchain:verify"
PERM_WATCHLIST_VIEW = "watchlist:view"
PERM_WATCHLIST_MANAGE = "watchlist:manage"
PERM_ANALYTICS_VIEW = "analytics:view"
PERM_SYSTEM_ADMIN = "system:admin"
```

### Role-to-Permissions Mapping

| Permission | OFFICER | SUPERVISOR | ADMIN | Description |
| :--- | :---: | :---: | :---: | :--- |
| `screening:create` | ✓ | ✓ | ✓ | Submit documents and selfies for screening |
| `screening:view` | ✓ (scoped) | ✓ (global) | ✓ (global) | View completed screening dossiers |
| `media:access` | ✓ (scoped) | ✓ (global) | ✓ (global) | Stream original document/live/heatmap images |
| `report:download` | ✓ (scoped) | ✓ (global) | ✓ (global) | Download official ReportLab PDF reports |
| `audit:view` | ✓ (scoped) | ✓ (global) | ✓ (global) | View cryptographic audit ledger entries |
| `audit:verify` | ✓ (scoped) | ✓ (global) | ✓ (global) | Verify unbroken SHA-256 hash chain |
| `blockchain:anchor` | ✓ (scoped) | ✓ (global) | ✓ (global) | Anchor evidence hashes to Hyperledger Fabric |
| `blockchain:verify` | ✓ (scoped) | ✓ (global) | ✓ (global) | Verify local hashes against on-chain record |
| `watchlist:view` | ✓ | ✓ | ✓ | View synthetic reference watchlist entries |
| `case:review` | ✗ | ✓ | ✓ | Modify case status (CLEARED, ESCALATED, etc.) |
| `watchlist:manage` | ✗ | ✓ | ✓ | Add new watchlist records |
| `system:admin` | ✗ | ✗ | ✓ | System configuration and user provisioning |

---

## 5. Data Classification Policy

SatyaScan establishes a four-tier data classification policy enforcing privacy by design and data minimization:

| Classification Level | Examples | Storage Location | Protection Controls |
| :--- | :--- | :--- | :--- |
| **RESTRICTED — PII & Biometrics** | Raw passport document images, live selfies, face embeddings, full passenger names, DOBs, passport numbers. | **Local Workstation Only** (Never on-chain) | UUID filenames, no static route, PII masking (`Z12***67`), service worker cache exclusion. Excluded from blockchain payloads by automated validator. |
| **INTERNAL OPERATIONAL** | Extracted OCR fields, MRZ parsed lines, quality metrics, forensic anomaly heatmaps, risk scores, officer notes. | **Local Database & Reports** | JWT-authenticated REST endpoints, station-scoped IDOR checks, ReportLab HTML/XML escaping. |
| **AUDIT EVIDENCE — CRYPTOGRAPHIC** | SHA-256 document hash, canonical result hash, audit event hashes, chain digests. | **Local Ledger + Hyperledger Fabric** | Immutably chained in local database; anchored on-chain to private consortium channel (`satyascan-channel`). Zero PII. |
| **PUBLIC / DEMO CONTEXT** | Checkpoint list, system health check, supported document types (`PASSPORT`, `VISA`). | **Public Endpoints** | Read-only endpoints, sanitized responses, rate-limited against scraping. |

---

## 6. Two-Tier Provenance Architecture

```
Screening Complete ──► Compute Deterministic SHA-256 Digests
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Tier 1: Local SHA-256]         [Tier 2: Hyperledger Fabric]
   - Event-by-event chaining       - Off-workstation proof
   - Previous hash linkage         - satyascan-channel
   - Full operational lifecycle    - Zero PII (digests only)
   - Retroactive tamper detection  - Multi-peer endorsement
```

1. **Tier 1 — Local SHA-256 Cryptographic Hash Chain**:
   - Manages granular lifecycle events (`DOC_UPLOADED`, `CLASSIFIER_PASSED`, `QUALITY_ASSESSED`, `OCR_EXTRACTED`, `MRZ_VERIFIED`, `FORENSICS_COMPLETED`, `FACE_VERIFIED`, `RISK_EVALUATED`, `ACCESS_DENIED`, `LOGIN_FAILURE`, `WATCHLIST_CHANGE`).
   - Each event computes:
     $$\text{Chain String} = \text{screening\_id} \,\|\, \text{previous\_hash} \,\|\, \text{timestamp} \,\|\, \text{actor} \,\|\, \text{event\_type} \,\|\, \text{payload\_hash}$$
     $$\text{Event Hash} = \text{SHA-256}(\text{Chain String})$$
   - `verify_audit_chain` verifies link-by-link continuity from genesis ($0^{64}$) to head.

2. **Tier 2 — Hyperledger Fabric Blockchain Anchor**:
   - Permissioned smart contract [`blockchain/chaincode/screening_anchor/screening_anchor.go`](file:///Users/princemahto/Downloads/SatyaScan/blockchain/chaincode/screening_anchor/screening_anchor.go).
   - Anchors two deterministic SHA-256 digests:
     1. `document_hash`: SHA-256 of uploaded raw document bytes.
     2. `result_hash`: SHA-256 of canonical deterministic string (`screening_id|doc_hash|risk_band|checkpoint_id|1.0.0`).
   - **Zero PII**: Strictly validated by `FabricAnchorService.validate_no_pii_in_payload`.
   - **Graceful Fallback**: Returns `status: "UNAVAILABLE"` when peer is unreachable. Never fabricates fake transaction hashes.

---

## 7. Known Limitations of the Prototype

1. **In-Memory Rate Limiter**: The sliding-window rate limiter runs in the Python process memory. In a distributed multi-replica deployment, rate limits must be shared across pods using Redis.
2. **Local SQLite Primary Store**: The prototype uses SQLite with WAL mode. Enterprise production requires PostgreSQL with at-rest encryption (TDE).
3. **Hyperledger Fabric Docker Dependency**: Full peer consensus execution requires Docker and Fabric binaries. In host environments lacking Docker, the service gracefully reports `status: "UNAVAILABLE"` while local SHA-256 auditing remains 100% active.

---

## 8. Production Hardening Checklist

For transition from SIH prototype to operational border infrastructure:

- [ ] **TLS Termination**: Deploy behind Nginx / Envoy reverse proxy with TLS 1.3 and HSTS (`max-age=31536000; includeSubDomains; preload`).
- [ ] **Enterprise Identity Provider (IdP)**: Connect workstation login to MHA PKI smart cards or Government SSO (SAML 2.0 / OIDC).
- [ ] **Hardware Security Module (HSM)**: Store JWT private signing keys and blockchain transaction signing keys in a FIPS 140-2 Level 3 HSM.
- [ ] **Database Migration**: Migrate from SQLite to PostgreSQL with Transparent Data Encryption (TDE) and row-level security.
- [ ] **Distributed Cache**: Replace in-memory rate limiter with a Redis cluster sliding window (`redis.call('zremrangebyscore', ...)`).
- [ ] **Biometric Retention Schedule**: Implement automated TTL purge of raw facial imagery after statutory retention periods (e.g., 30 days).
- [ ] **Dedicated Hyperledger Fabric Orderers & Peers**: Deploy multi-node Raft ordering service with Org1MSP (SSB), Org2MSP (Bureau of Immigration), and Org3MSP (MHA).
