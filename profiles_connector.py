"""
Connector module for profile endpoints.
Provides Flask route handlers for profile management.
Now includes streak tracking endpoints.
"""
import logging
from flask import request, jsonify, g
import profiles
from auth_connector import token_required

# Configure logging
logger = logging.getLogger(__name__)

@token_required
def get_profile_endpoint(user_id=None):
    """Handle the get profile endpoint"""
    try:
        # If no user_id is provided, use the current user's ID
        if user_id is None:
            user_id = g.user["user_id"]
        
        # Get profile
        profile = profiles.get_profile(user_id)
        
        if not profile:
            return jsonify({
                "message": "Profile not found, but you can create one",
                "user_id": user_id
            }), 404
        
        return jsonify(profile), 200
    
    except Exception as e:
        logger.error(f"Error in get_profile_endpoint: {str(e)}")
        return jsonify({"error": f"Error getting profile: {str(e)}"}), 500

@token_required
def create_or_update_profile_endpoint():
    """Handle the create or update profile endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        required_fields = ["name", "about", "cat_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
                
        # Get illness_id if provided, default to 0 (none)
        illness_id = data.get("illness_id", 0)
        try:
            illness_id = int(illness_id)
        except ValueError:
            return jsonify({"error": "illness_id must be an integer"}), 400
        
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Create or update profile
        try:
            cat_id = int(data["cat_id"])
        except ValueError:
            return jsonify({"error": "cat_id must be an integer"}), 400
        
        result, status_code = profiles.create_or_update_profile(
            user_id, 
            data["name"], 
            data["about"], 
            cat_id,
            illness_id
        )
        
        # Update streak for this activity
        profiles.update_streak(user_id)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in create_or_update_profile_endpoint: {str(e)}")
        return jsonify({"error": f"Error updating profile: {str(e)}"}), 500

# New endpoint for streak management
@token_required
def get_streak_endpoint():
    """Handle the get streak endpoint"""
    try:
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Get streak info
        streak_info, status_code = profiles.get_streak(user_id)
        
        return jsonify(streak_info), status_code
    
    except Exception as e:
        logger.error(f"Error in get_streak_endpoint: {str(e)}")
        return jsonify({"error": f"Error getting streak info: {str(e)}"}), 500

@token_required
def update_streak_endpoint():
    """Handle the update streak endpoint"""
    try:
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Update streak (this will be called when any learning activity happens)
        streak_info = profiles.update_streak(user_id)
        
        return jsonify(streak_info), 200
    
    except Exception as e:
        logger.error(f"Error in update_streak_endpoint: {str(e)}")
        return jsonify({"error": f"Error updating streak: {str(e)}"}), 500

@token_required
def delete_profile_endpoint():
    """Handle the delete profile endpoint"""
    try:
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Delete profile
        result, status_code = profiles.delete_profile(user_id)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in delete_profile_endpoint: {str(e)}")
        return jsonify({"error": f"Error deleting profile: {str(e)}"}), 500

def list_profiles_endpoint():
    """Handle the list profiles endpoint (admin only)"""
    try:
        # For simplicity, no admin check is implemented here
        # In a real application, you should check if the user is an admin
        
        profiles_list = profiles.list_profiles()
        
        return jsonify({
            "count": len(profiles_list),
            "profiles": profiles_list
        }), 200
    
    except Exception as e:
        logger.error(f"Error in list_profiles_endpoint: {str(e)}")
        return jsonify({"error": f"Error listing profiles: {str(e)}"}), 500

# Leaderboard endpoint - updated to include streak
def get_leaderboard_endpoint():
    """Handle the get leaderboard endpoint"""
    try:
        sort_by = request.args.get('sort_by', 'xp')
        limit = request.args.get('limit', 10)
        
        try:
            limit = int(limit)
        except ValueError:
            limit = 10
        
        leaderboard = profiles.get_leaderboard(sort_by, limit)
        
        return jsonify({
            "sort_by": sort_by,
            "count": len(leaderboard),
            "leaderboard": leaderboard
        }), 200
    
    except Exception as e:
        logger.error(f"Error in get_leaderboard_endpoint: {str(e)}")
        return jsonify({"error": f"Error getting leaderboard: {str(e)}"}), 500

@token_required
def check_exercise_answers_endpoint(exercise_id):
    """Handle the check exercise answers endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "correct_answers" not in data:
            return jsonify({"error": "Missing required field: correct_answers"}), 400
        
        # Get user_id from token
        user_id = g.user["user_id"]
        
        try:
            correct_answers = int(data["correct_answers"])
        except ValueError:
            return jsonify({"error": "correct_answers must be an integer"}), 400
        
        # Check answers and award rewards (this now includes streak update)
        result, status_code = profiles.check_exercise_answers(
            user_id,
            exercise_id,
            correct_answers
        )
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in check_exercise_answers_endpoint: {str(e)}")
        return jsonify({"error": f"Error checking answers: {str(e)}"}), 500

@token_required
def get_store_items_endpoint():
    """Handle the get store items endpoint"""
    try:
        store_items = profiles.get_store_items()
        
        return jsonify({
            "count": len(store_items),
            "items": store_items
        }), 200
    
    except Exception as e:
        logger.error(f"Error in get_store_items_endpoint: {str(e)}")
        return jsonify({"error": f"Error getting store items: {str(e)}"}), 500

@token_required
def buy_item_endpoint():
    """Handle the buy item endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "item_id" not in data:
            return jsonify({"error": "Missing required field: item_id"}), 400
        
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Buy the item
        result, status_code = profiles.buy_item(
            user_id,
            data["item_id"]
        )
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in buy_item_endpoint: {str(e)}")
        return jsonify({"error": f"Error buying item: {str(e)}"}), 500

@token_required
def equip_item_endpoint():
    """Handle the equip item endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "item_id" not in data:
            return jsonify({"error": "Missing required field: item_id"}), 400
        
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Equip the item
        result, status_code = profiles.equip_item(
            user_id,
            data["item_id"]
        )
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in equip_item_endpoint: {str(e)}")
        return jsonify({"error": f"Error equipping item: {str(e)}"}), 500

@token_required
def unequip_item_endpoint():
    """Handle the unequip item endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "item_id" not in data:
            return jsonify({"error": "Missing required field: item_id"}), 400
        
        # Get user_id from token
        user_id = g.user["user_id"]
        
        # Unequip the item
        result, status_code = profiles.unequip_item(
            user_id,
            data["item_id"]
        )
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in unequip_item_endpoint: {str(e)}")
        return jsonify({"error": f"Error unequipping item: {str(e)}"}), 500
