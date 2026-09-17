"""
tts.py
======
Text-to-Speech untuk bot Telegram.
Menggunakan Coqui TTS (lebih natural) + gTTS sebagai fallback.

Model Bahasa Indonesia:
- Coqui: tts_models/id/tts/vits/vits-id (natural, lokal)
- Fallback: gTTS (Google TTS - GRATIS, cloud-based)

Catatan:
- Coqui TTS memberi suara lebih natural seperti manusia
- Butuh resource lebih banyak (RAM/CPU)
- gTTS fallback bila Coqui gagal atau tidak tersedia
"""

import logging
import os
import tempfile
import uuid
from io import BytesIO

logger = logging.getLogger(__name__)

# Check which TTS is available
COQUI_AVAILABLE = False
GTTTS_AVAILABLE = False

try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
    logger.info("Coqui TTS tersedia - suara akan lebih natural")
except ImportError:
    logger.warning("Coqui TTS tidak tersedia, akan pakai gTTS")

try:
    from gtts import gTTS
    GTTTS_AVAILABLE = True
except ImportError:
    logger.warning("gTTS tidak tersedia")


def text_to_speech(text: str, language: str = "id") -> bytes | None:
    """Ubah teks menjadi audio bytes yang bisa dikirim sebagai voice note.
    
    Menggunakan Coqui TTS (lebih natural) dengan fallback ke gTTS.
    
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

    # 1. Coba Coqui TTS (lebih natural)
    if COQUI_AVAILABLE:
        try:
            logger.debug("Mencoba Coqui TTS...")
            from TTS.api import TTS
            
            # Muat model Bahasa Indonesia
            tts = TTS(model_name="tts_models/id/tts/vits/vits-id", progress_bar=False)
            
            # Generate audio
            audio = tts.tts(text.strip())
            
            if audio is not None and len(audio) > 0:
                # Konversi ke bytes
                import soundfile as sf
                import tempfile
                
                # Buat file temporary untuk soundfile
                temp_path = f"/tmp/{uuid.uuid4().hex}.wav"
                sf.write(temp_path, audio, tts.synthesizer.output_sample_rate)
                
                # Baca kembali sebagai bytes
                with open(temp_path, "rb") as f:
                    result = f.read()
                
                # Cleanup
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                if result and len(result) > 0:
                    logger.info(f"Coqui TTS berhasil ({len(result)} bytes)")
                    return result
                    
        except Exception as e:
            logger.warning(f"Coqui TTS gagal: {e}")

    # 2. Fallback ke gTTS (GRATIS, cloud-based)
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
    return COQUI_AVAILABLE or GTTTS_AVAILABLE


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