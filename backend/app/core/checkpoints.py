"""
SatyaScan Canonical Border Checkpoints Configuration
EVALUATION / DEMO ONLY
These represent canonical land borders and international airport checkpoints
for demonstration in SIH26188.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.database import Checkpoint, User
from backend.app.core.security import get_password_hash

DEMO_CHECKPOINT_PASSWORD = "Demo@123"

CANONICAL_CHECKPOINTS: List[Dict[str, Any]] = [
    {
        "id": "CP-DEL-AIR",
        "code": "CP-DEL-AIR",
        "name": "Delhi Airport Immigration Checkpoint",
        "location": "Delhi Airport (IGI)",
        "username": "delhi_airport",
        "full_name": "Delhi Airport Checkpoint Officer",
        "badge_number": "SSB-DEL-01",
        "email": "delhi_airport@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-ATTARI",
        "code": "CP-ATTARI",
        "name": "Attari Border Checkpoint",
        "location": "Attari, Punjab",
        "username": "attari_border",
        "full_name": "Attari Border Checkpoint Officer",
        "badge_number": "SSB-ATT-02",
        "email": "attari_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-RAXAUL",
        "code": "CP-RAXAUL",
        "name": "Raxaul Border Checkpoint",
        "location": "Raxaul, Bihar (Indo-Nepal)",
        "username": "raxaul_border",
        "full_name": "Raxaul Border Checkpoint Officer",
        "badge_number": "SSB-RAX-03",
        "email": "raxaul_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-JOGBANI",
        "code": "CP-JOGBANI",
        "name": "Jogbani Border Checkpoint",
        "location": "Jogbani, Bihar (Indo-Nepal)",
        "username": "jogbani_border",
        "full_name": "Jogbani Border Checkpoint Officer",
        "badge_number": "SSB-JOG-04",
        "email": "jogbani_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-SUNAULI",
        "code": "CP-SUNAULI",
        "name": "Sunauli Border Checkpoint",
        "location": "Sunauli, UP (Indo-Nepal)",
        "username": "sunauli_border",
        "full_name": "Sunauli Border Checkpoint Officer",
        "badge_number": "SSB-SUN-05",
        "email": "sunauli_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-RUPAIDIHA",
        "code": "CP-RUPAIDIHA",
        "name": "Rupaidiha Border Checkpoint",
        "location": "Rupaidiha, UP (Indo-Nepal)",
        "username": "rupaidiha_border",
        "full_name": "Rupaidiha Border Checkpoint Officer",
        "badge_number": "SSB-RUP-06",
        "email": "rupaidiha_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-PANITANKI",
        "code": "CP-PANITANKI",
        "name": "Panitanki Border Checkpoint",
        "location": "Panitanki, WB (Indo-Nepal)",
        "username": "panitanki_border",
        "full_name": "Panitanki Border Checkpoint Officer",
        "badge_number": "SSB-PAN-07",
        "email": "panitanki_border@satyascan.gov.in",
        "role": "OFFICER"
    },
    {
        "id": "CP-PETRAPOLE",
        "code": "CP-PETRAPOLE",
        "name": "Petrapole Border Checkpoint",
        "location": "Petrapole, WB (Indo-Bangladesh)",
        "username": "petrapole_border",
        "full_name": "Petrapole Border Checkpoint Officer",
        "badge_number": "SSB-PET-08",
        "email": "petrapole_border@satyascan.gov.in",
        "role": "OFFICER"
    }
]


def seed_checkpoints(db: Session):
    """
    Idempotently seeds all 8 canonical border checkpoints and corresponding user accounts.
    Also ensures the default demo 'officer' is mapped to Delhi Airport.
    """
    hashed_pwd = get_password_hash(DEMO_CHECKPOINT_PASSWORD)

    for cp_data in CANONICAL_CHECKPOINTS:
        # Check if checkpoint exists
        cp = db.query(Checkpoint).filter(Checkpoint.id == cp_data["id"]).first()
        if not cp:
            cp = Checkpoint(
                id=cp_data["id"],
                code=cp_data["code"],
                name=cp_data["name"],
                location=cp_data["location"],
                username=cp_data["username"],
                role=cp_data["role"],
                is_active=True
            )
            db.add(cp)
        else:
            cp.code = cp_data["code"]
            cp.name = cp_data["name"]
            cp.location = cp_data["location"]
            cp.username = cp_data["username"]

        # Check if user account exists
        user = db.query(User).filter(User.username == cp_data["username"]).first()
        if not user:
            user = User(
                username=cp_data["username"],
                email=cp_data["email"],
                hashed_password=hashed_pwd,
                role=cp_data["role"],
                full_name=cp_data["full_name"],
                badge_number=cp_data["badge_number"],
                checkpoint_id=cp_data["id"],
                checkpoint_name=cp_data["name"],
                location=cp_data["location"],
                is_active=True
            )
            db.add(user)
        else:
            user.email = cp_data["email"]
            user.checkpoint_id = cp_data["id"]
            user.checkpoint_name = cp_data["name"]
            user.location = cp_data["location"]

    # Also ensure officer user is mapped to Delhi Airport Checkpoint if not set
    officer = db.query(User).filter(User.username == "officer").first()
    if officer:
        if not officer.checkpoint_id:
            officer.checkpoint_id = "CP-DEL-AIR"
            officer.checkpoint_name = "Delhi Airport Immigration Checkpoint"
            officer.location = "Delhi Airport (IGI)"

    db.commit()
