#!/usr/bin/env python3
"""
Seed a test user for E2E. Run: python scripts/seed_e2e_user.py
Creates e2e@purdue.edu / e2epass123 (verified) for Playwright tests.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import User, PendingRegistration
from app.auth import hash_password

def main():
    db = SessionLocal()
    email = "e2e@purdue.edu"
    password = "e2epass123"
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"User {email} already exists. Use E2E_TEST_EMAIL={email} E2E_TEST_PASSWORD={password}")
            return
        user = User(
            email=email,
            username="e2etest",
            password_hash=hash_password(password),
            display_name="E2E Test",
            self_reported_skill=5,
            ai_skill_rating=5.0,
            skill_confidence=0.1,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {email}. Set: E2E_TEST_EMAIL={email} E2E_TEST_PASSWORD={password}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
