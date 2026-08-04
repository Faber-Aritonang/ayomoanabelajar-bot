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
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tidak ditemukan. Cek file .env kamu.")

    database.init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
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


if __name__ == "__main__":
    main()
