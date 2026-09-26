"""
SatyaScan Backend Main Application
FastAPI Server for Document Integrity & Identity Verification Workstation
SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division

Security Hardening:
- Restricted CORS whitelist (no wildcard with credentials)
- Custom Security Headers Middleware (nosniff, DENY, referrer policy, permissions policy)
- Complete removal of /storage static file mount (prevents unauthorized access to uploads & reports)
- Safe error handling preventing Python stack trace leakage
- Clear labelling of demo seed credentials
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import logging

from backend.app.core.config import settings
from backend.app.models.database import init_db, SessionLocal, User, ReferenceWatchlist
from backend.app.core.security import get_password_hash
from backend.app.core.checkpoints import seed_checkpoints
from backend.app.api.v1.endpoints import (
    auth, screenings, cases, audit, reports, watchlist, analytics, blockchain
)

logger = logging.getLogger("satyascan.server")


def seed_initial_demo_data():
    """
    EVALUATION / DEMO ONLY:
    Seeds default synthetic demo users, canonical checkpoints, and reference watchlist records.
    Production systems must provision users through secure identity providers.
    """
    db = SessionLocal()
    try:
        # Seed canonical border checkpoints and checkpoint users (EVALUATION ONLY)
        seed_checkpoints(db)

        # Seed default demo users (EVALUATION ONLY)
        existing_officer = db.query(User).filter(User.username == "officer").first()
        if not existing_officer:
            officer = User(
                username="officer",
                email="officer@satyascan.gov.in",
                hashed_password=get_password_hash("officer123"),
                role="OFFICER",
                full_name="Inspector Rajesh Kumar",
                badge_number="SSB-DEL-4092",
                checkpoint_id="CP-DEL-AIR",
                checkpoint_name="Delhi Airport Immigration Checkpoint",
                location="Delhi Airport (IGI)"
            )
            supervisor = User(
                username="supervisor",
                email="supervisor@satyascan.gov.in",
                hashed_password=get_password_hash("super123"),
                role="SUPERVISOR",
                full_name="Assistant Commandant Anita Roy",
                badge_number="SSB-HQ-1044"
            )
            db.add(officer)
            db.add(supervisor)
            db.commit()

        # Seed initial synthetic watchlist (EVALUATION ONLY)
        existing_wl = db.query(ReferenceWatchlist).first()
        if not existing_wl:
            wl1 = ReferenceWatchlist(
                document_id="DEMO-WATCH-01",
                full_name="VIKRAM SINGH",
                nationality="IND",
                reason="Flagged in simulated financial fraud lookout circular.",
                risk_category="LOOKOUT_CIRCULAR",
                status="ACTIVE"
            )
            wl2 = ReferenceWatchlist(
                document_id="Z9999999",
                full_name="UNKNOWN HOLDER",
                nationality="IND",
                reason="Simulated reported lost or stolen passport blank.",
                risk_category="STOLEN_PASSPORT",
                status="ACTIVE"
            )
            db.add(wl1)
            db.add(wl2)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("[SatyaScan Backend] Initializing database and security models...")
    init_db()
    seed_initial_demo_data()
    logger.info("[SatyaScan Backend] Ready for automated document screening requests.")
    yield
    # Shutdown
    logger.info("[SatyaScan Backend] Shutting down...")


app = FastAPI(
    title="SatyaScan API",
    description="AI-Based Fake Identity & Document Screening System (SIH26188 · Sashastra Seema Bal, Ministry of Home Affairs)",
    version=settings.VERSION,
    lifespan=lifespan
)

# 1. Defense-in-Depth HTTP Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(), microphone=()"
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    # HSTS only when served over HTTPS (prevents breaking local HTTP development)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# 2. Strict CORS Middleware: Whitelisted origins only (No wildcard with credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["X-Files-Time", "X-Class-Time", "X-Proc-Time", "X-Total-Server-Time"],
)


# 3. Global Exception Handlers (Never expose Python tracebacks to clients)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[SatyaScan Unhandled Exception] Path: {request.url.path} | Error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please retry or contact the administrator."}
    )


# 4. Mount Routers under API v1
api_prefix = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=api_prefix)
app.include_router(screenings.router, prefix=api_prefix)
app.include_router(cases.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(watchlist.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
app.include_router(blockchain.router, prefix=api_prefix)


@app.get("/health", tags=["System"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["System"])
def health_check():
    from ai.ocr.ocr_engine import PADDLE_AVAILABLE
    return {
        "status": "HEALTHY",
        "service": "SatyaScan Screening Engine",
        "version": settings.VERSION,
        "commit": os.getenv("RENDER_GIT_COMMIT", "local-dev")[:7],
        "paddle_available": PADDLE_AVAILABLE,
        "mode": "PROTOTYPE_OPERATIONAL"
    }


@app.get("/diag", tags=["System"])
def diagnostic_check():
    import pytesseract
    import numpy as np
    import cv2
    import time
    from ai.ocr.ocr_engine import PADDLE_AVAILABLE, RAPID_AVAILABLE, OCREngine

    dummy = np.full((600, 900, 3), 255, dtype=np.uint8)
    cv2.putText(dummy, "PASSPORT P<INDSHARMA<<ARJUN", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(dummy, "P<INDSHARMA<<ARJUN<<<<<<<<<<<<<<<<<<<<<<<<<<", (40, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(dummy, "Z1234567<1IND9205141M2805139<<<<<<<<<<<<<<<2", (40, 520), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    t0 = time.perf_counter()
    txt = pytesseract.image_to_string(dummy)
    tess_time = time.perf_counter() - t0

    eng = OCREngine()
    t1 = time.perf_counter()
    eng_res = eng.process_image(dummy)
    eng_time = time.perf_counter() - t1

    from ai.face.service import FaceVerificationService
    fvs = FaceVerificationService()
    arjun_doc = cv2.imread("data/genuine/case01_genuine_arjun.jpg")
    arjun_live = cv2.imread("data/selfies/case01_selfie_arjun.jpg")
    doc_crop, doc_box, doc_q = fvs.detect_and_crop_face(arjun_doc, is_document=True) if arjun_doc is not None else (None, None, {})
    live_crop, live_box, live_q = fvs.detect_and_crop_face(arjun_live, is_document=False) if arjun_live is not None else (None, None, {})
    verify_res = fvs.verify("data/genuine/case01_genuine_arjun.jpg", "data/selfies/case01_selfie_arjun.jpg") if arjun_doc is not None and arjun_live is not None else {}

    return {
        "paddle_available": PADDLE_AVAILABLE or RAPID_AVAILABLE,
        "rapid_available": RAPID_AVAILABLE,
        "primary_ocr_object": (eng._rapid_ocr is not None) or (eng._paddle_ocr is not None),
        "tesseract_only_time": round(tess_time, 3),
        "engine_process_time": round(eng_time, 3),
        "engine_used": eng_res.get("engine"),
        "tesseract_text": txt.strip(),
        "total_lines": eng_res.get("total_lines_detected", 0),
        "mrz_lines_count": len(eng_res.get("mrz_candidate_lines", [])),
        "fields_extracted": sum(1 for v in eng_res.get("extracted_fields", {}).values() if v),
        "face_diagnostics": {
            "face_cascade_loaded": fvs.face_cascade is not None,
            "eye_cascade_loaded": fvs.eye_cascade is not None,
            "sface_version": fvs.provider.version,
            "arjun_doc_detected": doc_q.get("detected"),
            "arjun_doc_usable": doc_q.get("usable"),
            "arjun_doc_reasons": doc_q.get("reasons"),
            "arjun_live_detected": live_q.get("detected"),
            "arjun_verify_result": verify_res.get("verification_result"),
            "arjun_similarity": verify_res.get("similarity_score"),
            "arjun_recommendation": verify_res.get("recommendation"),
            "arjun_reason": verify_res.get("reason"),
        }
    }


# Serve canonical synthetic test cases & presets for UI demo (html=False prevents directory browsing)
# SENSITIVE /storage MOUNT IS COMPLETELY REMOVED FOR SECURITY.
# All document images and reports are served exclusively through authenticated API endpoints.
if os.path.exists(settings.DATA_DIR):
    app.mount("/data", StaticFiles(directory=settings.DATA_DIR, html=False), name="data")


@app.get("/", tags=["System"])
def root():
    return {
        "platform": "SatyaScan",
        "tagline": "Verify. Detect. Explain.",
        "description": "Document Integrity & Identity Verification Workstation",
        "problem_statement": "SIH26188",
        "docs_url": "/docs"
    }
