"""
Improved error handling for the lessons API
This file adds better error handling for lesson and course endpoints
"""
import logging
from flask import jsonify, current_app
from functools import wraps
import json
import traceback
import lessons_manager

# Configure logging
logger = logging.getLogger(__name__)

def with_error_handling(f):
    """Decorator to add error handling to endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            return jsonify({
                "error": f"An unexpected error occurred: {str(e)}",
                "endpoint": f.__name__,
                "args": str(args),
                "kwargs": str(kwargs)
            }), 500
    
    return decorated_function

def improved_conspect_endpoint(lesson_id):
    """Improved endpoint for generating lesson summaries"""
    try:
        # Verify the lesson exists before attempting to generate conspect
        lesson = lessons_manager.lessons_data.get(lesson_id)
        
        if not lesson:
            # Check if lesson_id exists but with different case
            for key in lessons_manager.lessons_data.keys():
                if key.lower() == lesson_id.lower():
                    return jsonify({
                        "error": f"Lesson ID case mismatch. Did you mean '{key}' instead of '{lesson_id}'?",
                        "suggested_id": key
                    }), 400
            
            return jsonify({
                "error": f"Lesson with ID '{lesson_id}' not found",
                "available_ids": list(lessons_manager.lessons_data.keys())[:10]
            }), 404
        
        # Check if the lesson has a YouTube link
        if not lesson.get('youtube_link'):
            return jsonify({
                "error": f"Lesson '{lesson_id}' does not have a YouTube link",
                "lesson_data": lesson
            }), 400
        
        # Now try to generate the conspect
        result, status = lessons_manager.generate_conspect(lesson_id)
        
        # If there was an error, enhance the error message
        if status != 200:
            if isinstance(result, dict) and "error" in result:
                result["lesson_id"] = lesson_id
                result["lesson_data"] = lesson
            
            return jsonify(result), status
        
        return jsonify(result), status
    
    except Exception as e:
        logger.error(f"Error generating conspect for lesson {lesson_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": f"Error generating conspect: {str(e)}",
            "lesson_id": lesson_id
        }), 500

def improved_test_endpoint(course_id):
    """Improved endpoint for generating course tests"""
    try:
        # Check if course exists by finding any lessons for this course
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
                "available_course_ids": list(all_course_ids)[:10]
            }), 404
        
        # Now try to generate the test
        result, status = lessons_manager.generate_test(course_id)
        
        # If there was an error, enhance the error message
        if status != 200:
            if isinstance(result, dict) and "error" in result:
                result["course_id"] = course_id
                result["lesson_count"] = len(course_lessons)
            
            return jsonify(result), status
        
        return jsonify(result), status
    
    except Exception as e:
        logger.error(f"Error generating test for course {course_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": f"Error generating test: {str(e)}",
            "course_id": course_id
        }), 500

def register_improved_endpoints(app):
    """Register improved endpoints with the Flask app"""
    # Override the conspect endpoint
    @app.route('/api/lessons/<lesson_id>/conspect', methods=['GET'])
    @with_error_handling
    def better_generate_conspect(lesson_id):
        return improved_conspect_endpoint(lesson_id)
    
    # Override the test endpoint
    @app.route('/api/courses/<course_id>/test', methods=['GET'])
    @with_error_handling
    def better_generate_test(course_id):
        return improved_test_endpoint(course_id)
