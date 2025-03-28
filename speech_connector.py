"""
Connector module for speech endpoints.
Provides Flask route handlers for text-to-speech and speech-to-text.
"""
import logging
import base64
from flask import request, jsonify
import speech_services

# Configure logging
logger = logging.getLogger(__name__)

def text_to_speech_endpoint():
    """Handle the text-to-speech endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if "text" not in data:
            return jsonify({"error": "Text is required"}), 400
        
        # Get language (default to Ukrainian)
        lang = data.get("lang", "uk")
        
        # Generate speech
        result, status_code = speech_services.text_to_speech(data["text"], lang)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in text_to_speech_endpoint: {str(e)}")
        return jsonify({"error": f"Text-to-speech error: {str(e)}"}), 500

def speech_to_text_endpoint():
    """Handle the speech-to-text endpoint"""
    try:
        # Check if there's a file in the request
        if 'audio' not in request.files:
            # If no file, check if there's base64 audio in JSON
            data = request.get_json()
            if not data or "audio" not in data:
                return jsonify({"error": "No audio file or base64 audio data provided"}), 400
            
            # Decode base64 audio
            try:
                audio_data = base64.b64decode(data["audio"])
            except Exception as e:
                return jsonify({"error": f"Invalid base64 audio data: {str(e)}"}), 400
            
            # Get language (default to Ukrainian)
            lang = data.get("lang", "uk")
        else:
            # Read audio file
            audio_file = request.files['audio']
            audio_data = audio_file.read()
            
            # Get language (default to Ukrainian)
            lang = request.form.get("lang", "uk")
        
        # Transcribe speech
        result, status_code = speech_services.speech_to_text(audio_data, lang)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in speech_to_text_endpoint: {str(e)}")
        return jsonify({"error": f"Speech-to-text error: {str(e)}"}), 500