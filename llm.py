"""
llm.py
======
Pembungkus tipis (thin wrapper) untuk memanggil Anthropic API (Claude Haiku 4.5).
Kalau nanti mau ganti model, cukup ubah MODEL_NAME di sini.
"""

import os
from pathlib import Path

from anthropic import Anthropic, APIError, APIConnectionError

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500
MATERIALS_DIR = Path(__file__).parent / "materials"

_client = None


def _load_material(subject_key: str) -> str:
    """
    Baca materi buku cetak yang sudah dikurasi untuk mata pelajaran ini.
    Dicari di dua lokasi (yang manapun ditemukan duluan dipakai):
      1. materials/<subject_key>.md   -> dipakai saat bot jalan lokal di laptop.
      2. /etc/secrets/<subject_key>.md -> dipakai saat bot jalan di Render,
         diisi lewat fitur "Secret Files" di dashboard Render (bukan lewat
         GitHub), supaya materi buku tetap privat.
    Kembalikan string kosong kalau tidak ditemukan di keduanya, atau kalau
    isinya masih placeholder (bot tetap jalan normal, cuma tanpa acuan buku).
    """
    candidates = [
        MATERIALS_DIR / f"{subject_key}.md",
        Path("/etc/secrets") / f"{subject_key}.md",
    ]
    for path in candidates:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text.startswith("<!--") and text.endswith("-->"):
                continue
            return text
    return ""


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


def get_ai_reply(subject_key: str, system_prompt: str, history: list, user_message: str) -> str:
    """
    subject_key   : key mata pelajaran (dipakai untuk cari file materials/<subject_key>.md)
    system_prompt : instruksi guru untuk mata pelajaran yang sedang aktif
    history       : list pesan sebelumnya, format [{"role": "user"/"assistant", "content": "..."}]
    user_message  : pesan baru dari anak

    Return: string balasan dari Claude, atau pesan error ramah-anak kalau gagal.
    """
    client = _get_client()
    messages = history + [{"role": "user", "content": user_message}]

    # Susun system prompt sebagai list of blocks. Blok materi ditandai
    # cache_control supaya Anthropic tidak memproses ulang teks materi
    # yang sama di setiap pesan (jauh lebih hemat & lebih cepat).
    system_blocks = [{"type": "text", "text": system_prompt}]
    material_text = _load_material(subject_key)
    if material_text:
        system_blocks.append(
            {
                "type": "text",
                "text": (
                    "MATERI RUJUKAN DARI BUKU CETAK SEKOLAH (jawab berdasarkan isi ini "
                    "kalau relevan dengan pertanyaan anak):\n\n" + material_text
                ),
                "cache_control": {"type": "ephemeral"},
            }
        )

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
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
