"""
Connector module for authentication endpoints.
Provides Flask route handlers for registration, login, and logout.
"""
import logging
from flask import request, jsonify, g
import auth
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

def register_endpoint():
    """Handle the register endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password are required"}), 400
        
        # Register user
        email = data.get("email", "")
        result, status_code = auth.register_user(data["username"], data["password"], email)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in register_endpoint: {str(e)}")
        return jsonify({"error": f"Registration error: {str(e)}"}), 500

def login_endpoint():
    """Handle the login endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password are required"}), 400
        
        # Login user
        result, status_code = auth.login_user(data["username"], data["password"])
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in login_endpoint: {str(e)}")
        return jsonify({"error": f"Login error: {str(e)}"}), 500

def logout_endpoint():
    """Handle the logout endpoint"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401
        
        token = auth_header.split(" ")[1]
        
        # Logout user
        result, status_code = auth.logout_user(token)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in logout_endpoint: {str(e)}")
        return jsonify({"error": f"Logout error: {str(e)}"}), 500

def get_current_user_endpoint():
    """Handle get current user endpoint"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401
        
        token = auth_header.split(" ")[1]
        
        # Validate token
        user_info = auth.validate_token(token)
        
        if not user_info:
            return jsonify({"error": "Invalid token"}), 401
        
        # Get full user info
        user_detail = auth.get_user_by_id(user_info["user_id"])
        
        if not user_detail:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify(user_detail), 200
    
    except Exception as e:
        logger.error(f"Error in get_current_user_endpoint: {str(e)}")
        return jsonify({"error": f"Error getting user info: {str(e)}"}), 500

def token_required(f):
    """Decorator for routes that require token authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401
        
        token = auth_header.split(" ")[1]
        
        # Validate token
        user_info = auth.validate_token(token)
        
        if not user_info:
            return jsonify({"error": "Invalid token"}), 401
        
        # Store user info in g object for the route to use
        g.user = user_info
        
        return f(*args, **kwargs)
    
    return decorated