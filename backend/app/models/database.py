"""
SatyaScan Database Models (SQLAlchemy)
Supports SQLite for zero-config local execution and PostgreSQL for cloud deployments.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from backend.app.core.config import settings

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="OFFICER")  # OFFICER, SUPERVISOR, ADMIN
    full_name = Column(String(100), nullable=False)
    badge_number = Column(String(30), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    screenings = relationship("Screening", back_populates="operator")


class Screening(Base):
    __tablename__ = "screenings"

    id = Column(String(50), primary_key=True, index=True)  # SAT-2026-XXXX
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_type = Column(String(30), default="PASSPORT")
    masked_document_id = Column(String(30), nullable=False)
    status = Column(String(30), default="COMPLETED")  # COMPLETED, MANUAL_REVIEW_REQUIRED, CLEARED, ESCALATED
    risk_score = Column(Float, default=0.0)
    risk_band = Column(String(20), default="LOW")  # LOW, MEDIUM, HIGH, CRITICAL
    recommendation = Column(Text, nullable=True)
    doc_image_path = Column(String(255), nullable=True)
    live_image_path = Column(String(255), nullable=True)
    ela_heatmap_path = Column(String(255), nullable=True)
    execution_latency_ms = Column(Float, default=0.0)

    operator = relationship("User", back_populates="screenings")
    fields = relationship("ExtractedField", back_populates="screening", cascade="all, delete-orphan")
    validation_findings = relationship("ValidationFinding", back_populates="screening", cascade="all, delete-orphan")
    tamper_findings = relationship("TamperFinding", back_populates="screening", cascade="all, delete-orphan")
    face_result = relationship("FaceResult", uselist=False, back_populates="screening", cascade="all, delete-orphan")
    identity_matches = relationship("IdentityMatch", back_populates="screening", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="screening", cascade="all, delete-orphan")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, index=True)
    field_name = Column(String(50), nullable=False)
    visual_value = Column(String(100), nullable=True)
    mrz_value = Column(String(100), nullable=True)
    confidence = Column(Float, default=1.0)
    match_status = Column(String(20), default="MATCH")  # MATCH, MISMATCH, NOT_PRESENT
    bounding_box_json = Column(Text, nullable=True)

    screening = relationship("Screening", back_populates="fields")


class ValidationFinding(Base):
    __tablename__ = "validation_findings"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, index=True)
    rule_id = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    field = Column(String(50), nullable=True)
    expected = Column(String(100), nullable=True)
    observed = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    classification = Column(String(30), default="OFFICIAL_STANDARD")

    screening = relationship("Screening", back_populates="validation_findings")


class TamperFinding(Base):
    __tablename__ = "tamper_findings"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, index=True)
    technique = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    score = Column(Float, default=0.0)
    summary = Column(String(200), nullable=False)
    observation = Column(Text, nullable=True)
    interpretation = Column(Text, nullable=True)

    screening = relationship("Screening", back_populates="tamper_findings")


class FaceResult(Base):
    __tablename__ = "face_results"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, unique=True, index=True)
    metric = Column(String(50), default="Cosine Similarity")
    similarity_score = Column(Float, nullable=False)
    threshold = Column(Float, default=0.65)
    verification_result = Column(String(20), nullable=False)  # MATCH, BORDERLINE, MISMATCH, UNABLE_TO_VERIFY
    appearance_level = Column(String(20), default="MINIMAL")  # MINIMAL, MODERATE, SIGNIFICANT
    observations_json = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    screening = relationship("Screening", back_populates="face_result")


class IdentityMatch(Base):
    __tablename__ = "identity_matches"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, index=True)
    matched_document_id = Column(String(50), nullable=False)
    matched_name = Column(String(100), nullable=False)
    similarity = Column(Float, nullable=False)
    alert_message = Column(Text, nullable=False)

    screening = relationship("Screening", back_populates="identity_matches")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(String(50), ForeignKey("screenings.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    actor = Column(String(100), default="SYSTEM_AUTOMATION")
    event_type = Column(String(50), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False, unique=True)

    screening = relationship("Screening", back_populates="audit_events")


class ReferenceWatchlist(Base):
    __tablename__ = "reference_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    nationality = Column(String(10), default="IND")
    reason = Column(Text, nullable=False)
    risk_category = Column(String(30), default="STOLEN_PASSPORT")  # STOLEN_PASSPORT, LOOKOUT_CIRCULAR, SUSPENDED
    status = Column(String(20), default="ACTIVE")
    classification = Column(String(30), default="SYNTHETIC_PROTOTYPE_RECORD")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Engine and Session initialization
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI Dependency for obtaining DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
