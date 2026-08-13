"""
database.py
============
Penyimpanan riwayat percakapan mendukung SQLite (lokal) dan PostgreSQL (Cloud Render).
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Ambil DATABASE_URL dari environment (Render), fallback ke SQLite lokal
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///chatbot.db")

# Penyesuaian khusus untuk URL postgres dari Render (jika menggunakan awalan postgres://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Inisialisasi Engine SQLAlchemy
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    username = Column(String)
    subject = Column(String)
    role = Column(String)  # 'user' atau 'assistant'
    message = Column(Text)
    timestamp = Column(String)


class QuizScoreModel(Base):
    __tablename__ = "quiz_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    username = Column(String)
    subject = Column(String)
    score = Column(Integer)
    total_questions = Column(Integer)
    timestamp = Column(String)


def save_quiz_score(user_id, username, subject, score, total_questions):
    db = SessionLocal()
    try:
        db_item = QuizScoreModel(
            user_id=str(user_id),
            username=username,
            subject=subject,
            score=score,
            total_questions=total_questions,
            timestamp=datetime.now().isoformat()
        )
        db.add(db_item)
        db.commit()
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

def save_message(user_id, username, subject, role, message):
    db = SessionLocal()
    try:
        db_item = ConversationModel(
            user_id=str(user_id),
            username=username,
            subject=subject,
            role=role,
            message=message,
            timestamp=datetime.now().isoformat()
        )
        db.add(db_item)
        db.commit()
    finally:
        db.close()

def get_recent_messages(user_id, subject, limit=10):
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversationModel.role, ConversationModel.message)
            .filter(ConversationModel.user_id == str(user_id), ConversationModel.subject == subject)
            .order_by(ConversationModel.id.desc())
            .limit(limit)
            .all()
        )
        # Urutkan dari yang paling lama ke paling baru
        rows.reverse()
        return [{"role": role, "content": message} for role, message in rows]
    finally:
        db.close()

def get_user_progress(user_id):
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = (
            db.query(
                ConversationModel.subject,
                func.count(ConversationModel.id),
                func.max(ConversationModel.timestamp)
            )
            .filter(ConversationModel.user_id == str(user_id), ConversationModel.role == "user")
            .group_by(ConversationModel.subject)
            .all()
        )
        return rows
    except Exception as e:
        print(f"Error laporan: {e}")
        return []
    finally:
        db.close()


def get_all_recent_messages(user_id, limit=20):
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversationModel.subject, ConversationModel.role, ConversationModel.message)
            .filter(ConversationModel.user_id == str(user_id))
            .order_by(ConversationModel.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [{"subject": subject, "role": role, "content": message} for subject, role, message in rows]
    finally:
        db.close()


def get_streak(user_id):
    """Hitung streak hari belajar berturut-turut (role='user') dari riwayat.

    Return dict:
        streak       - jumlah hari berturut-turut (berakhir hari ini, atau
                       kemarin kalau hari ini belum ada aktivitas — streak
                       "belum putus" selama hari ini masih berjalan)
        last_active  - tanggal aktivitas terakhir (date) atau None
        active_today - True kalau sudah ada aktivitas hari ini
    """
    from datetime import date, datetime, timedelta

    db = SessionLocal()
    try:
        rows = (
            db.query(ConversationModel.timestamp)
            .filter(ConversationModel.user_id == str(user_id), ConversationModel.role == "user")
            .all()
        )
    finally:
        db.close()

    dates = set()
    for (ts,) in rows:
        try:
            dates.add(datetime.fromisoformat(ts).date())
        except (ValueError, TypeError):
            continue

    if not dates:
        return {"streak": 0, "last_active": None, "active_today": False}

    today = date.today()
    cursor = today if today in dates else today - timedelta(days=1)
    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)

    return {"streak": streak, "last_active": max(dates), "active_today": today in dates}


def get_active_user_ids(days=7):
    """Daftar user_id yang aktif dalam N hari terakhir (kandidat pengingat).

    Dipakai fitur pengingat belajar harian supaya tidak mengirim pesan ke
    orang yang sudah tidak pernah memakai bot.
    """
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversationModel.user_id)
            .filter(ConversationModel.timestamp >= cutoff)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def get_quiz_summary(user_id):
    """Rekap skor kuis per mata pelajaran: [(subject, total_poin, total_soal)]"""
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = (
            db.query(
                QuizScoreModel.subject,
                func.sum(QuizScoreModel.score),
                func.sum(QuizScoreModel.total_questions),
            )
            .filter(QuizScoreModel.user_id == str(user_id))
            .group_by(QuizScoreModel.subject)
            .all()
        )
        return rows
    except Exception as e:
        print(f"Error rekap kuis: {e}")
        return []
    finally:
        db.close()
