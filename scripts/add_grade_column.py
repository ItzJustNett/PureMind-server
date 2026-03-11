#!/usr/bin/env python3
"""
Add grade column to profiles table
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Add grade column to profiles table"""
    db = SessionLocal()
    try:
        # Add grade column if it doesn't exist
        logger.info("Adding grade column to profiles table...")

        db.execute(text("""
            ALTER TABLE profiles
            ADD COLUMN IF NOT EXISTS grade INTEGER;
        """))

        db.commit()
        logger.info("✓ Grade column added successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
