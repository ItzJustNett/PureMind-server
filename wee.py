"""
Main server file for the lessons API.
This file creates a FastAPI server that exposes endpoints for all lesson functionality.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import lessons_connector
import lessons_manager
import auth_connector
import profiles_connector
import debug_routes
import improved_error_handling
import speech_connector
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Lessons API",
    description="API for managing lessons, courses, users, and profiles",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize lessons data
lessons_connector.init_lessons_data()
logger.info(f"Lessons data initialized with {len(lessons_manager.lessons_data)} lessons")

# Register debug routes
debug_routes.register_debug_routes(app)

# Register improved error handling
improved_error_handling.register_improved_endpoints(app)

# Lessons endpoints
@app.get('/api/lessons')
def list_lessons():
    """Endpoint to list all lessons"""
    return lessons_connector.list_lessons_endpoint()

@app.get('/api/lessons/{lesson_id}')
def get_lesson(lesson_id: str):
    """Endpoint to get a specific lesson by ID"""
    return lessons_connector.get_lesson_endpoint(lesson_id)

@app.get('/api/lessons/search')
def search_lessons(q: str = ''):
    """Endpoint to search for lessons"""
    return lessons_connector.search_lessons_endpoint(q)

@app.get('/api/lessons/{lesson_id}/youtube')
def get_youtube_link(lesson_id: str):
    """Endpoint to get a YouTube link for a specific lesson"""
    return lessons_connector.get_youtube_link_endpoint(lesson_id)

@app.get('/api/test-openrouter')
def test_openrouter():
    """Endpoint to test the OpenRouter connection"""
    return lessons_connector.test_openrouter_connection_endpoint()

@app.post('/api/lessons')
async def add_lesson(request: Request):
    """Endpoint to add a new lesson"""
    try:
        data = await request.json()
        if not data:
            return JSONResponse({"error": "No data provided"}, status_code=400)

        # Validate required fields
        required_fields = ['id', 'title', 'course_id']
        for field in required_fields:
            if field not in data:
                return JSONResponse({"error": f"Missing required field: {field}"}, status_code=400)

        # Add lesson to lessons_data
        lessons_manager.lessons_data[data['id']] = data

        # Save to file
        import json
        with open('lessons.json', 'w', encoding='utf-8') as f:
            json.dump(lessons_manager.lessons_data, f, indent=2, ensure_ascii=False)

        return JSONResponse({"success": True, "message": "Lesson added successfully"}, status_code=201)
    except Exception as e:
        logger.error(f"Error adding lesson: {str(e)}")
        return JSONResponse({"error": f"Error adding lesson: {str(e)}"}, status_code=500)

@app.get('/api/lessons/{lesson_id}/test')
def generate_lesson_test(lesson_id: str):
    """Endpoint to generate a test for a specific lesson"""
    return lessons_connector.generate_lesson_test_endpoint(lesson_id)

@app.get('/api/lessons/{lesson_id}/video-url')
def get_video_url(lesson_id: str):
    """Endpoint to get only the video URL for a specific lesson"""
    return lessons_connector.get_video_url_endpoint(lesson_id)

# Authentication endpoints
@app.post('/api/auth/register')
async def register(request: Request):
    """Endpoint to register a new user"""
    return auth_connector.register_endpoint()

@app.post('/api/auth/login')
async def login(request: Request):
    """Endpoint to login a user"""
    return auth_connector.login_endpoint()

@app.post('/api/auth/logout')
async def logout(request: Request):
    """Endpoint to logout a user"""
    return auth_connector.logout_endpoint()

@app.get('/api/auth/me')
def get_current_user():
    """Endpoint to get current user info"""
    return auth_connector.get_current_user_endpoint()

# Profile endpoints
@app.get('/api/profiles/me')
def get_my_profile():
    """Endpoint to get current user's profile"""
    return profiles_connector.get_profile_endpoint()

@app.get('/api/profiles/{user_id}')
def get_profile(user_id: str):
    """Endpoint to get a specific user's profile"""
    return profiles_connector.get_profile_endpoint(user_id)

@app.post('/api/profiles')
@app.put('/api/profiles')
async def update_profile(request: Request):
    """Endpoint to create or update current user's profile"""
    return profiles_connector.create_or_update_profile_endpoint()

