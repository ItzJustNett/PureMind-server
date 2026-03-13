"""
Store management - handles store items, inventory, and equipped items.
Replaces store operations from profiles.py.
"""
import logging
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session

from database.models import StoreItem, Inventory, EquippedItem, Profile
from db_managers.profile_manager import update_streak

logger = logging.getLogger(__name__)


def get_store_items(db: Session) -> List[Dict]:
    """Get all store items"""
    try:
        items = db.query(StoreItem).all()
        return [
            {
                "id": str(item.id),
                "item_id": item.item_id,
                "name": item.name,
                "price": item.price,
                "description": item.description
            }
            for item in items
        ]
    except Exception as e:
        logger.error(f"Error getting store items: {e}")
        return []


def buy_item(db: Session, user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Buy an item from the store"""
    try:
        # Get store item
        store_item = db.query(StoreItem).filter(StoreItem.item_id == item_id).first()
        if not store_item:
            return {"error": f"Item '{item_id}' not found in store"}, 404

        # Get user profile
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            return {"error": "Profile not found"}, 404

        # Check if user has enough meowcoins
        if profile.meowcoins < store_item.price:
            return {
                "error": f"Not enough meowcoins. Need {store_item.price}, have {profile.meowcoins}"
            }, 400

        # Check if user already has the item
        existing = db.query(Inventory).filter(
            Inventory.user_id == user_id,
            Inventory.store_item_id == store_item.id
        ).first()
        if existing:
            return {"error": f"You already own the '{item_id}' item"}, 400

        # Purchase the item
        profile.meowcoins -= store_item.price
        inventory = Inventory(user_id=user_id, store_item_id=store_item.id)
        db.add(inventory)

        # Update streak
        update_streak(db, user_id)

        db.commit()

        # Get updated inventory
        inventory_items = get_user_inventory(db, user_id)

        logger.info(f"User {user_id} purchased item {item_id}")
        return {
            "success": True,
            "message": f"Successfully purchased '{item_id}'",
            "remaining_meowcoins": profile.meowcoins,
            "inventory": inventory_items
        }, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error buying item: {e}")
        return {"error": "Failed to purchase item"}, 500


def equip_item(db: Session, user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Equip an item from inventory"""
    try:
        # Get store item
        store_item = db.query(StoreItem).filter(StoreItem.item_id == item_id).first()
        if not store_item:
            return {"error": f"Item '{item_id}' not found"}, 404

        # Check if user owns the item
        inventory = db.query(Inventory).filter(
            Inventory.user_id == user_id,
            Inventory.store_item_id == store_item.id
        ).first()
        if not inventory:
            return {"error": f"You don't own the '{item_id}' item"}, 400

        # Check if already equipped
        equipped = db.query(EquippedItem).filter(
            EquippedItem.user_id == user_id,
            EquippedItem.store_item_id == store_item.id
        ).first()
        if equipped:
            return {"error": f"The '{item_id}' item is already equipped"}, 400

        # Equip the item
        equipped_item = EquippedItem(user_id=user_id, store_item_id=store_item.id)
        db.add(equipped_item)
        db.commit()

        equipped_items = get_equipped_items(db, user_id)

        logger.info(f"User {user_id} equipped item {item_id}")
        return {
            "success": True,
            "message": f"Successfully equipped '{item_id}'",
            "equipped_items": equipped_items
        }, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error equipping item: {e}")
        return {"error": "Failed to equip item"}, 500


def unequip_item(db: Session, user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Unequip an item"""
    try:
        # Get store item
        store_item = db.query(StoreItem).filter(StoreItem.item_id == item_id).first()
        if not store_item:
            return {"error": f"Item '{item_id}' not found"}, 404

        # Check if item is equipped
        equipped = db.query(EquippedItem).filter(
            EquippedItem.user_id == user_id,
            EquippedItem.store_item_id == store_item.id
        ).first()
        if not equipped:
            return {"error": f"The '{item_id}' item is not currently equipped"}, 400

        # Unequip the item
        db.delete(equipped)
        db.commit()

        equipped_items = get_equipped_items(db, user_id)

        logger.info(f"User {user_id} unequipped item {item_id}")
        return {
            "success": True,
            "message": f"Successfully unequipped '{item_id}'",
            "equipped_items": equipped_items
        }, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error unequipping item: {e}")
        return {"error": "Failed to unequip item"}, 500


def get_equipped_items(db: Session, user_id: int) -> List[str]:
    """Get list of equipped item IDs for a user"""
    try:
        items = db.query(EquippedItem).filter(EquippedItem.user_id == user_id).all()
        result = []
        for item in items:
            store_item = db.query(StoreItem).filter(StoreItem.id == item.store_item_id).first()
            if store_item:
                result.append(store_item.item_id)
        return result
    except Exception as e:
        logger.error(f"Error getting equipped items: {e}")
        return []


def get_user_inventory(db: Session, user_id: int) -> List[str]:
    """Get list of items in user's inventory"""
    try:
        items = db.query(Inventory).filter(Inventory.user_id == user_id).all()
        result = []
        for item in items:
            store_item = db.query(StoreItem).filter(StoreItem.id == item.store_item_id).first()
            if store_item:
                result.append(store_item.item_id)
        return result
    except Exception as e:
        logger.error(f"Error getting inventory: {e}")
        return []
