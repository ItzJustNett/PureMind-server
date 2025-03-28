"""
Debug routes for the lessons API
This file adds debugging endpoints to help diagnose issues
"""
from flask import jsonify
import lessons_manager
import logging

# Configure logging
logger = logging.getLogger(__name__)

def debug_lesson_endpoint(lesson_id):
    """Debug endpoint to get detailed information about a lesson"""
    # Get the raw lesson data
    lesson = lessons_manager.lessons_data.get(lesson_id)
    
    if not lesson:
        # Check if lesson_id exists but with different case
        for key in lessons_manager.lessons_data.keys():
            if key.lower() == lesson_id.lower():
                return jsonify({
                    "message": f"Lesson exists with different case: '{key}'",
                    "suggested_id": key,
                    "lesson_data": lessons_manager.lessons_data[key]
                })
        
        # If not found at all, show available lessons
        return jsonify({
            "error": f"Lesson with ID '{lesson_id}' not found",
            "available_lesson_ids": list(lessons_manager.lessons_data.keys())[:20],  # Show first 20 to avoid huge response
            "total_lessons": len(lessons_manager.lessons_data)
        }), 404
    
    # Return detailed lesson info
    return jsonify({
        "lesson_id": lesson_id,
        "lesson_data": lesson,
        "has_youtube_link": "youtube_link" in lesson and bool(lesson.get("youtube_link")),
        "youtube_link": lesson.get("youtube_link", "Not available"),
        "course_id": lesson.get("course_id", "Not available"),
    })

def debug_course_endpoint(course_id):
    """Debug endpoint to get detailed information about a course"""
    # Find all lessons for this course
    course_lessons = [lesson for lesson in lessons_manager.lessons_data.values() 
                    if lesson.get('course_id') == course_id]
    
    # Get all unique course IDs
    all_course_ids = set()
    for lesson in lessons_manager.lessons_data.values():
        if 'course_id' in lesson:
            all_course_ids.add(lesson.get('course_id'))
    
    if not course_lessons:
        return jsonify({
            "error": f"No lessons found for course ID '{course_id}'",
            "available_course_ids": list(all_course_ids),
            "total_courses": len(all_course_ids)
        }), 404
    
    # Return detailed course info
    return jsonify({
        "course_id": course_id,
        "lesson_count": len(course_lessons),
        "lessons": [
            {
                "id": lesson.get("id"),
                "title": lesson.get("title"),
                "has_youtube_link": "youtube_link" in lesson and bool(lesson.get("youtube_link"))
            } for lesson in course_lessons
        ],
        "available_course_ids": list(all_course_ids),
    })

def debug_overview_endpoint():
    """Debug endpoint to get overview information"""
    # Count courses
    course_ids = set()
    for lesson in lessons_manager.lessons_data.values():
        if 'course_id' in lesson:
            course_ids.add(lesson.get('course_id'))
    
    # Count YouTube links
    youtube_links = 0
    for lesson in lessons_manager.lessons_data.values():
        if 'youtube_link' in lesson and lesson['youtube_link']:
            youtube_links += 1
    
    # Find a few sample lesson IDs that definitely have YouTube links
    sample_lessons_with_youtube = []
    for lesson_id, lesson in lessons_manager.lessons_data.items():
        if 'youtube_link' in lesson and lesson['youtube_link']:
            sample_lessons_with_youtube.append({
                "id": lesson_id,
                "title": lesson.get("title"),
                "youtube_link": lesson.get("youtube_link")
            })
            if len(sample_lessons_with_youtube) >= 3:
                break
    
    return jsonify({
        "total_lessons": len(lessons_manager.lessons_data),
        "total_courses": len(course_ids),
        "lessons_with_youtube_links": youtube_links,
        "sample_course_ids": list(course_ids)[:5] if course_ids else [],
        "sample_lesson_ids": list(lessons_manager.lessons_data.keys())[:5] if lessons_manager.lessons_data else [],
        "sample_lessons_with_youtube": sample_lessons_with_youtube,
        "openrouter_api_key_configured": bool(lessons_manager.OPENROUTER_API_KEY),
        "lessons_data_type": str(type(lessons_manager.lessons_data))
    })

def register_debug_routes(app):
    """Register debug routes with the Flask app"""
    @app.route('/api/debug/lesson/<lesson_id>', methods=['GET'])
    def debug_lesson(lesson_id):
        return debug_lesson_endpoint(lesson_id)
    
    @app.route('/api/debug/course/<course_id>', methods=['GET'])
    def debug_course(course_id):
        return debug_course_endpoint(course_id)
    
    @app.route('/api/debug/overview', methods=['GET'])
    def debug_overview():
        return debug_overview_endpoint()
