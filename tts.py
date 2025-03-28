from gtts import gTTS
import os
import uuid
import logging

# Configure logging
logger = logging.getLogger(__name__)

def generate_speech(text, language='en'):
    """Generate speech from text and return the file path"""
    try:
        # Validate language
        if language not in ['en', 'uk']:
            raise ValueError("Language must be 'en' (English) or 'uk' (Ukrainian)")
        
        # Generate a unique filename
        filename = f"speech_{uuid.uuid4()}.mp3"
        filepath = os.path.join('audio_files', filename)
        
        # Ensure directory exists
        os.makedirs('audio_files', exist_ok=True)
        
        # Generate the audio file
        tts = gTTS(text=text, lang=language)
        tts.save(filepath)
        
        logger.info(f"Successfully generated speech file: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise 