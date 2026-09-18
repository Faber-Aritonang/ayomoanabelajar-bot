"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan OpenAI TTS (primary) + gTTS (fallback gratis).

Flow:
1. Coba OpenAI TTS jika OPENAI_API_KEY tersedia
2. Jika gagal/kehabisan credit, fallback ke gTTS (gratis)
"""

import logging
import os
import tempfile
import uuid
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

# ============= OpenAI TTS (Primary) =============
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    openai_client = None
    logger.info("OpenAI TTS tersedia")
except ImportError:
    OPENAI_AVAILABLE = False
    openai_client = None
    logger.info("OpenAI tidak tersedia")

def get_openai_client():
    global openai_client
    if openai_client is None and OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai_client = OpenAI(api_key=api_key)
    return openai_client if openai_client else None


# ============= gTTS (Fallback Gratis) =============
try:
    from gtts import gTTS
    GTTTS_AVAILABLE = True
    logger.info("gTTS tersedia (fallback)")
except ImportError:
    GTTTS_AVAILABLE = False
    logger.info("gTTS tidak tersedia")

def text_to_speech(text: str, language: str = "id", voice: str = "onyx") -> Optional[bytes]:
    """Ubah teks menjadi audio bytes.
    
    Priority:
    1. OpenAI TTS (voice onyx - sangat natural)
    2. gTTS (gratis, Bahasa Indonesia)
    """
    if not text or not text.strip():
        logger.warning("Teks kosong")
        return None

    # ============= Coba OpenAI TTS dulu =============
    if OPENAI_AVAILABLE:
        client = get_openai_client()
        if client:
            try:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key and api_key.strip():
                    response = client.audio.speech.create(
                        model="tts-1",
                        voice=voice,  # onyx untuk lebih natural
                        input=text.strip()
                    )
                    audio_bytes = response.content
                    logger.info(f"OpenAI TTS berhasil ({len(audio_bytes)} bytes)")
                    return audio_bytes
            except Exception as e:
                logger.warning(f"OpenAI TTS gagal: {e}")

    # ============= Fallback gTTS =============
    if GTTTS_AVAILABLE:
        try:
            # gTTS - Voice biasa tapi gratis
            tts = gTTS(text=text.strip(), lang=language, slow=False)
            buffer = BytesIO()
            tts.write_to_fp(buffer)
            audio_bytes = buffer.getvalue()
            logger.info(f"gTTS fallback berhasil ({len(audio_bytes)} bytes)")
            return audio_bytes
        except Exception as e:
            logger.error(f"gTTS gagal: {e}")

    logger.error("Tidak ada TTS yang tersedia")
    return None


def is_tts_available() -> bool:
    """Cek apakah salah satu TTS tersedia."""
    # OpenAI available
    if OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key.strip():
            return True
    
    # gTTS always available (free)
    if GTTTS_AVAILABLE:
        return True
    
    return False


def create_voice_file(audio_bytes: bytes, filename: str = "voice.mp3") -> str:
    """Buat file temporary untuk dikirim sebagai voice note."""
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"telegram_voice_{uuid.uuid4().hex}.mp3")
    
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    
    logger.debug("Buat file voice di %s", temp_path)
    return temp_path