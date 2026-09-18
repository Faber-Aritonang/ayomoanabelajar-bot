"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan OpenAI TTS API - gratis tier tersedia.

Fitur:
- GPT-4o-mini-tts (opsional, lebih natural)
- tts-1 (alloy, echo, onyx) - gratis tier tersedia

Instalasi:
    pip install openai

Penggunaan:
    OPENAI_API_KEY=isi_api_key_anda_di_.env
"""

import logging
import os
import tempfile
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# OpenAI client lazy import
try:
    from openai import OpenAI as _OpenAIClient
    OPENAI_AVAILABLE = True
    _client: Optional[object] = None
    logger.info("OpenAI TTS tersedia")
except ImportError:
    OPENAI_AVAILABLE = False
    _client = None
    logger.warning("OpenAI tidak tersedia. Install dengan: pip install openai")


def get_openai_client():
    """Lazy init OpenAI client."""
    global _client
    if _client is None and OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _client = _OpenAIClient(api_key=api_key)
        else:
            logger.warning("OPENAI_API_KEY tidak ditemukan di environment")
    return _client


def text_to_speech(text: str, language: str = "id", voice: str = "onyx") -> Optional[bytes]:
    """Ubah teks menjadi audio bytes yang bisa dikirim sebagai voice note.

    Args:
        text: Teks yang akan diubah menjadi suara
        voice: Suara OpenAI TTS (alloy, echo, onyx) - default onyx (lebih natural)

    Returns:
        Bytes audio MP3, atau None jika gagal
    """
    if not OPENAI_AVAILABLE:
        logger.error("OpenAI tidak tersedia")
        return None

    if not text or not text.strip():
        logger.warning("Teks kosong, tidak ada yang bisa diubah ke audio")
        return None

    try:
        openai_client = get_openai_client()
        if openai_client is None:
            logger.error("OpenAI client tidak tersedia")
            return None

        # OpenAI TTS API
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text.strip()
        )

        # Dapatkan audio bytes
        audio_bytes = response.content
        
        if len(audio_bytes) == 0:
            logger.warning("OpenAI TTS menghasilkan audio kosong")
            return None

        logger.info("Berhasil mengubah teks ke audio via OpenAI TTS (%d bytes)", len(audio_bytes))
        return audio_bytes

    except Exception as e:
        logger.error("Gagal konversi teks ke audio via OpenAI: %s", e)
        return None


def is_tts_available() -> bool:
    """Cek apakah OpenAI TTS tersedia dan bisa dipakai."""
    if not OPENAI_AVAILABLE:
        return False
    
    api_key = os.getenv("OPENAI_API_KEY")
    return api_key is not None and api_key.strip() != ""


def create_voice_file(audio_bytes: bytes, filename: str = "voice.mp3") -> str:
    """Buat file temporary untuk dikirim sebagai voice note ke Telegram.

    Args:
        audio_bytes: Bytes audio yang sudah dikonversi
        filename: Nama file (opsional)

    Returns:
        Path ke file temporary
    """
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"telegram_voice_{uuid.uuid4().hex}.mp3")
    
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    
    logger.debug("Buat file voice di %s", temp_path)
    return temp_path