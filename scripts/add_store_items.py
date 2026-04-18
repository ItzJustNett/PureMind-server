#!/usr/bin/env python3
"""
Add more cat accessories to the store
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from database.models import StoreItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORE_ITEMS = {
    "sunglasses": {"price": 100, "description": "Cool sunglasses for your cat 😎"},
    "crown": {"price": 300, "description": "Royal crown fit for a king/queen cat 👑"},
    "scarf": {"price": 200, "description": "Cozy winter scarf 🧣"},
}

def main():
    """Add store items to database"""
    logger.info("Adding cat accessories to store...")

    db = SessionLocal()
    try:
        items_added = 0
        items_updated = 0

        for item_id, item_data in STORE_ITEMS.items():
            # Check if item already exists
            existing = db.query(StoreItem).filter(StoreItem.item_id == item_id).first()

            if existing:
                # Update existing item
                existing.name = item_id.replace("-", " ").title()
                existing.price = item_data["price"]
                existing.description = item_data["description"]
                items_updated += 1
                logger.info(f"Updated: {item_id}")
            else:
                # Create new item
                store_item = StoreItem(
                    item_id=item_id,
                    name=item_id.replace("-", " ").title(),
                    price=item_data["price"],
                    description=item_data["description"]
                )
                db.add(store_item)
                items_added += 1
                logger.info(f"Added: {item_id}")

        # Remove items not in STORE_ITEMS
        removed = db.query(StoreItem).filter(StoreItem.item_id.notin_(STORE_ITEMS.keys())).delete(synchronize_session=False)

        db.commit()

        logger.info(f"\n✓ Added {items_added} new items")
        logger.info(f"✓ Updated {items_updated} existing items")
        logger.info(f"✓ Removed {removed} old items")
        logger.info(f"✓ Total store items: {len(STORE_ITEMS)}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
