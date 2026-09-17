"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan gTTS (Google Text-to-Speech) - GRATIS, tidak butuh API key.

Catatan:
- Untuk bahasa Indonesia, gunakan language='id'
- gTTS menghasilkan MP3 yang Telegram menerima sebagai voice note
- Tidak butuh konversi format ekstra - Telegram otomatis proses

Instalasi (hanya sekali):
    pip install gtts

Catatan: gTTS membutuhkan koneksi internet untuk mengakses API Google.
Untuk penggunaan offline, pertimbangkan pyttsx3 atau Coqui TTS.
"""

import logging
import os
import tempfile
from io import BytesIO

logger = logging.getLogger(__name__)

# Lazy import gTTS untuk menghindari error jika tidak dipakai
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    logger.info("gTTS berhasil di-load, ready untuk Text-to-Speech")
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS tidak tersedia. Install dengan: pip install gtts")


def text_to_speech(text: str, language: str = "id") -> bytes | None:
    """Ubah teks menjadi audio bytes yang bisa dikirim sebagai voice note.

    Args:
        text: Teks yang akan diubah menjadi suara
        language: Kode bahasa (default 'id' untuk Bahasa Indonesia)

    Returns:
        Bytes audio MP3, atau None jika gagal
    """
    if not GTTS_AVAILABLE:
        logger.error("gTTS tidak tersedia")
        return None

    if not text or not text.strip():
        logger.warning("Teks kosong, tidak ada yang bisa diubah ke audio")
        return None

    try:
        # gTTS menghasilkan MP3
        # Telegram mendukung MP3 sebagai voice note
        tts = gTTS(text=text.strip(), lang=language, slow=False)

        # Simpan ke buffer
        buffer = BytesIO()
        tts.write_to_fp(buffer)
        audio_bytes = buffer.getvalue()

        if len(audio_bytes) == 0:
            logger.warning("gTTS menghasilkan audio kosong")
            return None

        logger.info("Berhasil mengubah teks ke audio (%d bytes)", len(audio_bytes))
        return audio_bytes

    except Exception as e:
            logger.error("Gagal konversi teks ke audio: %s", e)
            return None


def is_tts_available() -> bool:
    """Cek apakah gTTS tersedia dan bisa dipakai."""
    return GTTS_AVAILABLE


def create_voice_file(audio_bytes: bytes, filename: str = "voice.mp3") -> str:
    """Buat file temporary untuk dikirim sebagai voice note ke Telegram.

    Args:
        audio_bytes: Bytes audio yang sudah dikonversi
        filename: Nama file (opsional)

    Returns:
        Path ke file temporary
    """
    import tempfile
    import uuid
    
    # Buat file temporary dengan nama unik
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"telegram_voice_{uuid.uuid4().hex}.mp3")
    
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    
    logger.debug("Buat file voice di %s", temp_path)
    return temp_path