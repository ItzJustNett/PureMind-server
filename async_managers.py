"""
Async wrapper for manager modules to support FastAPI
Uses httpx for async HTTP calls instead of blocking requests
"""
import httpx
import json
import os
import logging
import lessons_manager
import auth
import profiles
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

# ==============================================================================
# ASYNC LESSONS MANAGER
# ==============================================================================

async def search_lessons_async(query: str):
    """Async wrapper for search_lessons"""
    # This is I/O-free, can run directly
    return lessons_manager.search_lessons(query)

async def get_lesson_async(lesson_id: str):
    """Async wrapper for get_lesson"""
    return lessons_manager.get_lesson(lesson_id)

async def get_youtube_link_async(lesson_id: str):
    """Async wrapper for get_youtube_link"""
    return lessons_manager.get_youtube_link(lesson_id)

async def get_video_url_async(lesson_id: str):
    """Async wrapper for get_video_url"""
    return lessons_manager.get_video_url(lesson_id)

async def list_lessons_async():
    """Async wrapper for list_lessons"""
    return lessons_manager.list_lessons()

async def generate_lesson_test_async(lesson_id: str):
    """Generate test using async httpx instead of blocking requests"""
    try:
        # Use blocking get_lesson to retrieve from database
        lesson = lessons_manager.get_lesson(lesson_id)

        if not lesson:
            return {"error": "Lesson not found"}, 404

        if not lessons_manager.OPENROUTER_API_KEY:
            return {"error": "OpenRouter API key not configured"}, 500

        title = lesson.get('title', '')
        youtube_link = lesson.get('youtube_link', '')
        course_id = lesson.get('course_id', '')

        if not youtube_link:
            return {"error": "No YouTube link available"}, 404

        prompt = f"""You must return ONLY valid JSON with no other text.

Create a test with 10 questions about the lesson titled "{title}".
Write the test in Ukrainian language.

Return ONLY this exact JSON format (no markdown, no extra text):
{{"lesson_id": "{lesson_id}", "title": "{title}", "questions": [{{"question": "Q1 in Ukrainian?", "options": ["Option A", "Option B", "Option C", "Option D"], "correct_answer": 0}}]}}

Each question should have:
- "question": question text in Ukrainian
- "options": array of exactly 4 string options
- "correct_answer": index (0-3) of the correct option

Return ONLY the JSON, starting with {{ and ending with }}"""

        logger.info(f"Sending async request to OpenRouter for test: {title}")

        # Use httpx for async HTTP
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                lessons_manager.OPENROUTER_API_URL,
                headers=lessons_manager.OPENROUTER_HEADERS,
                json={
                    "model": lessons_manager.OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a helpful educational assistant that creates tests in Ukrainian."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )

        if response.status_code != 200:
            logger.error(f"OpenRouter API error: {response.text}")
            return {"error": f"OpenRouter API error: {response.status_code}"}, 500

        result = response.json()
        test_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not test_content:
            return {"error": "Failed to generate test"}, 500

        # Extract JSON from markdown code blocks if needed
        json_match_start = test_content.find('{')
        json_match_end = test_content.rfind('}')

        if json_match_start != -1 and json_match_end != -1:
            json_str = test_content[json_match_start:json_match_end+1]

            # Clean up control characters
            import re
            # Remove actual control characters (but keep escaped ones)
            json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)

            try:
                test_json = json.loads(json_str)
                return test_json, 200
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                logger.error(f"JSON content (first 500 chars): {json_str[:500]}")
                return {"error": f"Could not parse test JSON", "details": str(e), "sample": json_str[:200]}, 500

        return {"error": "Could not parse test JSON - no JSON structure found"}, 500

    except Exception as e:
        logger.error(f"Error generating test: {str(e)}")
        return {"error": f"Error: {str(e)}"}, 500

