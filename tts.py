"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan OpenAI TTS (primary) + Piper TTS (fallback).

Model Piper:
- Ringan & cepat
- Bahasa Indonesia tersedia
- Python 3.14 compatible

Flow:
1. Coba OpenAI TTS jika OPENAI_API_KEY tersedia
2. Jika gagal/kehabisan credit, fallback ke Piper TTS
"""

import logging
import os
import subprocess
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


# ============= Piper TTS (Fallback Natural) =============
try:
    from piper import Piper
    PIPER_AVAILABLE = True
    piper_instance = None
    logger.info("Piper TTS tersedia")
except ImportError:
    PIPER_AVAILABLE = False
    piper_instance = None
    logger.info("Piper TTS tidak tersedia")

def get_piper_instance():
    """Lazy init Piper TTS untuk Bahasa Indonesia."""
    global piper_instance
    if piper_instance is None and PIPER_AVAILABLE:
        try:
            # Model Bahasa Indonesia natural
            # Piper otomatis download model kalau belum ada
            piper_instance = Piper(
                model="thdq_hisr_id-id.onnx",  # Model Bahasa Indonesia
                use_cuda=False
            )
            logger.info("Piper TTS model loaded (voice natural Indonesia)")
        except Exception as e:
            logger.warning(f"Gagal load model Piper: {e}")
    return piper_instance

PIPER_BINARY = "/opt/render/.piper/bin/piper"

def text_to_speech(text: str, language: str = "id", voice: str = "onyx") -> Optional[bytes]:
    """Ubah teks menjadi audio bytes dengan voice natural.
    
    Priority:
    1. OpenAI TTS (voice onyx - sangat natural)
    2. Piper TTS (voice natural Bahasa Indonesia)
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

    # ============= Fallback Piper TTS =============
    if PIPER_AVAILABLE:
        try:
            model_path = get_piper_model_path()
            if os.path.exists(model_path):
                temp_wav = f"/tmp/piper_{uuid.uuid4().hex}.wav"
                
                # Run piper binary
                cmd = [
                    PIPER_BINARY,
                    f"--model {model_path}",
                    f"--output_file {temp_wav}",
                    f"--text '{text.strip()}'"
                ]
                
                result = subprocess.run(" ".join(cmd), shell=True, capture_output=True)
                
                if result.returncode == 0 and os.path.exists(temp_wav):
                    with open(temp_wav, "rb") as f:
                        audio_bytes = f.read()
                    os.remove(temp_wav)
                    logger.info(f"Piper TTS berhasil ({len(audio_bytes)} bytes) - voice natural Indonesia")
                    return audio_bytes
                else:
                    logger.error(f"Piper error: {result.stderr.decode() if result.stderr else 'unknown'}")
        except Exception as e:
            logger.error(f"Piper TTS gagal: {e}")

    logger.error("Tidak ada TTS yang tersedia")
    return None


def get_piper_model_path():
    """Cari path model Piper - coba beberapa lokasi."""
    paths = [
        "/opt/render/.piper_models/thdq_hisr_id-id.onnx",
        "/opt/render/piper-models/thdq_hisr_id-id.onnx",
        "./models/thdq_hisr_id-id.onnx",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0]  # Default path (akan download oleh Piper bila diperlukan)


def is_tts_available() -> bool:
    """Cek apakah salah satu TTS tersedia."""
    # OpenAI available
    if OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key.strip():
            return True
    
    # Piper available (always works offline, natural voice)
    if PIPER_AVAILABLE:
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