import re

path = "telegram_bot.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Pola regex untuk menemukan blok kuis_command lama
pattern = r"async def kuis_command\(update, context\):.*?except Exception as e:.*?await update\.message\.reply_text\(\"Maaf, Kak Moana sedang kesulitan menyiapkan kuis saat ini\. Coba lagi ya!\"\)"

new_code = """async def kuis_command(update, context):
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
    
    # 1. Ambil 6 pesan terakhir untuk mengevaluasi pemahaman anak
    history = database.get_recent_messages(user_id, subject_key, limit=6)
    
    # 2. Prompt adaptif: instruksikan AI untuk membaca riwayat dan menyesuaikan level
    prompt = f"Buatkan 1 soal latihan untuk mata pelajaran {subject_name}. Berikan pilihan ganda (A, B, C, D) tanpa kunci jawaban di awal.\n\nINSTRUKSI ADAPTIF PENTING: Evaluasi pemahaman anak dari riwayat obrolan yang diberikan. Jika anak sering salah atau bingung, berikan soal yang lebih dasar dan mudah. Jika anak menjawab dengan cepat dan benar, berikan soal yang 1 tingkat lebih sulit (Level Up). Sesuaikan nada bicaramu agar selalu menyemangati!"
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # 3. Kirim history bersama prompt ke AI
        question_text = get_ai_reply(subject_key, system_prompt, history, prompt)
        
        context.user_data["in_quiz"] = True
        
        await update.message.reply_text(f"📝 *Kuis Adaptif ({subject_name})*\n\n" + question_text)
    except Exception as e:
        print(f"Error kuis: {e}")
        await update.message.reply_text("Maaf, Kak Moana sedang kesulitan menyiapkan kuis saat ini. Coba lagi ya!")"""

# Ganti blok lama dengan blok baru yang adaptif
new_content = re.sub(pattern, new_code, content, flags=re.DOTALL)

if new_content != content:
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Fitur Kuis Adaptif berhasil dipasang di telegram_bot.py!")
else:
    print("Gagal menemukan blok kuis_command. Pastikan file belum diubah manual.")
