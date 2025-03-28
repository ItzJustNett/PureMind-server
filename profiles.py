"""
Profiles module for the lessons API.
Manages user profiles including name, about section, cat selection, meowcoins, XP, and completed exercises.
Now includes streak tracking functionality.
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

# Valid illness IDs and their names
ILLNESSES = {
    0: "None",
    1: "Dyslexia",
    2: "Cerebral Palsy (Motor Impairment)",
    3: "Photosensitivity",
    4: "Epilepsy",
    5: "Color Blindness"
}

# Mapping of illness IDs to their Ukrainian names
ILLNESSES_UA = {
    0: "Немає",
    1: "Дислексія",
    2: "ДЦП (порушення моторики)",
    3: "Світлочутливість",
    4: "Епілепсія",
    5: "Дальтонізм"
}

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

def create_or_update_profile(user_id: str, name: str, about: str, cat_id: int, illness_id: int = 0) -> Tuple[Dict, int]:
    """Create or update a user profile"""
    # Validate cat_id
    if cat_id not in VALID_CAT_IDS:
        return {
            "error": f"Invalid cat_id. Must be one of {VALID_CAT_IDS}"
        }, 400
        
    # Validate illness_id
    if illness_id not in ILLNESSES:
        return {
            "error": f"Invalid illness_id. Must be one of {list(ILLNESSES.keys())}"
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
            "illness_id": illness_id,
            "illness_name": ILLNESSES[illness_id],
            "illness_name_ua": ILLNESSES_UA[illness_id],
            "meowcoins": 0,
            "xp": 0,
            "completed_exercises": {},
            "inventory": [],
            "equipped_items": [],
            # Initialize streak data for new profiles
            "streak": {
                "current_streak": 0,
                "longest_streak": 0,
                "last_activity_date": None
            }
        }
    else:
        profile = profiles_data[user_id]
        profile["name"] = name
        profile["about"] = about
        profile["cat_id"] = cat_id
        profile["illness_id"] = illness_id
        profile["illness_name"] = ILLNESSES[illness_id]
        profile["illness_name_ua"] = ILLNESSES_UA[illness_id]
        # Ensure streak data exists for existing profiles
        if "streak" not in profile:
            profile["streak"] = {
                "current_streak": 0,
                "longest_streak": 0,
                "last_activity_date": None
            }
    
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
    valid_sort_options = ['xp', 'meowcoins', 'streak']  # Added streak as sorting option
    
    if sort_by not in valid_sort_options:
        logger.warning(f"Invalid sort option: {sort_by}. Using default 'xp'.")
        sort_by = 'xp'
    
    # Convert to list and sort
    leaderboard = list(profiles_data.values())
    
    # Special handling for streak sorting
    if sort_by == 'streak':
        leaderboard.sort(
            key=lambda x: x.get("streak", {}).get("current_streak", 0), 
            reverse=True
        )
    else:
        leaderboard.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    
    # Limit results and return simplified data
    return [
        {
            "user_id": profile["user_id"],
            "name": profile["name"],
            "xp": profile.get("xp", 0),
            "meowcoins": profile.get("meowcoins", 0),
            "equipped_items": profile.get("equipped_items", []),
            "current_streak": profile.get("streak", {}).get("current_streak", 0),
            "longest_streak": profile.get("streak", {}).get("longest_streak", 0),
            "rank": idx + 1
        }
        for idx, profile in enumerate(leaderboard[:limit])
    ]

def update_streak(user_id: str) -> Dict:
    """Update the user's learning streak"""
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}
    
    # Ensure streak data exists
    if "streak" not in profile:
        profile["streak"] = {
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None
        }
    
    # Get current date in YYYY-MM-DD format
    today = datetime.datetime.now().date()
    today_str = today.isoformat()
    
    # Get last activity date
    last_date_str = profile["streak"].get("last_activity_date")
    
    # If this is the first activity ever, set streak to 1
    if not last_date_str:
        profile["streak"]["current_streak"] = 1
        profile["streak"]["longest_streak"] = 1
        profile["streak"]["last_activity_date"] = today_str
    else:
        # Convert last activity date string to datetime.date object
        last_date = datetime.date.fromisoformat(last_date_str)
        
        # Calculate the difference in days
        delta_days = (today - last_date).days
        
        # If already logged in today, no change to streak
        if delta_days == 0:
            pass  # Streak unchanged
        # If consecutive day (yesterday), increment streak
        elif delta_days == 1:
            profile["streak"]["current_streak"] += 1
            # Update longest streak if current streak is longer
            if profile["streak"]["current_streak"] > profile["streak"]["longest_streak"]:
                profile["streak"]["longest_streak"] = profile["streak"]["current_streak"]
            profile["streak"]["last_activity_date"] = today_str
        # If more than one day gap, reset streak to 1
        else:
            profile["streak"]["current_streak"] = 1
            profile["streak"]["last_activity_date"] = today_str
    
    # Save the updated profile
    save_profiles_data()
    
    return {
        "current_streak": profile["streak"]["current_streak"],
        "longest_streak": profile["streak"]["longest_streak"],
        "last_activity_date": profile["streak"]["last_activity_date"]
    }

def get_streak(user_id: str) -> Tuple[Dict, int]:
    """Get a user's streak information"""
    profile = profiles_data.get(user_id)
    if not profile:
        return {"error": "Profile not found"}, 404
    
    # Ensure streak data exists
    if "streak" not in profile:
        profile["streak"] = {
            "current_streak": 0,
            "longest_streak": 0,
            "last_activity_date": None
        }
        save_profiles_data()
    
    return {
        "current_streak": profile["streak"]["current_streak"],
        "longest_streak": profile["streak"]["longest_streak"],
        "last_activity_date": profile["streak"]["last_activity_date"]
    }, 200

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
    
    # Update streak when an exercise is completed
    streak_info = update_streak(user_id)
    
    # Save profiles data
    save_profiles_data()
    
    return {
        "success": True,
        "exercise_completed": True,
        "meowcoins_earned": meowcoins_earned,
        "xp_earned": xp_earned,
        "total_meowcoins": profile["meowcoins"],
        "total_xp": profile["xp"],
        "streak": streak_info
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
    
    # Update streak when purchasing an item (counts as activity)
    update_streak(user_id)
    
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
