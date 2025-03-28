"""
Speech services module for the lessons API.
Handles text-to-speech and speech-to-text functionality.
"""
import base64
import io
import os
import logging
import tempfile
from typing import Dict, Tuple

# Import gtts for text-to-speech
from gtts import gTTS

# Import transformers for speech-to-text
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Whisper model (only done once at module load time)
try:
    # Load the tiny model to minimize resource usage
    whisper_processor = WhisperProcessor.from_pretrained("openai/whisper-tiny")
    whisper_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-tiny")
    if torch.cuda.is_available():
        whisper_model = whisper_model.to("cuda")
    logger.info("Whisper tiny model loaded successfully")
    stt_available = True
except Exception as e:
    logger.error(f"Error loading Whisper model: {e}")
    stt_available = False

def text_to_speech(text: str, lang: str = 'uk') -> Tuple[Dict, int]:
    """
    Convert text to speech using Google Text-to-Speech
    
    Args:
        text (str): Text to convert to speech
        lang (str): Language code (default: 'uk' for Ukrainian)
        
    Returns:
        Tuple[Dict, int]: Response dictionary and status code
    """
    try:
        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_filename = temp_file.name
        
        # Generate the speech
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_filename)
        
        # Read the file as binary data
        with open(temp_filename, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        # Clean up the temporary file
        os.unlink(temp_filename)
        
        # Encode the audio data as base64 for easy transmission
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "success": True,
            "audio": audio_base64,
            "format": "mp3",
            "language": lang
        }, 200
    
    except Exception as e:
        logger.error(f"Error in text_to_speech: {str(e)}")
        return {
            "success": False,
            "error": f"Error generating speech: {str(e)}"
        }, 500

def speech_to_text(audio_data: bytes, lang: str = 'uk') -> Tuple[Dict, int]:
    """
    Convert speech to text using Whisper tiny model
    
    Args:
        audio_data (bytes): Audio data to transcribe
        lang (str): Language code (default: 'uk' for Ukrainian)
        
    Returns:
        Tuple[Dict, int]: Response dictionary and status code
    """
    if not stt_available:
        return {
            "success": False,
            "error": "Speech-to-text service is not available. Whisper model failed to load."
        }, 503
    
    try:
        # Save the audio data to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(audio_data)
            temp_filename = temp_file.name
        
        # Process the audio with Whisper
        import librosa
        
        # Load audio and resample to 16kHz (Whisper's expected sampling rate)
        audio_array, sampling_rate = librosa.load(temp_filename, sr=16000)
        
        # Clean up the temporary file
        os.unlink(temp_filename)
        
        # Convert to PyTorch tensor
        input_features = whisper_processor(
            audio_array,
            sampling_rate=16000,
            return_tensors="pt"
        ).input_features
        
        if torch.cuda.is_available():
            input_features = input_features.to("cuda")
        
        # Generate token ids
        predicted_ids = whisper_model.generate(
            input_features, 
            language=lang, 
            task="transcribe"
        )
        
        # Decode token ids to text
        transcription = whisper_processor.batch_decode(
            predicted_ids, 
            skip_special_tokens=True
        )[0]
        
        return {
            "success": True,
            "text": transcription,
            "language": lang
        }, 200
    
    except Exception as e:
        logger.error(f"Error in speech_to_text: {str(e)}")
        return {
            "success": False,
            "error": f"Error transcribing speech: {str(e)}"
        }, 500