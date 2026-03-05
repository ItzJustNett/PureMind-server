"""
Authentication module for the lessons API.
Handles user registration, login, and token management.
"""
import json
import os
import logging
import hashlib
import secrets
import time
from typing import Dict, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Global variables
users_data = {}
active_tokens = {}  # Map of token -> user_id

def load_users_data(file_path: str = 'users.json') -> Dict:
    """Load users data from the JSON file"""
    global users_data
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                users_data = json.load(file)
            logger.info(f"Loaded {len(users_data)} users")
        else:
            # Create empty users file if it doesn't exist
            users_data = {}
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(users_data, file, indent=2)
            logger.info("Created empty users file")
        return users_data
    except Exception as e:
        logger.error(f"Error loading users data: {e}")
        return {}

def save_users_data(file_path: str = 'users.json') -> bool:
    """Save users data to the JSON file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(users_data, file, indent=2, ensure_ascii=False)
        logger.info("Saved users data")
        return True
    except Exception as e:
        logger.error(f"Error saving users data: {e}")
        return False

def hash_password(password: str) -> str:
    """Hash a password for secure storage"""
    # Using SHA-256 for simplicity; in production, use a proper password hashing algorithm
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str, email: str = "") -> Tuple[Dict, int]:
    """Register a new user"""
    # Check if username already exists
    if username in users_data:
        return {"error": "Username already exists"}, 400

    # Create new user
    user_id = f"user_{len(users_data) + 1}"
    users_data[username] = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "created_at": time.time()
    }
    
    # Save users data
    save_users_data()
    
    return {
        "message": "User registered successfully",
        "username": username,
        "user_id": user_id
    }, 201

def login_user(username: str, password: str) -> Tuple[Dict, int]:
    """Login a user and generate a token"""
    # Check if username exists
    if username not in users_data:
        return {"error": "Invalid username or password"}, 401
    
    # Check password
    if users_data[username]["password_hash"] != hash_password(password):
        return {"error": "Invalid username or password"}, 401
    
    # Generate token
    token = secrets.token_hex(32)
    user_id = users_data[username]["id"]
    
    # Store token
    active_tokens[token] = {
        "user_id": user_id,
        "username": username,
        "created_at": time.time()
    }
    
    return {
        "message": "Login successful",
        "token": token,
        "user_id": user_id,
        "username": username
    }, 200

def logout_user(token: str) -> Tuple[Dict, int]:
    """Logout a user by invalidating their token"""
    if token in active_tokens:
        username = active_tokens[token]["username"]
        del active_tokens[token]
        return {"message": f"User {username} logged out successfully"}, 200
    
    return {"error": "Invalid token"}, 401

def validate_token(token: str) -> Optional[Dict]:
    """Validate a token and return user information"""
    if token in active_tokens:
        return active_tokens[token]
    
    return None

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by ID"""
    for username, user_data in users_data.items():
        if user_data["id"] == user_id:
            # Return a copy without password hash
            user_info = user_data.copy()
            user_info.pop("password_hash", None)
            return user_info
    
    return None

# Initialize user data when the module is imported
load_users_data()