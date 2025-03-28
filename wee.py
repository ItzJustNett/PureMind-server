"""
Main server file for the lessons API.
This file creates a Flask server that exposes endpoints for all lesson functionality.
"""
from flask import Flask, request, jsonify, send_file
import lessons_connector
import lessons_manager
import auth_connector
import profiles_connector
import debug_routes
import improved_error_handling
import logging
import os
import json
import tts
import stt
from transformers import logging as transformers_logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Set transformers logging level
transformers_logging.set_verbosity_error()

# Initialize lessons data
lessons_connector.init_lessons_data()
logger.info(f"Lessons data initialized with {len(lessons_manager.lessons_data)} lessons")

# Initialize Whisper model
try:
    stt.initialize_whisper()
    logger.info("Whisper model initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Whisper: {str(e)}")

# Register debug routes
debug_routes.register_debug_routes(app)

# Register improved error handling
improved_error_handling.register_improved_endpoints(app)

# Define routes
@app.route('/api/lessons', methods=['GET'])
def list_lessons():
    """Endpoint to list all lessons"""
    return lessons_connector.list_lessons_endpoint()

@app.route('/api/lessons/<lesson_id>', methods=['GET'])
def get_lesson(lesson_id):
    """Endpoint to get a specific lesson by ID"""
    return lessons_connector.get_lesson_endpoint(lesson_id)

@app.route('/api/lessons/search', methods=['GET'])
def search_lessons():
    """Endpoint to search for lessons"""
    query = request.args.get('q', '')
    return lessons_connector.search_lessons_endpoint(query)

@app.route('/api/lessons/<lesson_id>/youtube', methods=['GET'])
def get_youtube_link(lesson_id):
    """Endpoint to get a YouTube link for a specific lesson"""
    return lessons_connector.get_youtube_link_endpoint(lesson_id)

# Note: conspect and test endpoints are overridden by improved_error_handling.py

@app.route('/api/test-openrouter', methods=['GET'])
def test_openrouter():
    """Endpoint to test the OpenRouter connection"""
    return lessons_connector.test_openrouter_connection_endpoint()

# Add a route to add a new lesson
@app.route('/api/lessons', methods=['POST'])
def add_lesson():
    """Endpoint to add a new lesson"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate required fields
        required_fields = ['id', 'title', 'course_id']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Add lesson to lessons_data
        lessons_manager.lessons_data[data['id']] = data
        
        # Save to file
        with open('lessons.json', 'w', encoding='utf-8') as f:
            json.dump(lessons_manager.lessons_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "Lesson added successfully"}), 201
    except Exception as e:
        logger.error(f"Error adding lesson: {str(e)}")
        return jsonify({"error": f"Error adding lesson: {str(e)}"}), 500

# Authentication routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Endpoint to register a new user"""
    return auth_connector.register_endpoint()

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Endpoint to login a user"""
    return auth_connector.login_endpoint()

# Add this route to wee.py just before the closing "if __name__ == '__main__':" section

@app.route('/api/lessons/<lesson_id>/test', methods=['GET'])
def generate_lesson_test(lesson_id):
    """Endpoint to generate a test for a specific lesson"""
    return lessons_connector.generate_lesson_test_endpoint(lesson_id)

@app.route('/api/lessons/<lesson_id>/video-url', methods=['GET'])
def get_video_url(lesson_id):
    """Endpoint to get only the video URL for a specific lesson"""
    return lessons_connector.get_video_url_endpoint(lesson_id)

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Endpoint to logout a user"""
    return auth_connector.logout_endpoint()

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Endpoint to get current user info"""
    return auth_connector.get_current_user_endpoint()

# Profile routes
@app.route('/api/profiles/me', methods=['GET'])
def get_my_profile():
    """Endpoint to get current user's profile"""
    return profiles_connector.get_profile_endpoint()

@app.route('/api/profiles/<user_id>', methods=['GET'])
def get_profile(user_id):
    """Endpoint to get a specific user's profile"""
    return profiles_connector.get_profile_endpoint(user_id)

@app.route('/api/profiles', methods=['POST', 'PUT'])
def update_profile():
    """Endpoint to create or update current user's profile"""
    return profiles_connector.create_or_update_profile_endpoint()

@app.route('/api/profiles', methods=['DELETE'])
def delete_profile():
    """Endpoint to delete current user's profile"""
    return profiles_connector.delete_profile_endpoint()

@app.route('/api/profiles/all', methods=['GET'])
def list_profiles():
    """Endpoint to list all profiles (admin only)"""
    return profiles_connector.list_profiles_endpoint()

