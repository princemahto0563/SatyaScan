# SatyaScan: Technical Research Sources & Standards Reference

**Project:** SatyaScan — AI-Assisted Identity & Document Screening Platform  
**Problem Statement:** SIH26188 (Ministry of Home Affairs / Sashastra Seema Bal, Police II Division)  
**Document Classification:** Official Research & Technical Reference  
**Last Updated:** 2026-09-13  

---

## 1. Primary International Standards & Specifications

### 1.1 ICAO Doc 9303 — Machine Readable Travel Documents (MRTDs)
* **Source Name:** International Civil Aviation Organization (ICAO) Doc 9303, Part 4: Specifications for Machine Readable Passports (MRPs) — TD3 Size
* **Official URL:** https://www.icao.int/publications/pages/publication.aspx?docnum=9303
* **What Was Researched:**
  - Standard physical and visual geometry of TD3 Machine Readable Passports (nominal size 88.0 mm × 125.0 mm).
  - Machine Readable Zone (MRZ) specifications: 2 lines of 44 alphanumeric characters (OCR-B font).
  - Field positions for Line 1: Document type (`P<`), Issuing Country code (3-letter ICAO code, e.g., `IND`), Primary identifier (Surname), delimiter (`<<`), Secondary identifiers (Given names), padded with `<`.
  - Field positions for Line 2: Document number (positions 1–9), check digit (position 10), nationality (positions 11–13), Date of Birth in `YYMMDD` (positions 14–19), DOB check digit (position 20), Sex code (`M`/`F`/`<` at position 21), Date of Expiry in `YYMMDD` (positions 22–27), Expiry check digit (position 28), Optional personal/data field (positions 29–42), optional check digit (position 43), and Composite check digit (position 44).
  - Check Digit Calculation: Repeating 7-3-1 weight vector applied sequentially modulo 10. Alphanumeric values: `0-9` $\rightarrow$ 0–9, `A-Z` $\rightarrow$ 10–35, `<` $\rightarrow$ 0. Composite check digit computed over positions 1–10, 14–20, 22–43 of Line 2.
  - Character substitution pitfalls during OCR: `0` vs `O`, `1` vs `I`, `8` vs `B`, `5` vs `S`.
* **What Was Actually Used:**
  - Mathematical implementation of the 7-3-1 check-digit verification algorithm.
  - TD3 two-line MRZ parser extracting Document Number, Nationality, DOB, Sex, Expiry Date, Optional Data, and all 5 individual and composite check digits.
  - Visual Inspection Zone (VIZ) vs. MRZ cross-verification matrix (comparing visual OCR fields against decoded MRZ fields).
* **Date Checked:** 2026-09-13
* **Version Checked:** Doc 9303, Eighth Edition (2021 / current revisions)
* **Implementation Impact:** Forms the primary mathematical ground truth for Module 2 (Document Validation). Any mismatch between VIZ and MRZ or failure of an internal check digit triggers an immediate deterministic flag.
* **Important Limitations:** An MRZ checksum pass confirms mathematical internal consistency, but does NOT by itself prove the physical passport was issued by an authentic government authority. Tampering can occur where a forger generates a mathematically valid MRZ for a fictitious identity. Hence, MRZ validation is an essential necessary condition, but not a sufficient condition on its own.
* **License Considerations:** Free public standard published by ICAO.

---

### 1.2 Indian Passport & Border Travel Guidelines
* **Source Name:** Ministry of External Affairs (MEA), Government of India / Passport Seva
* **Official URL:** https://www.passportindia.gov.in / https://mea.gov.in
* **What Was Researched:**
  - Indian passport numbering convention: Typically 1 alphabet letter followed by 7 numeric digits (e.g. `Z1234567`, `A1234567`), total 8 characters padded to 9 with `<` in MRZ.
  - Machine Readable Passport booklet layout: Visual layout of laminated biodata page, ghost image placement, signature strip, and MRZ placement along the bottom margin.
  - Distinction between Official Law Enforcement Systems (IVFRT / C-PIMS) and prototype software.
* **What Was Actually Used:**
  - Document layout profiles and regex patterns for Indian passport identifiers in the document adapter architecture (`documents/passport/`).
  - Strict classification: **Prototype Rule / Configurable Rule** rather than claiming an unauthorized connection to Government of India live databases.
