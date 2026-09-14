"""
SatyaScan Authentication Endpoints (JWT + RBAC)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.app.models.database import get_db, User
from backend.app.schemas.screening import UserLogin, TokenResponse, UserResponse
from backend.app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token, security_bearer
from backend.app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password credentials."
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "id": user.id}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "full_name": user.full_name,
        "badge_number": user.badge_number
    }


@router.get("/me", response_model=UserResponse)
def get_current_user(token_creds=Depends(security_bearer), db: Session = Depends(get_db)):
    if not token_creds or not token_creds.credentials:
        # For prototype ease-of-demo, return default officer if no token provided
        user = db.query(User).filter(User.username == "officer").first()
        if user:
            return user
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_access_token(token_creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
