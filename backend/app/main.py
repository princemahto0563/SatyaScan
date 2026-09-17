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
    auth, screenings, cases, audit, reports, watchlist, analytics
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


@app.get("/health", tags=["System"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "service": "SatyaScan Screening Engine",
        "version": settings.VERSION,
        "mode": "PROTOTYPE_OPERATIONAL"
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