* **Date Checked:** 2026-09-13
* **Version Checked:** Passport Seva Public Guidelines 2025/2026
* **Implementation Impact:** Guided regex validation, date plausibility boundaries, and synthetic dataset schema generation.
* **Important Limitations:** Real Indian border checkpoints connect via secure NIC networks to the Immigration, Visa and Foreigners Registration & Tracking (IVFRT) system. In SatyaScan, watchlist and blacklist lookups run against a simulated **Prototype Reference Database** with synthetic demo records (e.g., `DEMO-001`).
* **License Considerations:** Public Indian government operational guidelines.

---

## 2. Computer Vision & OCR Libraries

### 2.1 PaddleOCR / PP-OCRv4 & Pytesseract Fallback
* **Source Name:** Baidu PaddleOCR
* **Official URL:** https://github.com/PaddlePaddle/PaddleOCR
* **What Was Researched:**
  - PP-OCRv4 pipeline: DBNet (Real-time Scene Text Detection) + Direction Classifier + SVTR (Scene Text Recognition).
  - CPU inference latency on Apple Silicon / x86_64 architectures.
  - Bounding box coordinates output, character recognition confidence scores ($0.0 - 1.0$), and multi-language capability.
  - Pytesseract / Google Tesseract OCR 5.x engine as an immediate resilient local fallback adapter.
* **What Was Actually Used:**
  - Multi-engine OCR adapter: attempts PaddleOCR inference; if models are downloading or unavailable in edge environments, gracefully falls back to Tesseract OCR (`/opt/homebrew/bin/tesseract`).
  - Text box extraction preserving bounding box polygons, normalized text, and genuine OCR confidence scores.
* **Date Checked:** 2026-09-13
* **Version Checked:** PaddleOCR 3.7+ / Tesseract 5.5.0
* **Implementation Impact:** Powers Module 1 (OCR Field Extraction). Provides bounding boxes and authentic confidence scores displayed in the UI.
* **Important Limitations:** Degraded resolution, heavy specular glare, or extreme perspective angles can drop character confidence below 0.60. The Quality Gate pre-screens images to prevent garbage-in, garbage-out.
* **License Considerations:** Apache License 2.0 (PaddleOCR & Tesseract).

---

### 2.2 OpenCV (Open Source Computer Vision)
* **Source Name:** OpenCV Library
* **Official URL:** https://opencv.org / https://github.com/opencv/opencv-python
* **What Was Researched:**
  - Image quality metrics: Laplacian variance for blur detection, intensity histogram analysis for overexposure/glare, contrast measurement via standard deviation of luminance.
  - Document boundary detection and perspective rectification via Hough lines and contour approximation (`cv2.findContours`, `cv2.approxPolyDP`).
  - Copy-Move Forgery Detection (CMFD): ORB (Oriented FAST and Rotated BRIEF) feature extractor, descriptor matching via Brute-Force or FLANN, spatial distance thresholding to reject localized self-matches.
  - High-pass filtering and residual noise variance analysis across segmented grid patches.
* **What Was Actually Used:**
  - Document Quality Gate (`ai/quality/`): Blur score (Laplacian variance), Glare score (luminance clipping percentage), Contrast & Brightness validation.
  - Forensic modules: Noise residual analysis (`ai/tamper/noise_residual.py`), Copy-move detector (`ai/tamper/copy_move.py`), Edge transition analysis (`ai/tamper/edge_analysis.py`).
* **Date Checked:** 2026-09-13
* **Version Checked:** OpenCV 5.0.0.93 / 4.x
* **Implementation Impact:** Powers the multi-signal forensic pipeline in Module 3 and the pre-OCR quality gate.
* **Important Limitations:** Copy-move keypoint matching may produce false positives on repetitive guilloche security patterns if spatial distance thresholds are too small. Calibration requires minimum Euclidean separation between matched keypoints.
* **License Considerations:** Apache License 2.0.

---

