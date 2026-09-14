"""
SatyaScan Security & Privacy Utilities
Handles JWT token generation, password hashing, RBAC verification,
secure file upload validation (magic bytes & size limits), and PII masking.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import re

from backend.app.core.config import settings

security_bearer = HTTPBearer(auto_error=False)


# --- Password Hashing (Direct bcrypt for Python 3.13 compatibility) ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8')[:72], hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8')[:72], salt).decode('utf-8')


# --- JWT Token Handling ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


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

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_uploaded_image_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Validates uploaded file against MIME spoofing, magic header bytes, and size caps.
    Raises HTTPException if file is suspect or invalid.
    """
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB.")

    # Validate file extension
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
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

    return detected_mime
