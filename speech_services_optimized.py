"""
Optimized Speech Services with Lazy Loading
Whisper model is only loaded on first STT request, not at startup
"""
import io
import base64
import logging
import asyncio
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Lazy loading - these are None until first use
_whisper_model = None
_whisper_processor = None

async def get_whisper_model():
    """Get or initialize Whisper model (lazy loading)"""
    global _whisper_model, _whisper_processor

    if _whisper_model is None:
        logger.info("Loading Whisper model (first request)...")
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch

            # Use CPU for compatibility with low-RAM servers
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")

            # Load with 8-bit quantization to save memory (100MB instead of 400MB)
            _whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
                "openai/whisper-tiny",
                device_map="cpu",
                load_in_8bit=True,  # Key optimization: 8-bit quantization
                low_cpu_mem_usage=True  # Reduce peak memory during loading
            ).to(device)

            _whisper_processor = AutoProcessor.from_pretrained("openai/whisper-tiny")

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise

    return _whisper_model, _whisper_processor

async def text_to_speech(text: str, lang: str = "uk") -> Tuple[dict, int]:
    """Convert text to speech using gTTS"""
    try:
        if not text:
            return {"error": "Text is empty"}, 400

        from gtts import gTTS
        import os
        import tempfile

        logger.info(f"Converting text to speech ({lang}): {text[:50]}...")

        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Generate speech
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(tmp_path)

            # Read and encode as base64
            with open(tmp_path, "rb") as f:
                audio_data = f.read()

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            return {
                "success": True,
                "audio": audio_base64,
                "format": "mp3",
                "language": lang
            }, 200

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        logger.error(f"Error in text_to_speech: {e}")
        return {"error": f"TTS error: {str(e)}"}, 500

async def speech_to_text(audio_data: bytes, lang: str = "uk") -> Tuple[dict, int]:
    """Convert speech to text using Whisper (lazy loaded)"""
    try:
        if not audio_data:
            return {"error": "No audio data provided"}, 400

        logger.info(f"Converting speech to text ({lang})...")

        # Load model (lazy - only on first call)
        model, processor = await get_whisper_model()

        import librosa
        import numpy as np
        import torch

        # Decode audio
        audio_stream = io.BytesIO(audio_data)
        audio, sr = librosa.load(audio_stream, sr=16000)

        logger.info(f"Audio loaded: {len(audio)} samples at {sr}Hz")

        # Process with Whisper
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt")

        # Run inference
        with torch.no_grad():
            predicted_ids = model.generate(inputs["input_features"])

        # Decode
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)

        if transcription:
            text = transcription[0].strip()
            logger.info(f"Transcribed: {text[:100]}...")

            return {
                "success": True,
                "text": text,
                "language": lang
            }, 200
        else:
            return {"error": "No speech detected"}, 400

    except Exception as e:
        logger.error(f"Error in speech_to_text: {e}")
        return {"error": f"STT error: {str(e)}"}, 500

async def unload_whisper_model():
    """Free up memory by unloading the Whisper model"""
    global _whisper_model, _whisper_processor

    if _whisper_model is not None:
        import torch
        del _whisper_model
        del _whisper_processor
        _whisper_model = None
        _whisper_processor = None
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        logger.info("Whisper model unloaded")
