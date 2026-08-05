"""
telegram_bot.py
================
Bot Telegram "Ayo, Moana Belajar!" — asisten belajar untuk anak kelas 3 SD
(usia ~9 tahun). Anak memilih mata pelajaran lewat tombol, lalu bisa
ngobrol/bertanya bebas seputar pelajaran itu ke "Kak Moana" (persona AI).

Cara jalankan:
    source venv/bin/activate
    python3 telegram_bot.py
"""

import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database
from llm import get_ai_reply
from subjects import get_subject, list_subjects

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_NAME = "Ayo, Moana Belajar!"
HISTORY_LIMIT = 10  # jumlah pesan terakhir yang dikirim sebagai konteks ke LLM


def build_subject_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, data in list_subjects():
        label = f"{data['emoji']} {data['name']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"subject:{key}")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("subject", None)
    text = (
        f"Halo, Adik! 👋 Selamat datang di *{BOT_NAME}*!\n\n"
        "Aku Kak Moana, teman belajar untuk kelas 3 SD. 😊\n"
        "Yuk, pilih dulu mau belajar apa hari ini:"
    )
    await update.message.reply_markdown(text, reply_markup=build_subject_keyboard())


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Mau ganti pelajaran apa, Adik?", reply_markup=build_subject_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Perintah yang bisa dipakai:*\n"
        "/start - mulai dari awal & pilih pelajaran\n"
        "/menu - ganti mata pelajaran\n"
        "/reset - mulai obrolan baru (lupakan obrolan sebelumnya)\n"
        "/help - tampilkan bantuan ini\n\n"
        "Setelah pilih pelajaran, langsung saja ketik pertanyaanmu ya! 😊"
    )
    await update.message.reply_markdown(text)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text(
            "Belum ada pelajaran yang dipilih. Ketik /start dulu ya!"
        )
        return
    # Reset hanya menghapus konteks 'ingatan' percakapan (riwayat tetap
    # tersimpan di database untuk log), jadi obrolan berikutnya mulai segar.
    context.user_data["reset_marker"] = True
    subject_name = get_subject(subject_key)["name"]
    await update.message.reply_text(
        f"Oke, obrolan {subject_name} kita mulai dari awal lagi ya! 🔄"
    )


async def subject_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    subject_key = query.data.split(":", 1)[1]
    subject = get_subject(subject_key)
    if not subject:
        await query.edit_message_text("Wah, pelajaran itu tidak ditemukan. Coba /menu lagi ya.")
        return

    context.user_data["subject"] = subject_key
    context.user_data["reset_marker"] = True  # mulai konteks segar tiap ganti pelajaran

    await query.edit_message_text(
        f"{subject['emoji']} Oke! Sekarang kita belajar *{subject['name']}* ya.\n"
        "Langsung tanya apa saja seputar pelajaran ini, atau minta Kak Moana kasih soal latihan!",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text.strip()

    if len(user_text) < 1:
        await update.message.reply_text("Coba ketik pertanyaanmu, ya!")
        return

    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text(
            "Pilih dulu mau belajar apa, ya, Adik!", reply_markup=build_subject_keyboard()
        )
        return

    subject = get_subject(subject_key)

    # Kalau baru saja /reset atau baru pilih subject, jangan bawa histori lama
    if context.user_data.pop("reset_marker", False):
        history = []
    else:
        history = database.get_recent_messages(user.id, subject_key, limit=HISTORY_LIMIT)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    reply = get_ai_reply(subject_key, subject["system_prompt"], history, user_text)

    database.save_message(user.id, user.username or user.first_name, subject_key, "user", user_text)
    database.save_message(user.id, user.username or user.first_name, subject_key, "assistant", reply)

    await update.message.reply_text(reply)


def main():
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tidak ditemukan. Cek file .env kamu.")

    database.init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("laporan", laporan_command))
    app.add_handler(CommandHandler("bintang", bintang_command))
    app.add_handler(CommandHandler("kuis", kuis_command))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(subject_chosen, pattern=r"^subject:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    render_url = os.getenv("RENDER_EXTERNAL_URL")

    if render_url:
        # Mode WEBHOOK - dipakai saat deploy di Render (Web Service, free tier)
        port = int(os.getenv("PORT", "10000"))
        webhook_path = "webhook"
        webhook_url = f"{render_url}/{webhook_path}"
        logger.info("%s sedang berjalan (Telegram, webhook) di %s", BOT_NAME, webhook_url)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=webhook_url,
        )
    else:
        # Mode POLLING - dipakai saat dijalankan lokal di laptop
        logger.info("%s sedang berjalan (Telegram, polling)...", BOT_NAME)
        app.run_polling()








