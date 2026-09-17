"""
SatyaScan In-Memory Rate Limiter
Lightweight, thread-safe sliding window rate limiter for SIH prototype security.
Requires zero external infrastructure (no Redis / Celery required).
Defends against brute-force credential stuffing and OCR resource exhaustion.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException, status

from backend.app.core.config import settings


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    Cleans expired timestamps automatically to avoid memory leakage.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Filter timestamps within window
            valid_timestamps = [t for t in self._records[key] if t > cutoff]
            if len(valid_timestamps) >= max_requests:
                self._records[key] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._records[key] = valid_timestamps
            return True

    def reset(self):
        """Clears all records (useful for test assertions)."""
        with self._lock:
            self._records.clear()


limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """Safely extracts client IP address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit_login(request: Request):
    """Rate limits login attempts (e.g. 10 requests / min per IP)."""
    ip = get_client_ip(request)
    key = f"login:{ip}"
    if not limiter.is_allowed(key, max_requests=settings.LOGIN_RATE_LIMIT, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please retry after 60 seconds.",
            headers={"Retry-After": "60"}
        )


def rate_limit_screening(request: Request):
    """Rate limits screening creation to prevent OCR/CV denial-of-service (20 req / min per IP)."""
    ip = get_client_ip(request)
    key = f"screening:{ip}"
    if not limiter.is_allowed(key, max_requests=settings.SCREENING_RATE_LIMIT, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Screening request limit reached. Please wait before submitting more documents.",
            headers={"Retry-After": "60"}
        )
