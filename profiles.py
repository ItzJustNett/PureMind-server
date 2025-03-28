"""
Profiles module for the lessons API.
Manages user profiles including name, about section, cat selection, meowcoins, XP, and completed exercises.
"""
import json
import os
import logging
import datetime
from typing import Dict, Optional, List, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Global variables
profiles_data = {}  # Map of user_id -> profile

# Valid cat IDs
VALID_CAT_IDS = [0, 1, 10]

# Valid health condition options
VALID_HEALTH_CONDITIONS = ["none", "dyslexia", "cerebral_palsy", "photosensitivity", "epilepsy"]

# Valid chronotype options
VALID_CHRONOTYPES = ["owl", "early_bird"]

# Store items configuration
STORE_ITEMS = {
    "sunglasses": {"price": 100, "description": "Cool sunglasses for your cat"},
    "cap": {"price": 150, "description": "A stylish cap for your cat"},
    "moustache": {"price": 200, "description": "A fancy moustache for your cat"},
    "butterfly": {"price": 250, "description": "A cute butterfly accessory for your cat"}
}

def load_profiles_data(file_path: str = 'profiles.json') -> Dict:
    """Load profiles data from the JSON file"""
    global profiles_data
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                profiles_data = json.load(file)
            logger.info(f"Loaded {len(profiles_data)} profiles")
        else:
            # Create empty profiles file if it doesn't exist
            profiles_data = {}
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(profiles_data, file, indent=2)
            logger.info("Created empty profiles file")
        return profiles_data
    except Exception as e:
        logger.error(f"Error loading profiles data: {e}")
        return {}

