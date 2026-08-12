path = "telegram_bot.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

laporan_code = """async def laporan_command(update, context):
    import database
    user_id = update.effective_user.id
    progress = database.get_user_progress(user_id)
    
    if not progress:
        await update.message.reply_text("Belum ada riwayat aktivitas belajar yang tercatat, Adik/Orang Tua. Yuk, mulai belajar dengan /start!")
        return
        
    text = "📊 *Laporan Kemajuan Belajar Siswa*\\n\\n"
    for subject, count, last_time in progress:
        text += f"• *{subject.capitalize()}*: {count} interaksi obrolan/soal\\n"
        
    text += "\\nTerus semangat mendampingi proses belajar anak! 😊"
    await update.message.reply_markdown(text)
"""

if "async def laporan_command" not in content:
    target = 'if __name__ == "__main__":'
    if target in content:
        content = content.replace(target, laporan_code + "\n\n" + target)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fungsi laporan_command berhasil dikembalikan dengan selamat!")
    else:
        print("Gagal menemukan batas bawah file.")
else:
    print("Fungsi laporan_command sudah ada.")
