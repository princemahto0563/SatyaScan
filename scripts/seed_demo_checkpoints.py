#!/usr/bin/env python3
"""
SatyaScan Standalone Checkpoint Seeder
EVALUATION / DEMO ONLY (SIH26188)

Initializes the database schema and populates all 8 canonical border checkpoints
and their corresponding operator credentials with bcrypt-hashed passwords.
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.models.database import SessionLocal, init_db
from backend.app.core.checkpoints import seed_checkpoints, CANONICAL_CHECKPOINTS, DEMO_CHECKPOINT_PASSWORD


def main():
    print("=" * 65)
    print("SatyaScan Checkpoint Initialization (EVALUATION / DEMO ONLY)")
    print("=" * 65)
    print("[*] Ensuring database tables and column migrations...")
    init_db()

    db = SessionLocal()
    try:
        print(f"[*] Seeding {len(CANONICAL_CHECKPOINTS)} canonical border checkpoints...")
        seed_checkpoints(db)
        print("[+] Checkpoint seeding completed successfully.")
        print("-" * 65)
        print(f"{'Code':<15} | {'Username':<18} | {'Checkpoint Name'}")
        print("-" * 65)
        for cp in CANONICAL_CHECKPOINTS:
            print(f"{cp['code']:<15} | {cp['username']:<18} | {cp['name']}")
        print("-" * 65)
        print(f"[!] Default Demo Password: {DEMO_CHECKPOINT_PASSWORD} (Bcrypt hashed)")
        print("=" * 65)
    except Exception as e:
        print(f"[-] Seeding failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
