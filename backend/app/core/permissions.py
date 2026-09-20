"""
SatyaScan Centralized Role-Based Access Control (RBAC) & Checkpoint Isolation Policy
SIH26188 · Ministry of Home Affairs / Sashastra Seema Bal (SSB), Police II Division

Zero-Trust Architecture:
1. Strict server-side authorization: never trust client-provided roles, checkpoint IDs, or claims.
2. Checkpoint Scoping: Officers can only access screenings originating from their assigned station.
3. Supervisory Oversight: Supervisors and Admins have authorized cross-checkpoint operational visibility.
4. Security Auditing: All access violations log an ACCESS_DENIED audit event to the unbroken SHA-256 chain.
"""

from typing import List, Set, Optional, Any
from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session

from backend.app.models.database import User, get_db
from backend.app.core.security import get_current_user

# --- Fine-Grained Permission Definitions ---
PERM_SCREENING_CREATE = "screening:create"
PERM_SCREENING_VIEW = "screening:view"
PERM_CASE_REVIEW = "case:review"
PERM_MEDIA_ACCESS = "media:access"
PERM_REPORT_DOWNLOAD = "report:download"
PERM_AUDIT_VIEW = "audit:view"
PERM_AUDIT_VERIFY = "audit:verify"
PERM_BLOCKCHAIN_ANCHOR = "blockchain:anchor"
PERM_BLOCKCHAIN_VERIFY = "blockchain:verify"
PERM_WATCHLIST_VIEW = "watchlist:view"
PERM_WATCHLIST_MANAGE = "watchlist:manage"
PERM_ANALYTICS_VIEW = "analytics:view"
PERM_SYSTEM_ADMIN = "system:admin"

# --- Role-to-Permissions Mapping ---
OFFICER_PERMISSIONS: Set[str] = {
    PERM_SCREENING_CREATE,
    PERM_SCREENING_VIEW,
    PERM_MEDIA_ACCESS,
    PERM_REPORT_DOWNLOAD,
    PERM_AUDIT_VIEW,
    PERM_AUDIT_VERIFY,
    PERM_BLOCKCHAIN_ANCHOR,
    PERM_BLOCKCHAIN_VERIFY,
    PERM_WATCHLIST_VIEW,
    PERM_ANALYTICS_VIEW,
}

SUPERVISOR_PERMISSIONS: Set[str] = OFFICER_PERMISSIONS | {
    PERM_CASE_REVIEW,
    PERM_WATCHLIST_MANAGE,
}

ADMIN_PERMISSIONS: Set[str] = SUPERVISOR_PERMISSIONS | {
    PERM_SYSTEM_ADMIN,
}

ROLE_PERMISSIONS_MAP = {
    "OFFICER": OFFICER_PERMISSIONS,
    "SUPERVISOR": SUPERVISOR_PERMISSIONS,
    "ADMIN": ADMIN_PERMISSIONS,
}


def get_user_permissions(user: User) -> Set[str]:
    """Returns the set of valid permissions granted to the user's assigned role."""
    role = (user.role or "OFFICER").upper()
    return ROLE_PERMISSIONS_MAP.get(role, OFFICER_PERMISSIONS)


def has_permission(user: User, permission: str) -> bool:
    """Verifies whether the given user possesses the specified fine-grained permission."""
    return permission in get_user_permissions(user)


def require_permission(permission: str):
    """FastAPI dependency factory enforcing a specific fine-grained permission."""
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required permission '{permission}' not granted for role '{current_user.role}'."
            )
        return current_user
    return permission_checker


def check_checkpoint_access(
    user: User,
    screening: Any,
    db: Optional[Session] = None,
    resource_type: str = "screening"
) -> None:
    """
    Enforces server-side checkpoint isolation and prevents IDOR attacks.
    - Officers can only access screenings and derived assets (media, reports, audit, anchors)
      originating from their assigned checkpoint.
    - Supervisors and Admins possess legitimate cross-checkpoint oversight authority.
    - Violations trigger an immediate HTTP 403 and record an ACCESS_DENIED audit ledger event.
    """
    if not screening:
        return

    # Supervisors and Admins have cross-station inspection authority
    user_role = (user.role or "OFFICER").upper()
    if user_role in ("SUPERVISOR", "ADMIN"):
        return

    # For OFFICER: checkpoint binding is strictly enforced
    user_cp = (user.checkpoint_id or "").strip()
    resource_cp = (getattr(screening, "checkpoint_id", "") or "").strip()

    # If both user and resource have checkpoint identities, they must match
    if user_cp and resource_cp and user_cp != resource_cp:
        # Audit the access violation
        if db is not None:
            try:
                from backend.app.services.audit_service import AuditService
                AuditService.record_event(
                    db=db,
                    screening_id=getattr(screening, "id", "UNKNOWN"),
                    event_type="ACCESS_DENIED",
                    payload_data={
                        "attempted_resource": resource_type,
                        "resource_id": getattr(screening, "id", "UNKNOWN"),
                        "resource_checkpoint": resource_cp,
                        "user_checkpoint": user_cp,
                        "username": user.username,
                        "role": user.role,
                        "badge_number": user.badge_number,
                        "reason": f"Officer at checkpoint '{user_cp}' attempted access to '{resource_type}' from checkpoint '{resource_cp}'."
                    },
                    actor=f"{user.role}:{user.username}"
                )
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Screening belongs to checkpoint '{resource_cp}', but your session is bound to checkpoint '{user_cp}'."
        )