def save_profiles_data(file_path: str = 'profiles.json') -> bool:
    """Save profiles data to the JSON file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(profiles_data, file, indent=2, ensure_ascii=False)
        logger.info("Saved profiles data")
        return True
    except Exception as e:
        logger.error(f"Error saving profiles data: {e}")
        return False

def get_profile(user_id: str) -> Optional[Dict]:
    """Get a profile by user ID"""
    return profiles_data.get(user_id)

def create_or_update_profile(user_id: str, name: str, about: str, cat_id: int, 
                           health_condition: str = "none", chronotype: str = None) -> Tuple[Dict, int]:
    """Create or update a user profile"""
    # Validate cat_id
    if cat_id not in VALID_CAT_IDS:
        return {
            "error": f"Invalid cat_id. Must be one of {VALID_CAT_IDS}"
        }, 400
    
    # Validate health_condition
    if health_condition not in VALID_HEALTH_CONDITIONS:
        return {
            "error": f"Invalid health_condition. Must be one of {VALID_HEALTH_CONDITIONS}"
        }, 400
    
    # Validate chronotype if provided
    if chronotype is not None and chronotype not in VALID_CHRONOTYPES:
        return {
            "error": f"Invalid chronotype. Must be one of {VALID_CHRONOTYPES}"
        }, 400
    
    # Check if profile already exists
    is_new = user_id not in profiles_data
    
    # Initialize new profile or get existing one
    if is_new:
        profile = {
            "user_id": user_id,
            "name": name,
            "about": about,
            "cat_id": cat_id,
            "health_condition": health_condition,
            "chronotype": chronotype,
            "meowcoins": 0,
            "xp": 0,
            "completed_exercises": {},
            "inventory": [],
            "equipped_items": []
        }
    else:
        profile = profiles_data[user_id]
        profile["name"] = name
        profile["about"] = about
        profile["cat_id"] = cat_id
        profile["health_condition"] = health_condition
        if chronotype is not None:
            profile["chronotype"] = chronotype
    
    # Save updated profile
    profiles_data[user_id] = profile
    
    # Save profiles data
    save_profiles_data()
    
    status_code = 201 if is_new else 200
    return profiles_data[user_id], status_code

def delete_profile(user_id: str) -> Tuple[Dict, int]:
    """Delete a user profile"""
    if user_id not in profiles_data:
        return {"error": "Profile not found"}, 404
    
    # Delete profile
    del profiles_data[user_id]
    
    # Save profiles data
    save_profiles_data()
    
    return {"message": f"Profile for user {user_id} deleted successfully"}, 200

def list_profiles() -> List[Dict]:
    """List all profiles (for admin use)"""
    return list(profiles_data.values())

def get_leaderboard(sort_by: str = 'xp', limit: int = 10) -> List[Dict]:
    """Get the leaderboard sorted by XP or meowcoins"""
    valid_sort_options = ['xp', 'meowcoins']
    
    if sort_by not in valid_sort_options:
        logger.warning(f"Invalid sort option: {sort_by}. Using default 'xp'.")
        sort_by = 'xp'
    
    # Convert to list and sort
    leaderboard = list(profiles_data.values())
    leaderboard.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    
    # Limit results and return simplified data
    return [
        {
            "user_id": profile["user_id"],
            "name": profile["name"],
            "xp": profile.get("xp", 0),
            "meowcoins": profile.get("meowcoins", 0),
            "equipped_items": profile.get("equipped_items", []),
            "rank": idx + 1
        }
        for idx, profile in enumerate(leaderboard[:limit])
    ]

def check_exercise_answers(user_id: str, exercise_id: str, correct_answers: int) -> Tuple[Dict, int]:
    """Check exercise answers and award meowcoins and XP"""
    # Validate input
    if not user_id or not exercise_id:
        return {"error": "User ID and exercise ID are required"}, 400
    
    if not isinstance(correct_answers, int) or correct_answers < 0:
        return {"error": "correct_answers must be a non-negative integer"}, 400
    
    # Get user profile
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}, 404
    
    # Initialize profile fields if they don't exist
    if "meowcoins" not in profile:
        profile["meowcoins"] = 0
    if "xp" not in profile:
        profile["xp"] = 0
    if "completed_exercises" not in profile:
        profile["completed_exercises"] = {}
    
    # Calculate rewards
    meowcoins_earned = correct_answers * 2  # 2 meowcoins per correct answer
    
    # Cap at 20 meowcoins per exercise for simplicity
    if meowcoins_earned > 20:
        meowcoins_earned = 20
    
    # Calculate XP based on correct answers (simplified)
    xp_earned = min(correct_answers * 2, 20)  # Cap at 20 XP
    
    # Check if exercise was already completed (just for tracking purposes)
    already_completed = exercise_id in profile["completed_exercises"]
    previous_reward = 0
    
    if already_completed:
        previous_attempt = profile["completed_exercises"][exercise_id]
        previous_reward = previous_attempt.get("meowcoins_earned", 0)
        # We'll still track previous attempts, but always give full rewards
    
    # Always award full meowcoins and XP regardless of previous completions
    # This allows users to farm meowcoins by repeatedly doing the same exercise
    
    # Update profile
    profile["meowcoins"] += meowcoins_earned
    profile["xp"] += xp_earned
    
    # Record completion
    profile["completed_exercises"][exercise_id] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "correct_answers": correct_answers,
        "meowcoins_earned": meowcoins_earned,  # Always record the current amount earned
        "xp_earned": xp_earned,
        "completion_count": profile["completed_exercises"].get(exercise_id, {}).get("completion_count", 0) + 1
    }
    
    # Save profiles data
    save_profiles_data()
    
    return {
        "success": True,
        "exercise_completed": True,
        "meowcoins_earned": meowcoins_earned,
        "xp_earned": xp_earned,
        "total_meowcoins": profile["meowcoins"],
        "total_xp": profile["xp"]
    }, 200

def get_store_items() -> Dict:
    """Get the list of items available in the store"""
    return STORE_ITEMS

def buy_item(user_id: str, item_id: str) -> Tuple[Dict, int]:
    """Buy an item from the store"""
    # Validate item exists
    if item_id not in STORE_ITEMS:
        return {"error": f"Item '{item_id}' not found in store"}, 404
    
    # Get user profile
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}, 404
    
    # Check if user has enough meowcoins
    item_price = STORE_ITEMS[item_id]["price"]
    if profile.get("meowcoins", 0) < item_price:
        return {"error": f"Not enough meowcoins. Need {item_price}, have {profile.get('meowcoins', 0)}"}, 400
    
    # Check if user already has the item
    if "inventory" not in profile:
        profile["inventory"] = []
    
    if item_id in profile["inventory"]:
        return {"error": f"You already own the '{item_id}' item"}, 400
    
    # Purchase the item
    profile["meowcoins"] -= item_price
    profile["inventory"].append(item_id)
    
    # Save profiles data
    save_profiles_data()
    
    return {
        "success": True,
        "message": f"Successfully purchased '{item_id}'",
        "remaining_meowcoins": profile["meowcoins"],
        "inventory": profile["inventory"]
    }, 200

def equip_item(user_id: str, item_id: str) -> Tuple[Dict, int]:
    """Equip an item from the user's inventory"""
    # Get user profile
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}, 404
    
    # Check if user has the item
    if "inventory" not in profile:
        profile["inventory"] = []
    
    if item_id not in profile["inventory"]:
        return {"error": f"You don't own the '{item_id}' item"}, 400
    
    # Initialize equipped items if needed
    if "equipped_items" not in profile:
        profile["equipped_items"] = []
    
    # Check if already equipped
    if item_id in profile["equipped_items"]:
        return {"error": f"The '{item_id}' item is already equipped"}, 400
    
    # Equip the item
    profile["equipped_items"].append(item_id)
    
    # Save profiles data
    save_profiles_data()
    
    return {
        "success": True,
        "message": f"Successfully equipped '{item_id}'",
        "equipped_items": profile["equipped_items"]
    }, 200

def unequip_item(user_id: str, item_id: str) -> Tuple[Dict, int]:
    """Unequip an item"""
    # Get user profile
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}, 404
    
    # Check if item is equipped
    if "equipped_items" not in profile or item_id not in profile["equipped_items"]:
        return {"error": f"The '{item_id}' item is not currently equipped"}, 400
    
    # Unequip the item
    profile["equipped_items"].remove(item_id)
    
    # Save profiles data
    save_profiles_data()
    
    return {
        "success": True,
        "message": f"Successfully unequipped '{item_id}'",
        "equipped_items": profile["equipped_items"]
    }, 200

# Initialize profiles data when the module is imported
load_profiles_data()