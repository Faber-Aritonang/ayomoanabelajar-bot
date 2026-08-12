path = "telegram_bot.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

rapor_code = """async def rapor_command(update, context):
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
        history_text += f"[{msg['subject'].upper()}] {pengirim}: {msg['content']}\\n"
        
    system_prompt = "Kamu adalah konsultan pendidikan yang ahli memberikan umpan balik (feedback) positif dan konstruktif kepada orang tua."
    user_prompt = f\"\"\"Berikut adalah transkrip riwayat percakapan belajar seorang siswa SD dengan tutor AI-nya baru-baru ini:
    
{history_text}

TUGAS:
Buatkan ringkasan evaluasi (rapor naratif) maksimal 2 paragraf pendek untuk orang tua siswa. 
1. Sebutkan apa yang sudah dipahami dengan baik berdasarkan riwayat.
2. Sebutkan konsep yang masih perlu pengulangan/perbaikan (jika ada).
3. Berikan saran praktis dan actionable yang bisa dilakukan ayah/ibunya di rumah.

Gunakan nada bicara yang profesional, hangat, dan suportif. Hindari pengantar basa-basi, langsung ke isi rapor.\"\"\"
    
    try:
        # Menggunakan LLM untuk memproses transkrip menjadi ringkasan
        rapor_text = get_ai_reply("umum", system_prompt, [], user_prompt)
        
        pesan_rapor = f"📑 *RAPOR EVALUASI MINGGUAN AI* 📑\\n\\n{rapor_text}"
        await update.message.reply_markdown(pesan_rapor)
        
    except Exception as e:
        print(f"Error rapor: {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan teknis saat menyusun rapor. Coba lagi nanti ya.")
"""

if "async def rapor_command" not in content:
    target = "if __name__ == \"__main__\":"
    if target in content:
        content = content.replace(target, rapor_code + "\n\n" + target)
        
        # Tambahkan handler
        handler_target = "app.add_handler(CommandHandler(\"bintang\", bintang_command))"
        handler_replacement = handler_target + "\n    app.add_handler(CommandHandler(\"rapor\", rapor_command))"
        content = content.replace(handler_target, handler_replacement)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fitur /rapor naratif berhasil ditambahkan ke telegram_bot.py!")
    else:
        print("Gagal menemukan batas bawah file.")
else:
    print("Fitur /rapor sudah ada.")
