"""
SatyaScan Authentication Endpoints (JWT + RBAC + Checkpoint Binding)
Handles officer login, bcrypt verification, checkpoint assignment, and authenticated profile retrieval.
Includes rate limiting protection against brute-force attacks and cryptographic audit trail logging.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.app.models.database import get_db, User, Checkpoint
from backend.app.schemas.screening import (
    UserLogin, TokenResponse, UserResponse, CheckpointResponse
)
from backend.app.core.security import verify_password, create_access_token, get_current_user
from backend.app.core.rate_limiter import rate_limit_login
from backend.app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/checkpoints", response_model=List[CheckpointResponse])
def get_checkpoints(db: Session = Depends(get_db)):
    """
    Returns list of all active border and immigration checkpoints
    available for officer workstation authentication.
    """
    return db.query(Checkpoint).filter(Checkpoint.is_active == True).all()


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_login)])
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates border officer / supervisor credentials and issues JWT Bearer token.
    Rate-limited to prevent brute-force credential stuffing.
    Enforces strict checkpoint-user binding when checkpoint_id is specified.
    """
    # Safe lookup: do not reveal whether username or password was incorrect
    user = db.query(User).filter(User.username == credentials.username.strip()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Checkpoint validation: if checkpoint_id is provided, verify matching
    if credentials.checkpoint_id:
        cp = db.query(Checkpoint).filter(Checkpoint.id == credentials.checkpoint_id.strip()).first()
        if not cp or not cp.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid checkpoint credentials.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        # Strict Checkpoint-User Binding
        if user.checkpoint_id != cp.id and user.username != cp.username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid checkpoint credentials.",
                headers={"WWW-Authenticate": "Bearer"}
            )

    # Audit logging for login event
    try:
        AuditService.record_event(
            db=db,
            screening_id=f"AUTH-{user.username}",
            event_type="LOGIN_SUCCESS",
            payload_data={
                "username": user.username,
                "role": user.role,
                "checkpoint_id": user.checkpoint_id,
                "checkpoint_name": user.checkpoint_name
            },
            actor=f"OFFICER:{user.username}"
        )
    except Exception:
        pass

    token_data = {
        "sub": user.username,
        "role": user.role,
        "id": user.id,
        "checkpoint_id": user.checkpoint_id,
        "checkpoint_name": user.checkpoint_name
    }
    access_token = create_access_token(data=token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "full_name": user.full_name,
        "badge_number": user.badge_number,
        "checkpoint_id": user.checkpoint_id,
        "checkpoint_name": user.checkpoint_name,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "badge_number": user.badge_number,
            "checkpoint_id": user.checkpoint_id,
            "checkpoint_name": user.checkpoint_name,
            "location": user.location
        }
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated officer's profile from verified JWT token.
    Requires Bearer token authentication.
    """
    return current_user