async def generate_conspect_async(lesson_id: str):
    """Generate conspect (summary) using async httpx"""
    try:
        # Use blocking get_lesson to retrieve from database
        lesson = lessons_manager.get_lesson(lesson_id)

        if not lesson:
            return {"error": "Lesson not found"}, 404

        if not lessons_manager.OPENROUTER_API_KEY:
            return {"error": "OpenRouter API key not configured"}, 500

        title = lesson.get('title', '')
        youtube_link = lesson.get('youtube_link', '')

        if not youtube_link:
            return {"error": "No YouTube link available"}, 404

        prompt = f"""
        Create a detailed summary (conspect) for the lesson titled "{title}".
        YouTube link: {youtube_link}

        The summary should:
        1. Be in Ukrainian language
        2. Cover main topics
        3. Be suitable for students
        4. Be 3-5 paragraphs long

        Return in JSON format:
        {{
          "lesson_id": "{lesson_id}",
          "title": "{title}",
          "summary": "Your detailed summary here",
          "key_points": ["point1", "point2", ...]
        }}
        """

        logger.info(f"Generating conspect for: {title}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                lessons_manager.OPENROUTER_API_URL,
                headers=lessons_manager.OPENROUTER_HEADERS,
                json={
                    "model": lessons_manager.OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are an educational content expert writing in Ukrainian."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )

        if response.status_code != 200:
            return {"error": f"OpenRouter API error: {response.status_code}"}, 500

        result = response.json()
        conspect_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not conspect_content:
            return {"error": "Failed to generate conspect"}, 500

        # Extract JSON
        json_match_start = conspect_content.find('{')
        json_match_end = conspect_content.rfind('}')

        if json_match_start != -1 and json_match_end != -1:
            json_str = conspect_content[json_match_start:json_match_end+1]
            conspect_json = json.loads(json_str)
            return conspect_json, 200

        return {"error": "Could not parse conspect JSON"}, 500

    except Exception as e:
        logger.error(f"Error generating conspect: {str(e)}")
        return {"error": f"Error: {str(e)}"}, 500

async def test_openrouter_connection_async():
    """Test OpenRouter connection asynchronously"""
    try:
        if not lessons_manager.OPENROUTER_API_KEY:
            return {"error": "OPENROUTER_API_KEY not configured"}, 500

        logger.info("Testing OpenRouter connection...")

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                lessons_manager.OPENROUTER_API_URL,
                headers=lessons_manager.OPENROUTER_HEADERS,
                json={
                    "model": lessons_manager.OPENROUTER_MODEL,
                    "messages": [
                        {"role": "user", "content": "Say 'OK' in one word."}
                    ]
                }
            )

        if response.status_code == 200:
            return {"success": True, "message": "OpenRouter API is working"}, 200
        else:
            return {"error": f"OpenRouter returned status {response.status_code}"}, response.status_code

    except Exception as e:
        logger.error(f"Error testing OpenRouter: {str(e)}")
        return {"error": f"Failed to connect: {str(e)}"}, 500

# ==============================================================================
# ASYNC AUTH MANAGER WITH TOKEN TTL
# ==============================================================================

class AsyncTokenManager:
    """Token manager with TTL (time-to-live) and automatic cleanup"""

    def __init__(self, ttl_hours: int = 24):
        self.tokens = {}
        self.ttl = timedelta(hours=ttl_hours)
        self.cleanup_task = None

    async def create_token(self, user_id: str) -> str:
        """Create and store a token with TTL"""
        import secrets
        token = secrets.token_hex(32)
        self.tokens[token] = {
            'user_id': user_id,
            'created_at': datetime.utcnow()
        }
        return token

    def validate_token(self, token: str) -> dict:
        """Validate token and check expiration"""
        if token not in self.tokens:
            return None

        token_data = self.tokens[token]
        if datetime.utcnow() - token_data['created_at'] > self.ttl:
            del self.tokens[token]
            return None

        return {'user_id': token_data['user_id']}

    def invalidate_token(self, token: str) -> bool:
        """Invalidate a token"""
        if token in self.tokens:
            del self.tokens[token]
            return True
        return False

    async def cleanup_expired(self):
        """Periodically clean up expired tokens from database"""
        from database import SessionLocal
        from db_managers import auth_manager

        while True:
            await asyncio.sleep(3600)  # Run every hour
            try:
                db = SessionLocal()
                try:
                    deleted_count = auth_manager.cleanup_expired_tokens(db)
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} expired tokens from database")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error cleaning up expired tokens: {e}")

# Global token manager instance
token_manager = AsyncTokenManager(ttl_hours=24)

async def register_user_async(username: str, password: str):
    """Async wrapper for user registration"""
    return auth.register_user(username, password)

async def login_user_async(username: str, password: str):
    """Async login using database auth"""
    try:
        # Use the refactored login_user function which handles database
        result, status = auth.login_user(username, password)
        return result, status

    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        return {"error": f"Login error: {str(e)}"}, 500


async def login_user_by_id_async(user_id: str):
    """Async login by user ID (for OAuth)"""
    try:
        result, status = auth.login_by_user_id(int(user_id))
        return result, status

    except Exception as e:
        logger.error(f"Error in login by ID: {str(e)}")
        return {"error": f"Login error: {str(e)}"}, 500

async def logout_user_async(token: str):
    """Async logout using database"""
    try:
        # Use the refactored logout_user function which handles database
        return auth.logout_user(token)
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        return {"error": f"Logout error: {str(e)}"}, 500

async def validate_token_async(token: str):
    """Async token validation"""
    return token_manager.validate_token(token)

async def get_user_by_id_async(user_id: str):
    """Async wrapper for get_user_by_id"""
    return auth.get_user_by_id(user_id)

# ==============================================================================
# ASYNC PROFILES MANAGER
# ==============================================================================

async def create_or_update_profile_async(user_id: str, profile_data: dict):
    """Async wrapper for profile operations"""
    return profiles.create_or_update_profile(user_id, profile_data)

async def get_profile_async(user_id: str):
    """Async wrapper for get_profile"""
    return profiles.get_profile(user_id)

async def delete_profile_async(user_id: str):
    """Async wrapper for delete_profile"""
    return profiles.delete_profile(user_id)

async def list_profiles_async():
    """Async wrapper for list_profiles"""
    return profiles.list_profiles()

async def get_streak_async(user_id: str):
    """Async wrapper for get_streak"""
    return profiles.get_streak(user_id)

async def update_streak_async(user_id: str):
    """Async wrapper for update_streak"""
    return profiles.update_streak(user_id)

async def get_leaderboard_async(sort_by: str = "xp"):
    """Async wrapper for get_leaderboard"""
    return profiles.get_leaderboard(sort_by)

async def check_exercise_answers_async(user_id: str, exercise_id: str, correct_answers: int):
    """Async wrapper for exercise checking"""
    return profiles.check_exercise_answers(user_id, exercise_id, correct_answers)

async def get_store_items_async():
    """Async wrapper for get_store_items"""
    return profiles.get_store_items()

async def buy_item_async(user_id: str, item_id: str):
    """Async wrapper for buy_item"""
    return profiles.buy_item(user_id, item_id)

async def equip_item_async(user_id: str, item_id: str):
    """Async wrapper for equip_item"""
    return profiles.equip_item(user_id, item_id)

async def unequip_item_async(user_id: str, item_id: str):
    """Async wrapper for unequip_item"""
    return profiles.unequip_item(user_id, item_id)
