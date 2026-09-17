"""
SatyaScan Security & Privacy Utilities
Handles JWT token generation, bcrypt password hashing, RBAC verification,
secure file upload validation (magic bytes, decode integrity & dimension limits),
and PII masking.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
import io
import os
import re
from PIL import Image
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.database import get_db, User

security_bearer = HTTPBearer(auto_error=False)

# Configure PIL decompression bomb protection
Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS


# --- Password Hashing (Direct bcrypt with explicit work factor 12) ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # bcrypt standard limit is 72 bytes
        return bcrypt.checkpw(plain_password.encode('utf-8')[:72], hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    # Explicit cost factor 12 for strong defensive posture
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8')[:72], salt).decode('utf-8')


# --- JWT Token Handling ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            options={"verify_signature": True, "verify_exp": True}
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None


# --- Authentication & RBAC Dependencies ---

def get_current_user(
    token_creds: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """
    Validates Bearer JWT token and returns authenticated User model.
    In strict mode or production, strictly requires Bearer token (rejects missing with HTTP 401).
    In evaluation prototype mode, falls back to default officer if no token was passed,
    preserving seamless demonstration compatibility.
    Any provided token that is invalid or expired is ALWAYS rejected with HTTP 401.
    """
    if token_creds and token_creds.credentials:
        token = token_creds.credentials
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        user = db.query(User).filter(User.username == payload["sub"]).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated or not found.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user

    if settings.STRICT_AUTH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # SIH Evaluation Demo Fallback (EVALUATION ONLY)
    user = db.query(User).filter(User.username == "officer").first()
    if user and user.is_active:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided.",
        headers={"WWW-Authenticate": "Bearer"}
    )


def require_role(allowed_roles: List[str]):
    """Role-Based Access Control (RBAC) dependency factory."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of the following roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


# --- PII Masking Utilities (Privacy by Design) ---

def mask_document_number(doc_num: Optional[str]) -> str:
    """Masks document number for privacy: e.g. 'Z1234567' -> 'Z12****67'."""
    if not doc_num:
        return "N/A"
    clean = doc_num.strip()
    if len(clean) <= 4:
        return "****"
    prefix = clean[:3]
    suffix = clean[-2:]
    stars = "*" * (len(clean) - 5) if len(clean) > 5 else "**"
    return f"{prefix}{stars}{suffix}"


def mask_full_name(name: Optional[str]) -> str:
    """Masks name for public logging: e.g. 'ARJUN SHARMA' -> 'A****N S****A'."""
    if not name:
        return "ANONYMOUS"
    parts = name.strip().split()
    masked_parts = []
    for p in parts:
        if len(p) <= 2:
            masked_parts.append(p[0] + "*")
        else:
            masked_parts.append(p[0] + "*" * (len(p) - 2) + p[-1])
    return " ".join(masked_parts)


def mask_date_of_birth(dob: Optional[str]) -> str:
    """Masks day and month of birth: e.g. '1990-05-12' -> '1990-**-**'."""
    if not dob:
        return "N/A"
    clean = dob.strip()
    match = re.match(r'^(\d{4})[-/.]\d{2}[-/.]\d{2}$', clean)
    if match:
        return f"{match.group(1)}-**-**"
    return "****-**-**"


# --- File Upload Security Validation ---

ALLOWED_MAGIC_HEADERS = {
    b'\xFF\xD8\xFF': "image/jpeg",
    b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': "image/png",
    b'RIFF': "image/webp"
}


def sanitize_filename(filename: str) -> str:
    """Strips directory traversal sequences, returning safe basename."""
    base = os.path.basename(filename).strip()
    # Remove null bytes and non-alphanumeric/dot/dash characters
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return clean or "upload.jpg"


def validate_uploaded_image_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Validates uploaded file against MIME spoofing, magic header bytes,
    file corruption, and pixel dimension limits (decompression bomb protection).
    Raises HTTPException if file is suspect or invalid.
    """
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
        )

    # Sanitize and validate file extension
    clean_name = sanitize_filename(filename)
    ext = clean_name.lower().split('.')[-1] if '.' in clean_name else ''
    if ext not in ["jpg", "jpeg", "png", "webp"]:
        raise HTTPException(status_code=400, detail=f"Invalid file extension '.{ext}'. Supported: JPG, PNG, WEBP.")

    # Check magic header bytes
    valid_format = False
    detected_mime = ""
    for magic, mime in ALLOWED_MAGIC_HEADERS.items():
        if file_bytes.startswith(magic):
            valid_format = True
            detected_mime = mime
            break

    # WebP check (needs RIFF header and WEBP signature)
    if file_bytes.startswith(b'RIFF') and len(file_bytes) > 12:
        if file_bytes[8:12] == b'WEBP':
            valid_format = True
            detected_mime = "image/webp"

    if not valid_format:
        raise HTTPException(
            status_code=400,
            detail="File content header does not match valid JPEG, PNG, or WebP image format. Potential polyglot rejected."
        )

    # Structural decoding & corruption verification via PIL
    try:
        bio = io.BytesIO(file_bytes)
        with Image.open(bio) as img:
            img.verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Corrupted image file or invalid image structure. File could not be decoded."
        )

    # Dimension & decompression bomb protection (re-open fresh BytesIO after verify)
    try:
        bio2 = io.BytesIO(file_bytes)
        with Image.open(bio2) as img:
            width, height = img.size
            total_pixels = width * height
            if (
                width > settings.MAX_IMAGE_DIMENSION
                or height > settings.MAX_IMAGE_DIMENSION
                or total_pixels > settings.MAX_IMAGE_PIXELS
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Document image exceeds the permitted processing dimensions."
                )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Corrupted image file or invalid image structure."
        )

    return detected_mime
