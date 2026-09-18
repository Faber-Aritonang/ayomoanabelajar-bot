"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan OpenAI TTS (primary) + Coqui TTS Ekho (fallback natural).

Model Coqui Ekho:
- Voice natural seperti manusia
- Cocok untuk anak
- Bahasa Indonesia tersedia

Flow:
1. Coba OpenAI TTS jika OPENAI_API_KEY tersedia
2. Jika gagal/kehabisan credit, fallback ke Coqui TTS Ekho
"""

import logging
import os
import tempfile
import uuid
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


# ============= Coqui TTS Ekho (Fallback Natural) =============
try:
    from TTS.api import TTS as CoquiTTS
    COQUI_AVAILABLE = True
    coqui_model = None
    logger.info("Coqui TTS tersedia")
except ImportError:
    COQUI_AVAILABLE = False
    coqui_model = None
    logger.info("Coqui TTS tidak tersedia")

def get_coqui_model():
    """Lazy init Coqui TTS model Ekho untuk Bahasa Indonesia - voice natural."""
    global coqui_model
    if coqui_model is None and COQUI_AVAILABLE:
        try:
            # Model Ekho - voice natural untuk Bahasa Indonesia
            # Lebih natural daripada gTTS, cocok untuk anak
            coqui_model = CoquiTTS(
                model_name="tts_models/id/ekho/tts_vits",
                progress_bar=False,
                gpu=False  # Render free tier tidak pakai GPU
            )
            logger.info("Coqui TTS Ekho model loaded (voice natural)")
        except Exception as e:
            logger.warning(f"Gagal load model Coqui Ekho: {e}")
    return coqui_model

def get_coqui_voice_settings():
    """Voice settings untuk hasil natural, tidak terlalu robot."""
    return {
        "speed": 1.0,           # Speed normal (jangan > 1.3)
        "length_scale": 1.0,    # Normal speaking rate
        "noise_scale": 0.33,    # Natural noise level
        "pitch_scale": 1.0,     # Normal pitch
        "volume_scale": 1.0,    # Normal volume
    }


def text_to_speech(text: str, language: str = "id", voice: str = "onyx") -> Optional[bytes]:
    """Ubah teks menjadi audio bytes dengan voice natural.
    
    Priority:
    1. OpenAI TTS (voice onyx - sangat natural)
    2. Coqui TTS Ekho (voice natural lokal)
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

    # ============= Fallback Coqui TTS Ekho =============
    if COQUI_AVAILABLE:
        try:
            model = get_coqui_model()
            if model:
                voice_settings = get_coqui_voice_settings()
                temp_path = f"/tmp/tts_coqui_{uuid.uuid4().hex}.wav"
                
                # Generate dengan settings natural
                model.tts_to_file(
                    text=text.strip(),
                    file_path=temp_path,
                    language=language,
                    speed=voice_settings["speed"],
                    length_scale=voice_settings["length_scale"],
                    noise_scale=voice_settings["noise_scale"],
                    pitch_scale=voice_settings["pitch_scale"]
                )
                
                with open(temp_path, "rb") as f:
                    audio_bytes = f.read()
                
                os.remove(temp_path)
                logger.info(f"Coqui TTS Ekho berhasil ({len(audio_bytes)} bytes) - voice natural")
                return audio_bytes
        except Exception as e:
            logger.error(f"Coqui TTS gagal: {e}")

    logger.error("Tidak ada TTS yang tersedia")
    return None


def is_tts_available() -> bool:
    """Cek apakah salah satu TTS tersedia."""
    # OpenAI available
    if OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key.strip():
            return True
    
    # Coqui available (always works offline, natural voice)
    if COQUI_AVAILABLE:
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