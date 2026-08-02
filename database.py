"""
database.py
============
Penyimpanan riwayat percakapan pakai SQLite. Dipakai untuk:
1. Mencatat log semua percakapan (buat portofolio / debugging).
2. Mengambil beberapa pesan terakhir supaya bot "ingat" konteks obrolan
   dalam satu mata pelajaran yang sama.
"""

import sqlite3
from datetime import datetime

DB_PATH = "chatbot.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            subject TEXT,
            role TEXT,          -- 'user' atau 'assistant'
            message TEXT,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_message(user_id, username, subject, role, message):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (user_id, username, subject, role, message, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(user_id), username, subject, role, message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_recent_messages(user_id, subject, limit=10):
    """
    Ambil `limit` pesan terakhir (user + assistant) untuk user & subject
    tertentu, urut dari yang paling lama ke paling baru, dalam format
    siap pakai untuk parameter `messages` Anthropic API:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT role, message FROM conversations "
        "WHERE user_id = ? AND subject = ? "
        "ORDER BY id DESC LIMIT ?",
        (str(user_id), subject, limit),
    )
    rows = cur.fetchall()
    conn.close()
    rows.reverse()  # jadi urut lama -> baru
    return [{"role": role, "content": message} for role, message in rows]