### 2.3 Pillow (PIL Fork) & Error Level Analysis (ELA)
* **Source Name:** Python Imaging Library (Pillow) & Krawetz Forensic Research
* **Official URL:** https://pillow.readthedocs.io / Dr. Neal Krawetz, "A Picture's Worth..." (Hacker Factor Solutions, 2007)
* **What Was Researched:**
  - Error Level Analysis theory: When a lossy JPEG image is re-compressed at a known quality level (e.g. 90%), regions that were recently pasted or modified have not reached an error equilibrium with the rest of the image, yielding distinct difference magnitudes.
  - Implementation details: In-memory JPEG recompression, pixel-wise absolute difference calculation, multiplier scaling (e.g. 10x-20x) to bring visual contrast to subtle compression artifacts, and color-mapped heatmap generation.
* **What Was Actually Used:**
  - Authentic ELA module (`ai/tamper/ela.py`): Generates normalized ELA difference arrays, computes mean and standard deviation of anomaly scores per region (biodata, portrait, signature, MRZ), and exports colorized forensic heatmaps for display in the UI.
* **Date Checked:** 2026-09-13
* **Version Checked:** Pillow 12.0.0
* **Implementation Impact:** Powers the flagship visual forensic view in the screening result console.
* **Important Limitations:** ELA is compression-history dependent. Re-saving an entire document image multiple times at high quality can attenuate ELA differences. ELA provides evidence of compression inconsistency, NEVER "proof of forgery" on its own.
* **License Considerations:** Historical PIL License / HPND.

---

## 3. Biometric & Face Verification

### 3.1 Biometric Embedding Formulation & Classical Gabor-LBP Implementation
* **Theoretical Reference Researched:** DeepInsight ArcFace Research (Deng et al., CVPR 2019)
* **Official URL:** https://github.com/deepinsight/insightface
* **What Was Researched:**
  - ArcFace loss function: Imposes an additive angular margin penalty on the target angle in normalized hypersphere feature space to maximize inter-class discrepancy and minimize intra-class variance.
  - 512-dimensional L2-normalized face embedding vectors.
  - Cosine similarity metric: $\cos(\theta) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$.
  - Facial landmark alignment (5 points: two eyes, nose tip, two mouth corners) for geometric normalization.
  - Threshold calibration: Cosine similarity $\ge 0.65$ represents strong biometric correlation; below $0.40$ indicates distinct individuals.
* **What Was Actually Implemented in Prototype:**
  - Standardized local face verification service (`ai/face/face_verifier.py`): Haar cascade face detection, 512-dimensional handcrafted biometric feature descriptor (multi-scale block intensity pooling, 8-orientation Gabor wavelet bank, and LBP histogram normalized to unit hypersphere), and authentic cosine similarity calculation.
  - **Important Architectural Note**: The deployed prototype uses a zero-cloud, zero-heavy-dependency classical CV pipeline (OpenCV) rather than loading a deep neural network runtime (ONNX / InsightFace / PyTorch) to ensure universal compatibility across low-spec air-gapped border checkposts.
  - Separate Visible Appearance Variation analyzer: Evaluates facial hair, lighting disparity, and pose differences independently from embedding similarity.
* **Date Checked:** 2026-09-13
* **Implementation Impact:** Powers Module 4 (Face Verification). Strictly separates identity similarity from natural appearance variations (beard growth, aging, eyewear).
* **Important Limitations:** Synthetic vector avatar drawings lack natural facial photographic textures, resulting in high baseline correlation across avatars. Real photographic images should be used for production biometric validation.

---

## 4. Vector Search & Multi-Identity Detection

### 4.1 FAISS (Facebook AI Similarity Search)
* **Source Name:** Meta AI Research FAISS
* **Official URL:** https://github.com/facebookresearch/faiss
* **What Was Researched:**
  - Dense vector indexing and similarity search in high-dimensional Euclidean/Inner Product space.
  - `IndexFlatIP`: Computes exact inner product on unit-normalized vectors (mathematically identical to Cosine Similarity) with sub-millisecond retrieval on galleries up to tens of thousands of vectors.
* **What Was Actually Used:**
  - Multi-Identity Indexer (`ai/duplicate/indexer.py`): Maintains an in-memory index of synthetic reference identity embeddings. Flags cases where a scanned face exhibits high cosine similarity ($\ge 0.75$) with an existing record bearing a different primary identifier or document ID.
