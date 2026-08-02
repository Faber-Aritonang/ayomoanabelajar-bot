"""
llm.py
======
Pembungkus tipis (thin wrapper) untuk memanggil Anthropic API (Claude Haiku 4.5).
Kalau nanti mau ganti model, cukup ubah MODEL_NAME di sini.
"""

import os
from anthropic import Anthropic, APIError, APIConnectionError

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY tidak ditemukan. Cek file .env kamu."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def get_ai_reply(system_prompt: str, history: list, user_message: str) -> str:
    """
    system_prompt : instruksi guru untuk mata pelajaran yang sedang aktif
    history       : list pesan sebelumnya, format [{"role": "user"/"assistant", "content": "..."}]
    user_message  : pesan baru dari anak

    Return: string balasan dari Claude, atau pesan error ramah-anak kalau gagal.
    """
    client = _get_client()
    messages = history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        # response.content adalah list block; ambil semua block teks
        text_parts = [block.text for block in response.content if block.type == "text"]
        reply = "\n".join(text_parts).strip()
        return reply or "Hmm, Kak Moana belum bisa jawab itu. Coba tanya dengan cara lain, ya! 😊"

    except APIConnectionError:
        return "Wah, koneksi Kak Moana lagi bermasalah. Coba kirim lagi sebentar lagi ya! 🌐"
    except APIError as e:
        return f"Maaf ya, Kak Moana lagi ada gangguan kecil ({e.status_code}). Coba lagi sebentar ya! 🙏"
    except Exception:
        return "Ups, ada yang tidak beres di sistem Kak Moana. Coba kirim pesannya lagi ya! 🙏"
