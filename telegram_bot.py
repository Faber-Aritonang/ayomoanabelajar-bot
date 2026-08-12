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
import quiz
import stt
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
    context.user_data.pop("quiz", None)  # keluar dari kuis yang sedang berjalan
    text = (
        f"Halo, Adik! 👋 Selamat datang di *{BOT_NAME}*!\n\n"
        "Aku Kak Moana, teman belajar untuk kelas 3 SD. 😊\n"
        "Yuk, pilih dulu mau belajar apa hari ini:"
    )
    await update.message.reply_markdown(text, reply_markup=build_subject_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Perintah yang bisa dipakai:*\n"
        "/start - mulai dari awal & pilih pelajaran\n"
        "/menu - ganti mata pelajaran\n"
        "/reset - mulai obrolan baru (lupakan obrolan sebelumnya)\n"
        "/help - tampilkan bantuan ini\n\n"
        "🎤 *Mode Suara:* kirim pesan suara (voice note) untuk bertanya "
        "dengan bicara — Kak Moana akan mendengarkan dan menjawabnya!\n\n"
        "Setelah pilih pelajaran, langsung saja kirim pertanyaanmu ya! 😊"
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
    context.user_data.pop("quiz", None)  # keluar dari kuis yang sedang berjalan
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
    context.user_data.pop("quiz", None)  # pelajaran baru = kuis baru

    await query.edit_message_text(
        f"{subject['emoji']} Oke! Sekarang kita belajar *{subject['name']}* ya.\n"
        "Langsung tanya apa saja seputar pelajaran ini, atau minta Kak Moana kasih soal latihan!",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if len(user_text) < 1:
        await update.message.reply_text("Coba ketik pertanyaanmu, ya!")
        return
    await process_text(update, context, user_text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mode suara: transkripsi voice note, lalu lanjutkan seperti pesan teks."""
    user = update.effective_user

    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text(
            "Pilih dulu mau belajar apa, ya, Adik!", reply_markup=build_subject_keyboard()
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await update.message.reply_text("🎤 Aku dengar ya, Adik! Sebentar ya...")

    voice = update.message.voice
    if voice.duration and voice.duration > 120:
        await update.message.reply_text(
            "Wah, pesan suaranya kepanjangan, Adik! 😅 Coba kirim bagian yang "
            "pendek-pendek saja ya (maksimal 2 menit)."
        )
        return

    try:
        file = await voice.get_file()
        audio_bytes = await file.download_as_bytearray()
        user_text = stt.transcribe_audio(bytes(audio_bytes))
    except Exception as e:
        logger.error("Gagal memproses voice dari %s: %s", user.id, e)
        await update.message.reply_text(
            "Ups, suara kamu belum bisa kudengar dengan jelas. "
            "Coba kirim lagi, atau ketik pertanyaannya ya! 🙏"
        )
        return

    if not user_text:
        await update.message.reply_text(
            "Aku tidak mendengar kata-katanya, Adik. Coba bicara lebih jelas atau lebih dekat dengan HP ya! 🎤"
        )
        return

    # Beri tahu anak teks yang tertangkap, lalu proses seperti pesan biasa.
    await update.message.reply_markdown(f'🎧 Kak Moana mendengar: *"{user_text}"*')
    await process_text(update, context, user_text)


async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """Inti alur pesan teks — dipakai oleh pesan ketik maupun hasil transkripsi suara."""
    user = update.effective_user

    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text(
            "Pilih dulu mau belajar apa, ya, Adik!", reply_markup=build_subject_keyboard()
        )
        return

    subject = get_subject(subject_key)

    # Kalau kuis sedang berjalan, pesan ini adalah JAWABAN kuis.
    if context.user_data.get("quiz"):
        await handle_quiz_answer(update, context, user_text, subject_key, subject)
        return

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


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, answer_text, subject_key, subject):
    """Proses jawaban anak untuk kuis yang sedang berjalan (Telegram)."""
    user = update.effective_user
    username = user.username or user.first_name

    feedback, need_next, summary = quiz.answer_quiz(context.user_data, answer_text)

    if summary:  # sesi selesai — simpan skor ke database
        database.save_quiz_score(user.id, username, subject_key, summary["score"], summary["total"])

    database.save_message(user.id, username, subject_key, "user", answer_text)
    database.save_message(user.id, username, subject_key, "assistant", feedback)
    await update.message.reply_markdown(feedback)

    if need_next == "NEXT":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        history = database.get_recent_messages(user.id, subject_key, limit=6)
        question_text = quiz.start_quiz(context.user_data, subject_key, subject, history)
        if question_text:
            database.save_message(user.id, username, subject_key, "assistant", question_text)
            await update.message.reply_markdown(f"📝 *Kuis Adaptif ({subject['name']})*\n\n{question_text}")
        else:
            await update.message.reply_text(
                "Maaf, Kak Moana sedang kesulitan menyiapkan soal berikutnya. Coba lagi ya!"
            )


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
    app.add_handler(CommandHandler("rapor", rapor_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("kuis", kuis_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(subject_chosen, pattern=r"^subject:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

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
    user_id = update.effective_user.id
    subject_key = context.user_data.get("subject")
    if not subject_key:
        await update.message.reply_text("Pilih dulu mau belajar apa ya, Adik! Ketik /start atau /menu.")
        return

    subject = get_subject(subject_key)
    subject_name = subject["name"]

    # Mulai sesi kuis baru (skor direset). Soal sebelumnya dibuang.
    context.user_data.pop("quiz", None)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    history = database.get_recent_messages(user_id, subject_key, limit=6)
    question_text = quiz.start_quiz(context.user_data, subject_key, subject, history)

    if not question_text:
        await update.message.reply_text(
            "Maaf, Kak Moana sedang kesulitan menyiapkan kuis saat ini. Coba lagi ya!"
        )
        return

    # Simpan soal ke database agar Kak Moana ingat apa yang baru saja ditanyakan
    username = update.effective_user.username or update.effective_user.first_name
    database.save_message(user_id, username, subject_key, "assistant", question_text)
    await update.message.reply_text(f"📝 *Kuis Adaptif ({subject_name})*\n\n{question_text}")


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

    quiz_rows = database.get_quiz_summary(user_id)
    if quiz_rows:
        text += "\n🎯 *Skor Kuis:*\n"
        for subject, total_poin, total_soal in quiz_rows:
            text += f"• *{subject.capitalize()}*: {total_poin} poin dari {total_soal} soal\n"

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


async def rapor_command(update, context):
    import database
    from llm import get_ai_reply
    
    user_id = update.effective_user.id
    
    await update.message.reply_text("⏳ Mohon tunggu sebentar ya, Kak Moana sedang menganalisis data untuk menyusun Rapor Evaluasi Adik...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Ambil 20 interaksi terakhir dari semua mata pelajaran
    recent_history = database.get_all_recent_messages(user_id, limit=20)
    
    if len(recent_history) < 5:
        await update.message.reply_text("Data aktivitas belajar belum cukup untuk dianalisis. Yuk, ajak Adik berlatih lebih banyak lagi bersama Kak Moana! 🚀")
        return
        
    # Format riwayat untuk dibaca AI
    history_text = ""
    for msg in recent_history:
        pengirim = "Anak" if msg["role"] == "user" else "Tutor AI"
        history_text += f"[{msg['subject'].upper()}] {pengirim}: {msg['content']}\n"
        
    system_prompt = "Kamu adalah konsultan pendidikan yang ahli memberikan umpan balik (feedback) positif dan konstruktif kepada orang tua."
    user_prompt = f"""Berikut adalah transkrip riwayat percakapan belajar seorang siswa SD dengan tutor AI-nya baru-baru ini:
    
{history_text}

TUGAS:
Buatkan ringkasan evaluasi (rapor naratif) maksimal 2 paragraf pendek untuk orang tua siswa. 
1. Sebutkan apa yang sudah dipahami dengan baik berdasarkan riwayat.
2. Sebutkan konsep yang masih perlu pengulangan/perbaikan (jika ada).
3. Berikan saran praktis dan actionable yang bisa dilakukan ayah/ibunya di rumah.

Gunakan nada bicara yang profesional, hangat, dan suportif. Hindari pengantar basa-basi, langsung ke isi rapor."""
    
    try:
        # Menggunakan LLM untuk memproses transkrip menjadi ringkasan
        rapor_text = get_ai_reply("umum", system_prompt, [], user_prompt)
        
        pesan_rapor = f"📑 *RAPOR EVALUASI MINGGUAN AI* 📑\n\n{rapor_text}"
        await update.message.reply_markdown(pesan_rapor)
        
    except Exception as e:
        print(f"Error rapor: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan teknis saat menyusun rapor. Coba lagi nanti ya.")


async def menu_command(update, context):
    pesan = "🗂️ *Dashboard Ayo, Moana Belajar!* 🗂️\n\n"
    pesan += "🎓 *Area Belajar (Untuk Adik):*\n"
    pesan += "• /start - Pilih pelajaran dan mulai obrolan\n"
    pesan += "• /kuis - Uji kemampuan dengan soal adaptif\n"
    pesan += "• /bintang - Lihat koleksi bintang prestasimu ⭐\n\n"
    pesan += "👨‍👩‍👧 *Area Pantauan (Untuk Orang Tua):*\n"
    pesan += "• /laporan - Cek angka keaktifan harian\n"
    pesan += "• /rapor - Baca analisis evaluasi dari AI Tutor\n\n"
    pesan += "Ketik salah satu perintah di atas kapan saja ya!"
    
    await update.message.reply_markdown(pesan)


if __name__ == "__main__":
    main()
