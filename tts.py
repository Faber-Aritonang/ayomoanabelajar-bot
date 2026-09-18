"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan Kokoro TTS (sangat natural) + gTTS sebagai fallback.

Kokoro TTS:
- Model 768M - hasil sangat natural seperti manusia
- Open source, bisa dijalankan lokal
- Bahasa Indonesia tersedia
- Lebih ringan dari Coqui

Fallback: gTTS (Google TTS - GRATIS, cloud-based)
"""

import logging
import os
import tempfile
import uuid
from io import BytesIO

logger = logging.getLogger(__name__)

# Check which TTS is available
KOKORO_AVAILABLE = False
GTTTS_AVAILABLE = False

try:
    import torch
    from kokoro import Kokoro
    KOKORO_AVAILABLE = True
    logger.info("Kokoro TTS tersedia - suara sangat natural!")
except ImportError:
    logger.warning("Kokoro TTS tidak tersedia")

try:
    from gtts import gTTS
    GTTTS_AVAILABLE = True
    logger.info("gTTS tersedia sebagai fallback")
except ImportError:
    logger.warning("gTTS tidak tersedia")


# Cache model Kokoro
_kokoro_model = None
_kokoro_voice = None

def _get_kokoro():
    """Lazy load Kokoro model untuk hemat memory."""
    global _kokoro_model, _kokoro_voice
    
    if _kokoro_model is None and KOKORO_AVAILABLE:
        try:
            # Muat model Bahasa Indonesia
            _kokoro_model = Kokoro.for_open_chars(
                model_path="gsxr/kokoro-tts-lite",
                voice_dir="voices-v1.0"
            )
            # Dapatkan voice Indonesia
            _kokoro_voice = _kokoro_model.load_voice("id")
            logger.info("Kokoro model Indonesia berhasil dimuat")
        except Exception as e:
            logger.warning(f"Gagal load model Kokoro: {e}")
            KOKORO_AVAILABLE = False
    
    return _kokoro_model, _kokoro_voice


def text_to_speech(text: str, language: str = "id") -> bytes | None:
    """Ubah teks menjadi audio bytes yang bisa dikirim sebagai voice note.
    
    Menggunakan Kokoro TTS (sangat natural) dengan fallback ke gTTS.
    
    Args:
        text: Teks yang akan diubah menjadi suara
        language: Kode bahasa (default 'id' untuk Bahasa Indonesia)
    
    Returns:
        Bytes audio MP3, atau None jika gagal
    """
    if not text or not text.strip():
        logger.warning("Teks kosong, tidak ada yang bisa diubah ke audio")
        return None

    result = None

    # 1. Coba Kokoro TTS (sangat natural)
    if KOKORO_AVAILABLE:
        try:
            logger.debug("Mencoba Kokoro TTS...")
            model, voice = _get_kokoro()
            
            if model is not None:
                # Generate audio dengan Kokoro
                audio = model.generate(text.strip(), voice)
                
                if audio is not None and len(audio) > 0:
                    # Kokoro output biasanya Numpy array, konversi ke WAV/MP3
                    if hasattr(audio, '__len__') and len(audio) > 0:
                        import numpy as np
                        audio_array = np.array(audio)
                        
                        # Simpan sebagai file WAV
                        import tempfile
                        temp_path = f"/tmp/{uuid.uuid4().hex}.wav"
                        
                        # Konversi ke WAV
                        import soundfile as sf
                        sample_rate = 22050  # Kokoro default
                        sf.write(temp_path, audio_array, sample_rate)
                        
                        # Baca sebagai bytes
                        with open(temp_path, "rb") as f:
                            result = f.read()
                        
                        # Cleanup
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                        
                        if result and len(result) > 0:
                            logger.info(f"Kokoro TTS berhasil ({len(result)} bytes)")
                            return result
                            
        except Exception as e:
            logger.warning(f"Kokoro TTS gagal: {e}")

    # 2. Fallback ke gTTS (Google TTS)
    if GTTTS_AVAILABLE:
        try:
            logger.debug("Mencoba gTTS fallback...")
            gtts = gTTS(text=text.strip(), lang=language, slow=False)
            
            buffer = BytesIO()
            gtts.write_to_fp(buffer)
            audio_bytes = buffer.getvalue()
            
            if len(audio_bytes) > 0:
                logger.info(f"gTTS fallback berhasil ({len(audio_bytes)} bytes)")
                return audio_bytes
                
        except Exception as e:
            logger.error(f"gTTS fallback gagal: {e}")

    logger.error("Semua TTS gagal - tidak ada yang tersedia")
    return None


def is_tts_available() -> bool:
    """Cek apakah ada TTS yang tersedia."""
    return KOKORO_AVAILABLE or GTTTS_AVAILABLE


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
    
    logger.debug(f"Buat file voice di {temp_path}")
    return temp_path