async def kuis_command(update, context):
    from subjects import get_subject
    from llm import get_ai_reply
    import database

    user_id = update.effective_user.id
    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text("Pilih dulu mau belajar apa ya, Adik! Ketik /start atau /menu.")
        return

    subject = get_subject(subject_key)
    subject_name = subject["name"]
    system_prompt = subject["system_prompt"]
    
    history = database.get_recent_messages(user_id, subject_key, limit=6)
    
    # Menggunakan triple quotes untuk string multi-baris agar tidak error
    prompt = f"""Buatkan 1 soal latihan untuk mata pelajaran {subject_name}. Berikan pilihan ganda (A, B, C, D) tanpa kunci jawaban di awal.
    
INSTRUKSI ADAPTIF PENTING: Evaluasi pemahaman anak dari riwayat obrolan yang diberikan. Jika anak sering salah atau bingung, berikan soal yang lebih dasar dan mudah. Jika anak menjawab dengan cepat dan benar, berikan soal yang 1 tingkat lebih sulit (Level Up). Sesuaikan nada bicaramu agar selalu menyemangati!"""
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        question_text = get_ai_reply(subject_key, system_prompt, history, prompt)
        context.user_data["in_quiz"] = True
        
        # Simpan soal kuis ke database agar Kak Moana ingat apa yang baru saja ia tanyakan
        username = update.effective_user.username or update.effective_user.first_name
        database.save_message(user_id, username, subject_key, "assistant", question_text)
        await update.message.reply_text(f"📝 *Kuis Adaptif ({subject_name})*\n\n" + question_text)
    except Exception as e:
        print(f"Error kuis: {e}")
        await update.message.reply_text("Maaf, Kak Moana sedang kesulitan menyiapkan kuis saat ini. Coba lagi ya!")


async def laporan_command(update, context):
    import database
    user_id = update.effective_user.id
    progress = database.get_user_progress(user_id)
    
    if not progress:
        await update.message.reply_text("Belum ada riwayat aktivitas belajar yang tercatat, Adik/Orang Tua. Yuk, mulai belajar dengan /start!")
        return
        
    text = "📊 *Laporan Kemajuan Belajar Siswa*\n\n"
    for subject, count, last_time in progress:
        text += f"• *{subject.capitalize()}*: {count} interaksi obrolan/soal\n"
        
    text += "\nTerus semangat mendampingi proses belajar anak! 😊"
    await update.message.reply_markdown(text)


async def bintang_command(update, context):
    import database
    user_id = update.effective_user.id
    progress = database.get_user_progress(user_id)
    
    if not progress:
        await update.message.reply_text("Kamu belum punya bintang, nih. Yuk mulai mengobrol dan jawab kuis dari Kak Moana untuk mengumpulkan bintang! 🌟")
        return
        
    total_interaksi = sum([count for subject, count, last_time in progress])
    total_bintang = total_interaksi // 5  # 1 Bintang untuk setiap 5 interaksi
    
    if total_bintang == 0:
        butuh = 5 - (total_interaksi % 5)
        await update.message.reply_text(f"Semangat! Kamu butuh {butuh} interaksi lagi untuk mendapatkan Bintang pertamamu! 🌟")
        return
        
    teks_bintang = "⭐" * total_bintang
    
    pesan = f"🎉 *Koleksi Bintang Keaktifanmu!* 🎉\n\n"
    pesan += f"Luar biasa! Kamu sudah belajar sangat rajin dan berhasil mengumpulkan:\n"
    pesan += f"{teks_bintang} ({total_bintang} Bintang)\n\n"
    pesan += "Terus semangat belajar bersama Kak Moana ya! 🚀"
    
    await update.message.reply_markdown(pesan)


if __name__ == "__main__":
    main()
