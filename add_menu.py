path = "telegram_bot.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

menu_code = """async def menu_command(update, context):
    pesan = "🗂️ *Dashboard Ayo, Moana Belajar!* 🗂️\\n\\n"
    pesan += "🎓 *Area Belajar (Untuk Adik):*\\n"
    pesan += "• /start - Pilih pelajaran dan mulai obrolan\\n"
    pesan += "• /kuis - Uji kemampuan dengan soal adaptif\\n"
    pesan += "• /bintang - Lihat koleksi bintang prestasimu ⭐\\n\\n"
    pesan += "👨‍👩‍👧 *Area Pantauan (Untuk Orang Tua):*\\n"
    pesan += "• /laporan - Cek angka keaktifan harian\\n"
    pesan += "• /rapor - Baca analisis evaluasi dari AI Tutor\\n\\n"
    pesan += "Ketik salah satu perintah di atas kapan saja ya!"
    
    await update.message.reply_markdown(pesan)
"""

if "async def menu_command" not in content:
    target = 'if __name__ == "__main__":'
    if target in content:
        content = content.replace(target, menu_code + "\n\n" + target)
        
        # Cari baris handler terakhir (rapor) untuk menyisipkan handler menu
        handler_target = 'app.add_handler(CommandHandler("rapor", rapor_command))'
        if handler_target in content:
            handler_replacement = handler_target + '\n    app.add_handler(CommandHandler("menu", menu_command))'
            content = content.replace(handler_target, handler_replacement)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Fitur Dasbor /menu berhasil ditambahkan ke telegram_bot.py!")
        else:
            print("Gagal menemukan handler rapor. Pastikan kodenya tidak berubah.")
    else:
        print("Gagal menemukan batas bawah file.")
else:
    print("Fitur /menu sudah ada.")
