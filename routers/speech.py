"""
Speech API routes (FastAPI version with lazy loading optimization)
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional
import logging
import speech_services_optimized as speech_services
import base64

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/speech", tags=["speech"])

# Request models
class TTSRequest(BaseModel):
    text: str
    lang: Optional[str] = "uk"

class STTRequest(BaseModel):
    audio: str  # base64 encoded audio
    lang: Optional[str] = "uk"

@router.post("/tts")
async def text_to_speech(data: TTSRequest):
    """Convert text to speech"""
    try:
        result, status = speech_services.text_to_speech(data.text, data.lang)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "TTS failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")

@router.post("/stt")
async def speech_to_text(
    audio: Optional[str] = Form(None),
    lang: Optional[str] = Form("uk"),
    file: Optional[UploadFile] = File(None)
):
    """Convert speech to text

    Supports two input methods:
    1. Form data with audio file: multipart/form-data with 'file' field
    2. JSON with base64: {'audio': 'base64_string', 'lang': 'uk'}
    """
    try:
        audio_data = None

        if file:
            # File upload
            audio_data = await file.read()
        elif audio:
            # Base64 encoded audio
            audio_data = base64.b64decode(audio)
        else:
            raise HTTPException(status_code=400, detail="No audio provided. Use 'file' or 'audio' field.")

        result, status = speech_services.speech_to_text(audio_data, lang)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "STT failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in STT: {str(e)}")
        raise HTTPException(status_code=500, detail=f"STT error: {str(e)}")