* **Date Checked:** 2026-09-13
* **Version Checked:** FAISS CPU 1.10+
* **Implementation Impact:** Directly addresses the SIH problem statement requirement: "Multiple identities used by the same person".
* **Important Limitations:** The index operates exclusively on fictional synthetic reference records in prototype mode.
* **License Considerations:** MIT License.

---

## 5. Security, Cryptography & Audit Logging

### 5.1 Tamper-Evident SHA-256 Hash Chain & OWASP Standards
* **Source Name:** OWASP Secure Coding Practices & NIST FIPS 180-4 (Secure Hash Standard)
* **Official URL:** https://owasp.org / https://csrc.nist.gov/publications/detail/fips/180-4/final
* **What Was Researched:**
  - Merkle-Damgård hash chains: Linking sequential state transitions such that $H_i = \text{SHA256}(H_{i-1} \parallel \text{Payload}_i \parallel \text{Timestamp}_i \parallel \text{Actor}_i)$.
  - Any retroactive modification to record $j$ ($j < i$) invalidates all subsequent hash digests $H_k$ ($k \ge j$).
  - OWASP Top 10 API Security: File upload validation (magic bytes, MIME type, file size caps, rejection of executable polyglots), PII masking (e.g. `X12****67`), role-based access control (RBAC), and JWT token expiration.
* **What Was Actually Used:**
  - Audit Trail Service (`backend/services/audit_service.py`): Immutable append-only audit ledger with cryptographic hash chaining.
  - Audit verification endpoint: Recalculates and verifies chain integrity from genesis block to current head.
  - Blockchain Adapter Interface (`backend/services/blockchain_adapter.py`): Exposes anchor method for publishing periodic audit root hashes to external smart contracts.
* **Date Checked:** 2026-09-13
* **Version Checked:** SHA-256 (FIPS 180-4) / OWASP 2024 Guidelines
* **Implementation Impact:** Guarantees court-grade digital chain of custody for border screening events.
* **Important Limitations:** Blockchain anchoring notarizes the timestamp and hash of the audit trail; it does not store sensitive passenger PII or raw images on-chain.
* **License Considerations:** Public domain / NIST standard.

---

## 6. PDF Forensic Report Generation

### 6.1 ReportLab
* **Source Name:** ReportLab Core PDF Library
* **Official URL:** https://www.reportlab.com
* **What Was Researched:**
  - Programmatic generation of vector-quality PDF documents using Flowable elements, custom styles, tables, and embedded images.
  - Page-level cryptographic hashing and digital metadata stamping.
* **What Was Actually Used:**
  - Official ReportLab PDF exporter (`backend/services/report_generator.py`): Generates a multi-page border security screening case summary containing case header, document metadata, masked PII, forensic ELA & residual thumbnails, audit hash chain stamp, and officer verification signature box.
* **Date Checked:** 2026-09-13
* **Version Checked:** ReportLab 5.0.1
* **Implementation Impact:** Delivers the required exportable case file artifact for downstream judicial or border investigation teams.
* **Important Limitations:** PDFs are generated server-side and streamed securely with Content-Disposition headers.
* **License Considerations:** BSD License (ReportLab Open Source).

---

## 7. Frontend Framework & PWA

### 7.1 Next.js 15, Tailwind CSS, Lucide, Recharts & PWA
* **Source Name:** Vercel Next.js / W3C Web App Manifest
* **Official URL:** https://nextjs.org / https://www.w3.org/TR/appmanifest/
* **What Was Researched:**
  - App Router architecture, server/client component boundaries, dynamic metadata.
  - PWA service worker lifecycle, offline application shell caching, installability manifests.
  - Recharts radar and area charts for multi-dimensional risk factor decomposition.
* **What Was Actually Used:**
  - Next.js frontend with Tailwind CSS, custom dark border-security workstation theme, responsive grid layouts, react-webcam live feed, and PWA manifest (`manifest.json` and service worker).
* **Date Checked:** 2026-09-13
* **Version Checked:** Next.js 15+ / React 19 / Tailwind CSS 4+
* **Implementation Impact:** Provides an operational, command-center UI tailored for high-throughput checkpoint environments.
* **Important Limitations:** In offline mode, the cached PWA shell alerts the operator that AI inference services require server network connectivity.
* **License Considerations:** MIT License.
