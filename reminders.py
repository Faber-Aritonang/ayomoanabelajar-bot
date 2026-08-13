"""
reminders.py
============
Logika **Pengingat Belajar Harian** bersama untuk bot Telegram & WhatsApp.

Cara kerja:
1. Setiap interval tertentu (diatur di masing-masing bot), dipanggil
   ``reminder_job_once`` untuk mencari anak yang memenuhi syarat.
2. Syarat penerima pengingat: pernah aktif dalam N hari terakhir
   (``get_active_user_ids``), tapi **belum belajar hari ini**.
3. Pesan dikirim paling banyak 1x per hari per anak — bot mencatat nomor
   yang sudah diingatkan hari ini lewat parameter ``sent_today`` (set).

Env vars (opsional):
    REMINDER_ENABLED      - "0" untuk mematikan pengingat, default aktif.
    REMINDER_HOUR         - jam pengingat dikirim (0-23, zona waktu server),
                             default 16 (WIB sore hari setelah pulang sekolah).
    REMINDER_ACTIVE_DAYS  - seberapa jauh ke belakang dianggap "aktif",
                             default 7 hari.
"""

import os
import re
from datetime import datetime

import database

REMINDER_ENABLED = os.getenv("REMINDER_ENABLED", "1").strip() != "0"
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "16"))
# Batas atas jendela pengiriman: reminder dikirim pada jam [REMINDER_HOUR,
# REMINDER_MAX_HOUR) — sekali per hari per anak. Ini membuat pengingat tetap
# terkirim walau bot baru hidup beberapa jam setelah REMINDER_HOUR (mis. baru
# jalan 18:00 saat target 16:00), tanpa berisiko mengirim tengah malam.
REMINDER_MAX_HOUR = int(os.getenv("REMINDER_MAX_HOUR", "21"))
REMINDER_ACTIVE_DAYS = int(os.getenv("REMINDER_ACTIVE_DAYS", "7"))

# Pola nomor WhatsApp Indonesia (E.164, diawali 62). Dipakai memisahkan
# pengguna Telegram vs WhatsApp kalau kedua bot berbagi database yang sama
# (DATABASE_URL sama), supaya pengingat tidak nyasar ke platform lain.
_PHONE_RE = re.compile(r"^62\d{8,12}$")


def _is_whatsapp_number(user_id: str) -> bool:
    return bool(_PHONE_RE.match(user_id))

# Pesan pengingat (dikirim sekali sehari ke anak yang belum belajar).
REMINDER_TEXT = (
    "Hai, Adik! 👋 Kak Moana kangen ngajak belajar nih. 😊\n"
    "Hari ini kamu belum belajar, lho. Yuk sempatkan 5 menit aja belajar "
    "sama Kak Moana, biar semangatmu tetap menyala! 🔥\n"
    "Ketik *menu* untuk mulai ya!"
)


def reminder_job_once(sent_today: set, platform: str = "whatsapp") -> list[tuple[str, str]]:
    """Cari penerima pengingat hari ini.

    Return list [(user_id, teks_pengingat)] untuk anak yang belum diingatkan
    dan belum belajar hari ini. Dipanggil bot masing-masing platform; kalau
    belum waktunya (di luar jendela jam) atau pengingat dimatikan, return [].

    ``platform`` ("whatsapp" / "telegram") dipakai menyaring user dari
    platform lain kalau kedua bot berbagi database yang sama.
    """
    if not REMINDER_ENABLED:
        return []
    hour = datetime.now().hour
    if not (REMINDER_HOUR <= hour < REMINDER_MAX_HOUR):
        return []

    today = datetime.now().date().isoformat()
    targets = []
    for user_id in database.get_active_user_ids(days=REMINDER_ACTIVE_DAYS):
        is_phone = _is_whatsapp_number(user_id)
        if platform == "whatsapp" and not is_phone:
            continue  # ini user Telegram, bukan WhatsApp
        if platform == "telegram" and is_phone:
            continue  # ini user WhatsApp, bukan Telegram

        key = (today, user_id)
        if key in sent_today:
            continue  # sudah diingatkan hari ini
        info = database.get_streak(user_id)
        if info["active_today"]:
            continue  # sudah belajar hari ini, tidak perlu diingatkan
        sent_today.add(key)
        targets.append((user_id, REMINDER_TEXT))
    return targets
