#!/usr/bin/env python3
"""
Give meowcoins to a user by email.
Usage: python give_meowcoins.py <email> <amount>
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from database.models import User, Profile

def main():
    if len(sys.argv) < 3:
        print("Usage: python give_meowcoins.py <email> <amount>")
        sys.exit(1)

    email = sys.argv[1]
    amount = int(sys.argv[2])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User with email '{email}' not found")
            sys.exit(1)

        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if not profile:
            print(f"Profile for user '{user.username}' not found")
            sys.exit(1)

        old_balance = profile.meowcoins
        profile.meowcoins += amount
        db.commit()

        print(f"Gave {amount} meowcoins to {user.username} ({email})")
        print(f"Balance: {old_balance} -> {profile.meowcoins}")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
