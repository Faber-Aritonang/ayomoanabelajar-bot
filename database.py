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
