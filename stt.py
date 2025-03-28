import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import librosa
import os
import logging
import gc

# Configure logging
logger = logging.getLogger(__name__)

# Global variables for model and processor
model = None
processor = None

def initialize_whisper():
    """Initialize the Whisper tiny model using transformers"""
    global model, processor
    try:
        logger.info("Loading Whisper tiny model through Transformers...")
        
        # Load processor and model
        model_id = "openai/whisper-tiny"
        processor = WhisperProcessor.from_pretrained(model_id)
        model = WhisperForConditionalGeneration.from_pretrained(model_id)
        
        # Move to GPU if available
        if torch.cuda.is_available():
            model = model.to("cuda")
            logger.info("Model moved to GPU")
        
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error(f"Error loading Whisper model: {str(e)}")
        raise

def cleanup_resources():
    """Clean up resources to free memory"""
    global model, processor
    if model is not None:
        # Move model to CPU before deletion if it was on GPU
        if hasattr(model, 'device') and str(model.device) != 'cpu':
            model = model.to('cpu')
        # Delete model and processor
        del model
        del processor
        model = None
        processor = None
        # Force garbage collection
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def transcribe_audio(audio_path):
    """Transcribe audio file using Whisper through transformers"""
    if model is None or processor is None:
        initialize_whisper()
    
    try:
        # Load audio
        audio_array, sampling_rate = librosa.load(audio_path, sr=16000)
        
        # Process audio through the model
        input_features = processor(audio_array, sampling_rate=16000, return_tensors="pt").input_features
        
        # Move to GPU if available
        if torch.cuda.is_available():
            input_features = input_features.to("cuda")
        
        # Generate tokens
        predicted_ids = model.generate(input_features)
        
        # Decode the tokens to text
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        
        return transcription
    except Exception as e:
        logger.error(f"Error in transcription: {str(e)}")
        raise 