# SatyaScan Controlled Evaluation Dataset & Reference Directory

Evaluation images are intentionally excluded from source control because they contain identity-document and biometric content.

## Directory Structure

```
data/
├── README.md                           # This document (tracked)
├── metadata/
│   ├── reference_manifest.schema.json  # Reference manifest JSON schema (tracked)
│   ├── reference_manifest.local.json   # Local dataset manifest with SHA-256 hashes (git-ignored)
│   └── evaluation_results.json         # Automated evaluation report (tracked, no PII)
├── evaluation_input/                   # Raw uploaded evaluation material (git-ignored)
├── reference/                          # Cropped & isolated baseline documents (git-ignored)
│   ├── passports/
│   └── visas/
├── mutations/                          # Controlled evaluation tampering variants (git-ignored)
│   ├── field_tampering/
│   ├── face_replacement/
│   ├── mrz_tampering/
│   ├── date_tampering/
│   ├── document_number_tampering/
│   ├── visa_tampering/
│   └── combined_tampering/
├── genuine/                            # Pre-existing synthetic demo fixtures (tracked)
├── tampered/                           # Pre-existing synthetic demo fixtures (tracked)
├── masks/                              # Ground truth masks (tracked)
└── selfies/                            # Live selfie fixtures (tracked)
```

## Security and Privacy Policy

1. **Zero Raw PII in Source Control:** No real personal identification numbers, unmasked names, dates of birth, or biometric face descriptors are committed to GitHub.
2. **Deterministic Hashing:** All reference baselines and evaluation inputs are identified exclusively by cryptographic SHA-256 digests and anonymous internal identifiers (`PERSON-001`, `PERSON-002`).
3. **Reproducibility:** Controlled mutations are generated deterministically from local reference documents for automated regression testing and pipeline evaluation.
