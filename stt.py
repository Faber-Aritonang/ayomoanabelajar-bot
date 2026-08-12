"""
stt.py
======
Transkripsi pesan suara (voice note) menjadi teks memakai **Groq Whisper API**.

Kenapa Groq? Gratis (2.000 request/hari, tanpa kartu kredit), akurasi terbaik
untuk Bahasa Indonesia (mesin `whisper-large-v3`), dan respons sangat cepat.

Env var yang dibutuhkan:
    GROQ_API_KEY        - API key dari https://console.groq.com (wajib)
    GROQ_STT_MODEL      - opsional, default: whisper-large-v3-turbo
    GROQ_STT_LANGUAGE   - opsional, default: id (Bahasa Indonesia)

Modul ini murni HTTP (httpx) dan bisa dipakai bot Telegram maupun WhatsApp.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
GROQ_LANGUAGE = os.getenv("GROQ_STT_LANGUAGE", "id")


def transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Ubah audio (bytes, mis. voice note OGG dari Telegram) menjadi teks.

    Return string hasil transkripsi (bisa kosong kalau tidak ada kata
    terdeteksi). Lempar exception kalau API key tidak ada atau request gagal,
    biar pemanggil bisa menangani dengan pesan yang ramah.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY tidak ditemukan. Cek file .env kamu.")

    files = {"file": (filename, audio_bytes, "audio/ogg")}
    data = {"model": GROQ_MODEL}
    if GROQ_LANGUAGE:
        data["language"] = GROQ_LANGUAGE

    resp = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files=files,
        data=data,
        timeout=60.0,
    )
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()
