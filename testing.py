#!/usr/bin/env python3
"""
Test script for the gamification features of the Lessons API
"""
import requests
import json
import time

API_BASE_URL = "http://localhost:5000/api"
TEST_USER = {
    "username": "testuser",
    "password": "testpassword"
}

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"   {title}")
    print("=" * 80 + "\n")

def pretty_print_json(data):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print()

def test_gamification():
    """Test the gamification features"""
    print_section("TESTING GAMIFICATION FEATURES")
    
    # Register user
    print("Registering test user...")
    register_response = requests.post(f"{API_BASE_URL}/auth/register", json=TEST_USER)
    register_data = register_response.json()
    pretty_print_json(register_data)
    
    # Login
    print("Logging in...")
    login_response = requests.post(f"{API_BASE_URL}/auth/login", json=TEST_USER)
    login_data = login_response.json()
    pretty_print_json(login_data)
    
    if "token" not in login_data:
        print("Failed to login, aborting test")
        return
    
    # Set auth header for subsequent requests
    auth_header = {"Authorization": f"Bearer {login_data['token']}"}
    
    # Create profile
    print("Creating profile...")
    profile_data = {
        "name": "Test User",
        "about": "This is a test profile for gamification features",
        "cat_id": 0
    }
    profile_response = requests.post(f"{API_BASE_URL}/profiles", json=profile_data, headers=auth_header)
    profile_result = profile_response.json()
    pretty_print_json(profile_result)
    
    # Check initial profile (should have 0 meowcoins and 0 XP)
    print("Checking initial profile...")
    profile_get_response = requests.get(f"{API_BASE_URL}/profiles/me", headers=auth_header)
    initial_profile = profile_get_response.json()
    pretty_print_json(initial_profile)
    
    # Check exercise answers
    print("Checking exercise answers...")
    exercise_data = {
        "correct_answers": 8
    }
    exercise_response = requests.post(
        f"{API_BASE_URL}/exercises/exercise_001/check", 
        json=exercise_data, 
        headers=auth_header
    )
    exercise_result = exercise_response.json()
    pretty_print_json(exercise_result)
    
    # Check updated profile
    print("Checking updated profile (after exercise)...")
    profile_updated_response = requests.get(f"{API_BASE_URL}/profiles/me", headers=auth_header)
    updated_profile = profile_updated_response.json()
    pretty_print_json(updated_profile)
    
    # Get store items
    print("Getting store items...")
    store_response = requests.get(f"{API_BASE_URL}/store", headers=auth_header)
    store_items = store_response.json()
    pretty_print_json(store_items)
    
    # Earn more meowcoins by completing more exercises
    print("Earning more meowcoins...")
    for i in range(2, 6):
        exercise_data = {
            "correct_answers": 10
        }
        exercise_response = requests.post(
            f"{API_BASE_URL}/exercises/exercise_00{i}/check", 
            json=exercise_data, 
            headers=auth_header
        )
        exercise_result = exercise_response.json()
        print(f"Exercise {i} completed: {exercise_result['meowcoins_earned']} meowcoins earned")
    
    # Check profile with earned meowcoins
    print("Checking profile with earned meowcoins...")
    profile_coins_response = requests.get(f"{API_BASE_URL}/profiles/me", headers=auth_header)
    coins_profile = profile_coins_response.json()
    pretty_print_json(coins_profile)
    
    # Buy an item
    print("Buying an item...")
    buy_data = {
        "item_id": "sunglasses"
    }
    buy_response = requests.post(f"{API_BASE_URL}/store/buy", json=buy_data, headers=auth_header)
    buy_result = buy_response.json()
    pretty_print_json(buy_result)
    
    # Equip the item
    print("Equipping the item...")
    equip_data = {
        "item_id": "sunglasses"
    }
    equip_response = requests.post(f"{API_BASE_URL}/inventory/equip", json=equip_data, headers=auth_header)
    equip_result = equip_response.json()
    pretty_print_json(equip_result)
    
    # Check updated profile with equipped item
    print("Checking profile with equipped item...")
    final_profile_response = requests.get(f"{API_BASE_URL}/profiles/me", headers=auth_header)
    final_profile = final_profile_response.json()
    pretty_print_json(final_profile)
    
    # Check the leaderboard
    print("Checking leaderboard...")
    leaderboard_response = requests.get(f"{API_BASE_URL}/leaderboard")
    leaderboard = leaderboard_response.json()
    pretty_print_json(leaderboard)
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_gamification()