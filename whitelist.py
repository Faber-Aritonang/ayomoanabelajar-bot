"""
whitelist.py
============
Pembatasan akses bot (whitelist) bersama untuk Telegram & WhatsApp.

Cara kerja:
1. Kalau `BOT_WHITELIST_ENABLED` != "1", semua orang boleh pakai bot
   (perilaku default, tidak ada perubahan).
2. Kalau aktif, hanya pengguna yang terdaftar yang dilayani:
   - daftar tetap dari env var (`WA_WHITELIST` / `TG_WHITELIST`, koma),
   - ditambah daftar dinamis di database (tabel `whitelist`) yang bisa
     diubah lewat perintah admin tanpa restart.
3. Admin (`BOT_ADMIN_WHATSAPP` / `BOT_ADMIN_TELEGRAM`) selalu dilayani dan
   menjadi satu-satunya yang bisa menambah/menghapus nomor lewat bot.
"""

import os
import re

import database

# Aktifkan whitelist dengan env BOT_WHITELIST_ENABLED=1.
ENABLED = os.getenv("BOT_WHITELIST_ENABLED", "0").strip() == "1"

# Nomor/user_id admin — selalu boleh dan bisa mengelola daftar.
ADMIN_WHATSAPP = os.getenv("BOT_ADMIN_WHATSAPP", "").strip()
ADMIN_TELEGRAM = os.getenv("BOT_ADMIN_TELEGRAM", "").strip()

# Daftar tetap dari env var (basis awal sebelum pakai perintah bot).
_BASE_WHATSAPP: set[str] = set()
_BASE_TELEGRAM: set[str] = set()


def _split_csv(raw: str) -> set[str]:
    return {x.strip() for x in (raw or "").split(",") if x.strip()}


def _normalize_phone(raw: str) -> str:
    """Bersihkan format nomor: hilangkan +, spasi, tanda hubung, 0 di depan.

    "0812-3456-789" / "+628123456789" / "628123456789" -> "628123456789"
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


def _load_env_whitelists():
    global _BASE_WHATSAPP, _BASE_TELEGRAM
    _BASE_WHATSAPP = {_normalize_phone(x) for x in _split_csv(os.getenv("WA_WHITELIST", ""))}
    _BASE_TELEGRAM = _split_csv(os.getenv("TG_WHITELIST", ""))


# Muat daftar env saat import.
_load_env_whitelists()


def normalize_phone(raw: str) -> str:
    """Versi publik _normalize_phone, dipakai bot untuk perintah admin."""
    return _normalize_phone(raw)


def enabled() -> bool:
    return ENABLED


def is_admin(identifier: str, platform: str) -> bool:
    """Apakah identifier ini admin (berhak mengelola whitelist)?"""
    if platform == "whatsapp":
        return bool(ADMIN_WHATSAPP) and normalize_phone(identifier) == normalize_phone(ADMIN_WHATSAPP)
    return bool(ADMIN_TELEGRAM) and identifier == ADMIN_TELEGRAM


def is_allowed(identifier: str, platform: str) -> bool:
    """Apakah pengguna boleh memakai bot?

    Whitelist nonaktif -> semua boleh. Aktif -> admin, daftar env, atau
    daftar database.
    """
    if not ENABLED:
        return True
    if is_admin(identifier, platform):
        return True
    if platform == "whatsapp":
        return normalize_phone(identifier) in _BASE_WHATSAPP or database.whitelist_contains(
            normalize_phone(identifier), "whatsapp"
        )
    return identifier in _BASE_TELEGRAM or database.whitelist_contains(identifier, "telegram")


def base_list(platform: str) -> list[str]:
    """Daftar tetap dari env var (untuk ditampilkan admin)."""
    if platform == "whatsapp":
        return sorted(_BASE_WHATSAPP)
    return sorted(_BASE_TELEGRAM)


# Pesan ramah untuk pengguna yang tidak terdaftar.
REJECT_TEXT = (
    "Halo! 👋 Bot ini khusus untuk siswa yang sudah terdaftar ya. 😊\n"
    "Kalau kamu ingin bergabung, minta ayah/ibu atau gurumu menghubungi admin "
    "untuk mendaftarkan nomor ini. Terima kasih!"
)
