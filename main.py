"""
FastAPI version of the Lessons API
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

import lessons_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import asyncio
    import async_managers

    logger.info("Starting up Lessons API (FastAPI)")
    lessons_manager.load_lessons_data()
    logger.info(f"Lessons data initialized with {len(lessons_manager.lessons_data)} lessons")
    logger.info(f"OpenRouter API Key configured: {bool(lessons_manager.OPENROUTER_API_KEY)}")

    # Start token cleanup task
    cleanup_task = asyncio.create_task(async_managers.token_manager.cleanup_expired())
    logger.info("Token cleanup task started (runs every hour)")

    yield

    # Shutdown
    cleanup_task.cancel()
    logger.info("Shutting down Lessons API")

# Create FastAPI app
app = FastAPI(
    title="Lessons API",
    description="API for managing lessons, courses, users, and profiles",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS (must be first middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://puremind.xoperr.dev",
        "https://puremindd.netlify.app",  # Netlify deployment
        "http://localhost:3000",      # для локальної розробки
        "http://localhost:5173",      # для Vite
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "*"],
    max_age=3600,
)

# Import routers
from routers import lessons, auth, profiles, speech, debug

# Exception handler for HTTPException to ensure CORS headers are included
from fastapi import HTTPException
from starlette.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"Access-Control-Allow-Origin": "*"}
    )

# Include routers
app.include_router(lessons.router)
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(speech.router)
app.include_router(debug.router)

# Root endpoint
@app.get("/")
async def home():
    """Home endpoint to provide basic information about the API"""
    try:
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
                    "/api/lessons/{lesson_id}/test",
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

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Lessons API"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
