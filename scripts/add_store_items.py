#!/usr/bin/env python3
"""
Add more cat accessories to the store
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from database.models import StoreItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORE_ITEMS = {
    # Existing items
    "sunglasses": {"price": 100, "description": "Cool sunglasses for your cat 😎"},
    "cap": {"price": 150, "description": "A stylish cap for your cat 🧢"},
    "moustache": {"price": 200, "description": "A fancy moustache for your cat 🥸"},
    "butterfly": {"price": 250, "description": "A cute butterfly accessory 🦋"},

    # New accessories
    "bow-tie": {"price": 120, "description": "Elegant bow tie for a classy cat 🎀"},
    "crown": {"price": 300, "description": "Royal crown fit for a king/queen cat 👑"},
    "glasses": {"price": 180, "description": "Smart reading glasses 🤓"},
    "party-hat": {"price": 150, "description": "Fun party hat for celebrations 🎉"},
    "scarf": {"price": 200, "description": "Cozy winter scarf 🧣"},
    "bandana": {"price": 130, "description": "Cool bandana for adventurous cats 🏴‍☠️"},
    "flower": {"price": 110, "description": "Pretty flower accessory 🌸"},
    "bow": {"price": 140, "description": "Cute hair bow 🎀"},
    "top-hat": {"price": 250, "description": "Fancy top hat for special occasions 🎩"},
    "headphones": {"price": 220, "description": "Music-loving cat headphones 🎧"},
    "wizard-hat": {"price": 280, "description": "Magical wizard hat ✨"},
    "pirate-hat": {"price": 270, "description": "Arr matey! Pirate captain hat 🏴‍☠️"},
    "santa-hat": {"price": 160, "description": "Festive Santa hat for holidays 🎅"},
    "chef-hat": {"price": 190, "description": "Master chef hat for foodie cats 👨‍🍳"},
    "beret": {"price": 170, "description": "Artistic French beret 🎨"},
    "necklace": {"price": 240, "description": "Sparkly diamond necklace 💎"},
    "monocle": {"price": 210, "description": "Distinguished monocle 🧐"},
    "tie": {"price": 140, "description": "Professional business tie 👔"},
    "collar": {"price": 100, "description": "Stylish spiked collar 🔷"},
    "badge": {"price": 180, "description": "Sheriff badge for law-abiding cats ⭐"},
    "goggles": {"price": 200, "description": "Cool aviator goggles 🥽"}
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

        db.commit()

        logger.info(f"\n✓ Added {items_added} new items")
        logger.info(f"✓ Updated {items_updated} existing items")
        logger.info(f"✓ Total store items: {len(STORE_ITEMS)}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
