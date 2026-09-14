"""
SatyaScan Backend Main Application
FastAPI Server for AI-Assisted Identity & Document Screening Platform
SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from backend.app.core.config import settings
from backend.app.models.database import init_db, SessionLocal, User, ReferenceWatchlist
from backend.app.core.security import get_password_hash
from backend.app.api.v1.endpoints import (
    auth, screenings, cases, audit, reports, watchlist, analytics
)


def seed_initial_demo_data():
    """Seeds default demo users and synthetic watchlist records if not already present."""
    db = SessionLocal()
    try:
        # Seed default users
        existing_officer = db.query(User).filter(User.username == "officer").first()
        if not existing_officer:
            officer = User(
                username="officer",
                email="officer@satyascan.gov.in",
                hashed_password=get_password_hash("officer123"),
                role="OFFICER",
                full_name="Inspector Rajesh Kumar",
                badge_number="SSB-DEL-4092"
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

        # Seed initial synthetic watchlist
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
    print("[SatyaScan Backend] Initializing database and security models...")
    init_db()
    seed_initial_demo_data()
    print("[SatyaScan Backend] Ready for automated document screening requests.")
    yield
    # Shutdown
    print("[SatyaScan Backend] Shutting down...")


app = FastAPI(
    title="SatyaScan API",
    description="AI-Based Fake Identity & Document Screening System (SIH26188 · Sashastra Seema Bal, Ministry of Home Affairs)",
    version=settings.VERSION,
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers under API v1
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


# Serve generated heatmaps and reports statically
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")


@app.get("/", tags=["System"])
def root():
    return {
        "platform": "SatyaScan",
        "tagline": "Verify. Detect. Explain.",
        "description": "AI-Assisted Identity & Document Screening Platform",
        "problem_statement": "SIH26188",
        "docs_url": "/docs"
    }