# New gamification endpoints
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Endpoint to get the leaderboard"""
    return profiles_connector.get_leaderboard_endpoint()

@app.route('/api/exercises/<exercise_id>/check', methods=['POST'])
def check_exercise_answers(exercise_id):
    """Endpoint to check exercise answers and award rewards"""
    return profiles_connector.check_exercise_answers_endpoint(exercise_id)

@app.route('/api/store', methods=['GET'])
def get_store_items():
    """Endpoint to get the list of items available in the store"""
    return profiles_connector.get_store_items_endpoint()

@app.route('/api/store/buy', methods=['POST'])
def buy_item():
    """Endpoint to buy an item from the store"""
    return profiles_connector.buy_item_endpoint()

@app.route('/api/inventory/equip', methods=['POST'])
def equip_item():
    """Endpoint to equip an item from the user's inventory"""
    return profiles_connector.equip_item_endpoint()

@app.route('/api/inventory/unequip', methods=['POST'])
def unequip_item():
    """Endpoint to unequip an item"""
    return profiles_connector.unequip_item_endpoint()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint to provide basic information about the API"""
    try:
        # Get quick stats
        lesson_count = len(lessons_manager.lessons_data)
        course_ids = set()
        for lesson in lessons_manager.lessons_data.values():
            if 'course_id' in lesson:
                course_ids.add(lesson.get('course_id'))
        
        return jsonify({
            "name": "Lessons API",
            "description": "API for managing lessons, courses, users, and profiles",
            "status": {
                "lessons_loaded": lesson_count,
                "courses_available": len(course_ids),
                "api_status": "running"
            },
            "endpoints": {
                "lessons": [
                    "/api/lessons",
                    "/api/lessons/<lesson_id>",
                    "/api/lessons/search?q=<query>",
                    "/api/lessons/<lesson_id>/youtube",
                    "/api/lessons/<lesson_id>/conspect",
                    "/api/courses/<course_id>/test",
                    "/api/test-openrouter"
                ],
                "authentication": [
                    "/api/auth/register",
                    "/api/auth/login",
                    "/api/auth/logout",
                    "/api/auth/me"
                ],
                "profiles": [
                    "/api/profiles/me",
                    "/api/profiles/<user_id>",
                    "/api/profiles",
                    "/api/profiles/all"
                ],
                "gamification": [
                    "/api/leaderboard",
                    "/api/exercises/<exercise_id>/check",
                    "/api/store",
                    "/api/store/buy",
                    "/api/inventory/equip",
                    "/api/inventory/unequip"
                ],
                "debug": [
                    "/api/debug/overview",
                    "/api/debug/lesson/<lesson_id>",
                    "/api/debug/course/<course_id>"
                ]
            }
        })
    except Exception as e:
        logger.error(f"Error in home endpoint: {e}")
        return jsonify({
            "name": "Lessons API",
            "description": "API for managing lessons, courses, users, and profiles",
            "status": "Error getting status information",
            "error": str(e)
        })

# Text-to-Speech endpoint
@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """Convert text to speech and return audio file"""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "Text is required"}), 400
        
        text = data['text']
        language = data.get('language', 'en')
        
        # Generate speech
        filepath = tts.generate_speech(text, language)
        
        # Return the file
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        logger.error(f"Error in text_to_speech: {str(e)}")
        return jsonify({"error": f"Error generating speech: {str(e)}"}), 500

# Speech-to-Text endpoint
@app.route('/api/stt', methods=['POST'])
def speech_to_text():
    """Convert speech to text using Whisper via Transformers"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Save uploaded file
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)
        
        # Transcribe the audio
        from stt import transcribe_audio, cleanup_resources
        text = transcribe_audio(filepath)
        
        # Clean up resources to free memory
        cleanup_resources()
        
        # Clean up the file
        os.remove(filepath)
        
        return jsonify({"text": text})
    except Exception as e:
        logger.error(f"Error in speech_to_text: {str(e)}")
        return jsonify({"error": f"Error transcribing speech: {str(e)}"}), 500

@app.route('/api/openrouter/request', methods=['POST'])
def openrouter_request_route():
    """Endpoint to make a request to OpenRouter API"""
    return lessons_connector.openrouter_request_endpoint()

# Run the server if this file is executed directly
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Print some useful debug info
    logger.info(f"Lessons loaded: {len(lessons_manager.lessons_data)}")
    logger.info(f"OpenRouter API Key configured: {bool(lessons_manager.OPENROUTER_API_KEY)}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=True)
    logger.info(f"Server running on port {port}")