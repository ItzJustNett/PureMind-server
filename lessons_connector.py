"""
Connector module that bridges between Flask routes and lessons_manager.py functionality.
This module adapts the lessons_manager functions to work with Flask endpoints.
"""
import json
import logging
import os
import re
import datetime
from flask import jsonify
import lessons_manager

# Configure logging
logger = logging.getLogger(__name__)

def init_lessons_data():
    """Initialize lessons data at server startup"""
    lessons_manager.load_lessons_data()
    logger.info(f"Loaded {len(lessons_manager.lessons_data)} lessons through connector")

def search_lessons_endpoint(query):
    """Handle the search lessons endpoint"""
    if not query:
        return jsonify({"error": 'Please provide a search query parameter "q"'}), 400
    
    results = lessons_manager.search_lessons(query)
    
    return jsonify({"count": len(results), "results": results})

def get_lesson_endpoint(lesson_id):
    """Handle the get lesson endpoint"""
    lesson = lessons_manager.get_lesson(lesson_id)
    
    if not lesson:
        return jsonify({"error": "Lesson not found"}), 404
    
    return jsonify(lesson)

def get_youtube_link_endpoint(lesson_id):
    """Handle the get YouTube link endpoint"""
    result = lessons_manager.get_youtube_link(lesson_id)
    
    if not result:
        return jsonify({"error": "Lesson not found or no YouTube link available"}), 404
    
    return jsonify(result)

def list_lessons_endpoint():
    """Handle the list lessons endpoint"""
    simplified_list = lessons_manager.list_lessons()
    
    return jsonify({"count": len(simplified_list), "lessons": simplified_list})

def generate_conspect_endpoint(lesson_id):
    """Handle the generate conspect endpoint"""
    try:
        result, status = lessons_manager.generate_conspect(lesson_id)
        
        if status != 200:
            return jsonify(result), status
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in generate_conspect_endpoint: {str(e)}")
        return jsonify({
            "error": f"Error generating conspect: {str(e)}"
        }), 500

def generate_test_endpoint(course_id):
    """Handle the generate test endpoint"""
    try:
        result, status = lessons_manager.generate_test(course_id)
        
        if status != 200:
            return jsonify(result), status
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in generate_test_endpoint: {str(e)}")
        return jsonify({
            "error": f"Error generating test: {str(e)}"
        }), 500

def get_video_url_endpoint(lesson_id):
    """Handle the get video URL endpoint"""
    url = lessons_manager.get_video_url(lesson_id)
    
    if not url:
        return jsonify({"error": "Lesson not found or no YouTube link available"}), 404
    
    return jsonify({"url": url})


def generate_lesson_test_endpoint(lesson_id):
    """Handle the generate lesson test endpoint"""
    try:
        result, status = lessons_manager.generate_lesson_test(lesson_id)
        
        if status != 200:
            return jsonify(result), status
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in generate_lesson_test_endpoint: {str(e)}")
        return jsonify({
            "error": f"Error generating lesson test: {str(e)}"
        }), 500

def test_openrouter_connection_endpoint():
    """Handle the test OpenRouter connection endpoint"""
    try:
        result, status = lessons_manager.test_openrouter_connection()
        
        if result['success']:
            return jsonify({
                "status": "success",
                "message": result.get('message', 'Connection successful'),
                "model": result.get('model', 'unknown')
            })
        else:
            return jsonify({
                "status": "error",
                "error": result.get('error', 'Unknown error'),
                "details": result.get('details', '')
            }), status
        
    except Exception as e:
        logger.error(f"Error in test_openrouter_connection_endpoint: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Error testing OpenRouter connection: {str(e)}"
        }), 500