@app.delete('/api/profiles')
async def delete_profile(request: Request):
    """Endpoint to delete current user's profile"""
    return profiles_connector.delete_profile_endpoint()

@app.get('/api/profiles/all')
def list_profiles():
    """Endpoint to list all profiles (admin only)"""
    return profiles_connector.list_profiles_endpoint()

# Streak endpoints
@app.get('/api/streaks')
def get_streak():
    """Endpoint to get current user's streak info"""
    return profiles_connector.get_streak_endpoint()

@app.post('/api/streaks/update')
async def update_streak(request: Request):
    """Endpoint to manually update user's streak"""
    return profiles_connector.update_streak_endpoint()

# Gamification endpoints
@app.get('/api/leaderboard')
def get_leaderboard():
    """Endpoint to get the leaderboard"""
    return profiles_connector.get_leaderboard_endpoint()

@app.post('/api/exercises/{exercise_id}/check')
async def check_exercise_answers(exercise_id: str, request: Request):
    """Endpoint to check exercise answers and award rewards"""
    return profiles_connector.check_exercise_answers_endpoint(exercise_id)

@app.get('/api/store')
def get_store_items():
    """Endpoint to get the list of items available in the store"""
    return profiles_connector.get_store_items_endpoint()

@app.post('/api/store/buy')
async def buy_item(request: Request):
    """Endpoint to buy an item from the store"""
    return profiles_connector.buy_item_endpoint()

@app.post('/api/inventory/equip')
async def equip_item(request: Request):
    """Endpoint to equip an item from the user's inventory"""
    return profiles_connector.equip_item_endpoint()

@app.post('/api/inventory/unequip')
async def unequip_item(request: Request):
    """Endpoint to unequip an item"""
    return profiles_connector.unequip_item_endpoint()

# Speech endpoints
@app.post('/api/speech/tts')
async def text_to_speech(request: Request):
    """Endpoint to convert text to speech"""
    return speech_connector.text_to_speech_endpoint()

@app.post('/api/speech/stt')
async def speech_to_text(request: Request):
    """Endpoint to convert speech to text"""
    return speech_connector.speech_to_text_endpoint()

# Home endpoint
@app.get('/')
def home():
    """Home endpoint to provide basic information about the API"""
    try:
        # Get quick stats
        lesson_count = len(lessons_manager.lessons_data)
        course_ids = set()
        for lesson in lessons_manager.lessons_data.values():
            if 'course_id' in lesson:
                course_ids.add(lesson.get('course_id'))

        return {
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
                    "/api/lessons/{lesson_id}",
                    "/api/lessons/search?q=<query>",
                    "/api/lessons/{lesson_id}/youtube",
                    "/api/lessons/{lesson_id}/conspect",
                    "/api/courses/{course_id}/test",
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
                    "/api/profiles/{user_id}",
                    "/api/profiles",
                    "/api/profiles/all"
                ],
                "streaks": [
                    "/api/streaks",
                    "/api/streaks/update"
                ],
                "gamification": [
                    "/api/leaderboard",
                    "/api/exercises/{exercise_id}/check",
                    "/api/store",
                    "/api/store/buy",
                    "/api/inventory/equip",
                    "/api/inventory/unequip"
                ],
                "speech": [
                    "/api/speech/tts",
                    "/api/speech/stt"
                ],
                "debug": [
                    "/api/debug/overview",
                    "/api/debug/lesson/{lesson_id}",
                    "/api/debug/course/{course_id}"
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error in home endpoint: {e}")
        return {
            "name": "Lessons API",
            "description": "API for managing lessons, courses, users, and profiles",
            "status": "Error getting status information",
            "error": str(e)
        }

# Run the server if this file is executed directly
if __name__ == '__main__':
    import uvicorn

    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))

    # Print some useful debug info
    logger.info(f"Lessons loaded: {len(lessons_manager.lessons_data)}")
    logger.info(f"OpenRouter API Key configured: {bool(lessons_manager.OPENROUTER_API_KEY)}")
    logger.info(f"CORS enabled for all routes")
    logger.info(f"Starting server on port {port}")

    # Run FastAPI app with uvicorn
    uvicorn.run(app, host='0.0.0.0', port=port)
