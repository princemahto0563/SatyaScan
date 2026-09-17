# SatyaScan — Security Policy & Security Architecture Dossier
**Problem Statement:** SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division  
**System Name:** SatyaScan Document Integrity & Identity Verification Workstation  
**Classification:** Security-Hardened SIH Prototype  
**Philosophy:** Secure by Default · Privacy by Design · Auditable · Explainable  

---

## Security Controls — Judge Summary

An executive summary of defensive security controls implemented in the SatyaScan SIH prototype:

| Security Domain | Implemented Prototype Control | Concrete Code Reference |
| :--- | :--- | :--- |
| **Authentication** | JWT Bearer authentication (`HS256`) with strict signature, expiry, and format validation. Seamless in-memory token manager in client. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L40-L115), [`frontend/src/lib/api.ts`](file:///Users/princemahto/Downloads/SatyaScan/frontend/src/lib/api.ts#L17-L65) |
| **Password Security** | Direct `bcrypt` password hashing with cost factor 12. Password values never logged or returned in responses. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L25-L38) |
| **Authorization / RBAC** | Role-Based Access Control (`OFFICER`, `SUPERVISOR`, `ADMIN`). Sensitive administrative actions (e.g. watchlist additions) restricted to `SUPERVISOR`+. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L118-L128), [`backend/app/api/v1/endpoints/watchlist.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/api/v1/endpoints/watchlist.py#L32-L49) |
| **File Upload Security** | 10MB upload cap, strict magic header validation (`JPEG`, `PNG`, `WEBP`), PIL/OpenCV structural decode verification, and dimension caps (`<= 5000px` / 25M pixels) for decompression bomb protection. | [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L182-L252) |
| **Filesystem Isolation** | User-controlled filenames discarded; UUID-only randomized storage filenames (`doc_{uuid}.jpg`); path traversal sequences stripped. Static `/storage` route completely removed. | [`backend/app/api/v1/endpoints/screenings.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/api/v1/endpoints/screenings.py#L55-L75), [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L125-L135) |
| **API & CORS Security** | Backend Pydantic validation on all requests; restricted CORS whitelist without wildcard credentials; in-memory sliding window rate limiting on sensitive routes. | [`backend/app/core/rate_limiter.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/rate_limiter.py#L20-L75), [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L115-L125) |
| **HTTP Defense Headers** | Custom middleware injecting `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`. | [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L100-L113) |
| **Privacy & PII Protection** | Zero client-side storage of biometrics in `localStorage` or `sessionStorage`. Service worker strictly excludes sensitive media, reports, and API responses. PII masking (`mask_document_number`, `mask_full_name`, `mask_date_of_birth`). | [`frontend/public/sw.js`](file:///Users/princemahto/Downloads/SatyaScan/frontend/public/sw.js#L25-L42), [`backend/app/core/security.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/core/security.py#L131-L175) |
| **Audit Integrity** | SHA-256 cryptographically chained ledger where each event hashes `previous_hash`, `timestamp`, `actor`, `event_type`, and `payload_hash`. Retroactive modifications immediately trigger verification failure. | [`backend/app/services/audit_service.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/audit_service.py#L25-L135) |
| **Database Security** | SQLAlchemy parameterized queries / ORM preventing SQL injection; controlled transaction rollback on exceptions. No exposure of SQLite file via static routes. | [`backend/app/models/database.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/models/database.py#L165-L188) |
| **Error Security** | Client-safe error messages with masked technical details; diagnostic stack traces logged securely server-side; global exception handler prevents traceback leakage. | [`backend/app/main.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/main.py#L125-L135), [`backend/app/services/orchestrator.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/orchestrator.py#L100-L135) |
| **Report / PDF Safety** | ReportLab PDF generator safely escapes all dynamic field strings, risk findings, and IDs with `html.escape()`, preventing XML parsing crashes and markup injection. | [`backend/app/services/report_generator.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/report_generator.py#L150-L285) |
| **Offline Architecture** | Completely local inference pipeline (PaddleOCR/Tesseract, OpenCV ELA, Cosine Similarity, FAISS index). Zero mandatory external cloud AI APIs; sensitive identity assets remain local to workstation. | [`backend/app/services/orchestrator.py`](file:///Users/princemahto/Downloads/SatyaScan/backend/app/services/orchestrator.py#L40-L85) |

---

## 1. Threat Model

The SatyaScan workstation is engineered to operate in high-throughput border checkpoints and security stations (e.g. Sashastra Seema Bal frontier checkpoints). The threat model evaluates threats across 13 core vectors:

```
[External Attacker / Disguised File]
         │
         ├── (T-01: Malicious Polyglot) ──────► Magic Bytes + PIL Image Verify
         ├── (T-02: Decompression Bomb) ──────► Dimension Caps (<=5000px, 25M px)
         ├── (T-03: Path Traversal) ──────────► Basename Isolation + UUID File Paths
         ├── (T-04: Static Exposure) ─────────► Closed /storage static route
         └── (T-06: Brute Force Login) ───────► In-Memory Sliding Window Rate Limiting (10/min)

[Network / Transport Boundary]
         ├── (T-07: Forged / alg=none JWT) ───► Explicit HS256 validation + Signature check
         ├── (T-11: Stack Trace Leakage) ─────► Global Sanitized Error Handler
         └── (T-12: Cross-Origin Spoofing) ───► Strict Origin Whitelist (No wildcard credentials)

[Checkpoint Workstation / Storage]
         ├── (T-05: Privilege Escalation) ────► RBAC (OFFICER vs SUPERVISOR vs ADMIN)
         ├── (T-08: Biometric Caching) ───────► In-memory tokens; SW excludes all media
         ├── (T-09: PDF XML Injection) ───────► Complete html.escape() across report cells
         └── (T-10: Database Tampering) ──────► SHA-256 Cryptographically Chained Ledger
```

---

## 2. Authentication & Checkpoint Binding Architecture

1. **Checkpoint Identity & Workstation Binding**:
   - Each border station operates under a dedicated checkpoint identity.
   - 8 canonical border checkpoints are configured for the SIH prototype:
     1. Delhi Airport Immigration Checkpoint (`CP-DEL-AIR`, `delhi_airport`)
     2. Attari Border Checkpoint (`CP-ATTARI`, `attari_border`)
     3. Raxaul Border Checkpoint (`CP-RAXAUL`, `raxaul_border`)
     4. Jogbani Border Checkpoint (`CP-JOGBANI`, `jogbani_border`)
     5. Sunauli Border Checkpoint (`CP-SUNAULI`, `sunauli_border`)
     6. Rupaidiha Border Checkpoint (`CP-RUPAIDIHA`, `rupaidiha_border`)
     7. Panitanki Border Checkpoint (`CP-PANITANKI`, `panitanki_border`)
     8. Petrapole Border Checkpoint (`CP-PETRAPOLE`, `petrapole_border`)
   - **Strict Checkpoint-User Binding**: When an officer selects a checkpoint during login, the system verifies that the operator username belongs to that checkpoint. Mismatched credentials are rejected with HTTP 401 (`"Invalid checkpoint credentials."`).
   - Successful authentications record an immutable `LOGIN_SUCCESS` event in the cryptographic audit ledger.

2. **Password Security**:
   - Stored strictly as `bcrypt` hashes with cost factor 12.
   - Passwords are never logged, displayed, or serialized into responses.
   - Input passwords truncated to standard 72-byte bcrypt limit to prevent memory-exhaustion hashing attacks.
   - Demo password for canonical checkpoints is `Demo@123` (bcrypt-hashed).

3. **Timing-Insensitive Error Messaging**:
   - Login failures return generic: `"Invalid username or password credentials."` or `"Invalid checkpoint credentials."`
   - Prevents username enumeration.

4. **Demo Credential Disclosure**:
   - All checkpoint accounts and seed credentials (`officer` / `officer123`, `supervisor` / `super123`) are explicitly flagged in code, UI, and documentation as **EVALUATION / DEMO ONLY**.

---

## 3. JWT & Session Security

1. **Cryptographic Algorithm**:
   - Hardcoded to `HS256` explicitly.
   - Rejects unsigned tokens or tokens with `alg="none"`.
   - Encodes checkpoint metadata (`checkpoint_id`, `checkpoint_name`) in the signed payload.

2. **Key Hygiene**:
   - `.env.example` contains placeholder tokens instead of real production keys.
   - `JWT_SECRET` is drawn from the environment variable, with development fallback.
   - When running in production (`ENVIRONMENT=production` or `STRICT_AUTH=true`), unauthenticated requests are strictly rejected with `401 Unauthorized`.

3. **Token Storage & XSS Mitigation**:
   - The Next.js frontend maintains the active token in **JavaScript memory (closure scope)**.
   - Neither the JWT token nor biometric data is written to `localStorage` or `sessionStorage`.
   - Workstation session terminates cleanly on Logout or on token expiry (HTTP 401 triggers immediate return to checkpoint login screen).

---

## 4. Authorization & RBAC

Endpoints enforce role-based segregation of duties:

| Role | Permitted Actions | Prohibited Actions |
| :--- | :--- | :--- |
| **OFFICER** | Run document screenings, view assigned cases, stream media assets, download PDF dossiers, verify audit chains. | Cannot add watchlist records, cannot alter system roles. |
| **SUPERVISOR** | All Officer capabilities + Add/modify reference watchlist records, notarize audit roots, review escalated cases. | Cannot modify immutable audit ledger records. |
| **ADMIN** | System administration, user provisioning, station configuration. | Cannot retroactively modify historical audit records. |

---

## 5. File Upload & Resource Exhaustion Defense

Document and selfie uploads undergo multi-layer verification before hitting the filesystem or AI pipelines:

1. **File Size Enforcement**: Caps file payload at `10 MB` (HTTP 413 on violation).
2. **Extension Whitelist**: Only `.jpg`, `.jpeg`, `.png`, `.webp` allowed.
3. **Magic Byte Verification**: Verifies magic bytes (`\xFF\xD8\xFF` for JPEG, `\x89PNG` for PNG, `RIFF...WEBP` for WebP).
4. **Structural Image Decode Verification**: Decodes the byte stream using `PIL.Image.open().verify()` to detect truncated or corrupted files.
5. **Decompression Bomb Protection**:
   - `PIL.Image.MAX_IMAGE_PIXELS = 25_000_000`.
   - Dimension ceiling: maximum width `<= 5000px`, maximum height `<= 5000px`, and total pixels `<= 25,000,000`.
   - Rejects oversized dimensions with user-safe message: `"Document image exceeds the permitted processing dimensions."`
6. **Filesystem Sanitization**:
   - User filenames are sanitized with `sanitize_filename` (stripping directory traversal `../` or special characters).
   - Saved to filesystem using random UUIDs (`doc_{uuid4}.jpg`), eliminating arbitrary file overwrites and path traversal.

---

## 6. Static Route Removal & Media Authorization

- **Vulnerability Remediated**: The unauthenticated static directory mount `app.mount("/storage", ...)` was **completely removed**.
- **Controlled Streaming**: Raw passport document images, live selfie captures, and ELA heatmaps are accessible exclusively via the authenticated endpoint `/api/v1/screenings/media/{screening_id}/{media_type}`.
- Path traversal verification ensures real filesystem paths remain strictly within server-controlled directories.

---

## 7. PII & Biometric Privacy

1. **Data Minimization**:
   - Sensitive document numbers are masked in database summaries and logs (e.g. `Z12****67`).
   - Names and DOBs are masked in public displays (`A****N S****A`, `1990-**-**`).
2. **Client-Side Privacy Boundary**:
   - The browser Service Worker (`public/sw.js`) intercepts all network requests and explicitly excludes `/api/`, `/storage/`, `/reports/`, `/media/`, `selfie`, `passport`, `heatmap`, and `pdf` from browser caching.
   - PII and biometric representations are never stored in browser offline caches.

---

## 8. Audit Trail Integrity

The SatyaScan audit trail uses append-only cryptographic hash chaining:

$$\text{Chain String} = \text{previous\_hash} \,\|\, \text{timestamp} \,\|\, \text{actor} \,\|\, \text{event\_type} \,\|\, \text{payload\_hash}$$
$$\text{Event Hash} = \text{SHA-256}(\text{Chain String})$$

- **Integrity Guarantee**: If any historical row's payload, timestamp, or actor is modified, recomputing the chain from genesis produces a hash mismatch, alerting operators to data tampering.
- **Local Cryptographic Notarization Adapter**: Generates deterministic notarization receipts certifying the state of the audit chain head.

---

## 9. Secure Error Handling

1. **Server-Side Diagnostics**: Full tracebacks logged via Python `logging` with level `ERROR`.
2. **Client-Facing Sanitization**: Clients receive standardized, safe messages:
   - `"Screening could not be completed due to an internal processing error. Please retry or contact the administrator."`
   - No filesystem paths, database queries, or module structures are disclosed.
3. **State Guarantee**: In the event of a pipeline failure, transactions are rolled back, and the screening status is persisted as `FAILED` to prevent the frontend from remaining indefinitely stuck in a `PROCESSING` state.

---

## 10. Known Limitations of the Prototype

1. **In-Memory Rate Limiting**: The sliding-window rate limiter is stored in application memory. In a multi-node, load-balanced deployment, rate limits are not shared across processes without a distributed cache (e.g., Redis).
2. **Local Cryptographic Notarization**: The current blockchain adapter creates deterministic local cryptographic receipts; it does not commit live transactions to an external public or consortium network.
3. **Embedded Database**: Default execution utilizes local SQLite (`satyascan.db`). File-level access controls depend on operating system file permissions.

---

## 11. Production Hardening Requirements

Prior to real-world operational border deployment, the following additional controls are recommended:

1. **TLS / HTTPS**: Deploy behind a TLS-terminating reverse proxy (Nginx / Envoy) with strict HSTS (`max-age=31536000; includeSubDomains; preload`).
2. **External Identity Provider (IdP)**: Connect authentication to government enterprise IdPs (e.g., SAML 2.0 / OpenID Connect / PKI smart cards).
3. **Hardware Security Module (HSM)**: Store JWT signing keys and cryptographic audit anchor keys within an HSM / TPM.
4. **PostgreSQL with At-Rest Encryption**: Migrate from SQLite to PostgreSQL with transparent data encryption (TDE) and encrypted storage volumes.
5. **Automated Biometric Purge / Data Retention Policies**: Enforce statutory retention schedules (e.g., automated purge of raw biometric imagery after 30 days).
6. **Distributed Rate Limiter**: Upgrade in-memory rate limiting to distributed Redis token buckets.
