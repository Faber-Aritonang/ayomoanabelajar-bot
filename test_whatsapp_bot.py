"""
test_whatsapp_bot.py
=====================
Tes offline untuk whatsapp_bot.py — TANPA perlu HP atau koneksi WhatsApp.

Skrip ini menyimulasikan pesan WhatsApp masuk (event protobuf Neonize) dan
memverifikasi bahwa semua perintah bot merespons dengan benar. Aman dijalankan
kapan saja, bahkan saat bot tidak terhubung ke WhatsApp.

Cara jalankan:
    source venv/bin/activate
    python3 test_whatsapp_bot.py

Kode keluar: 0 = semua lulus, 1 = ada yang gagal.
"""

import os
import sys

# Pakai database test terpisah supaya data asli pengguna tidak tercemar.
# (Harus diset SEBELUM import database/whatsapp_bot.)
TEST_DB = "test_whatsapp.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

import database
import quiz
import reminders
import whitelist
import whatsapp_bot as wb
from neonize.proto.Neonize_pb2 import Message as MessageEv
from neonize.utils import build_jid

PHONE = "6281234567890"  # nomor uji (bukan nomor asli)


class FakeClient:
    """Pengganti NewClient: tidak mengirim apa pun, hanya mencatat pesan."""

    connected = False

    def __init__(self):
        self.sent = []

    def send_message(self, to, msg):
        self.sent.append((str(to.User), msg))

    def download_any(self, message):
        """Tiruan download media voice note — kembalikan byte audio palsu."""
        return b"\xff\xfb\x90\x00fake-ogg-audio"


def make_event(text, from_me=False, is_group=False, phone=PHONE):
    """Bangun event pesan WhatsApp palsu berisi teks."""
    ev = MessageEv()
    ev.Info.MessageSource.Chat.CopyFrom(build_jid(phone, "s.whatsapp.net"))
    ev.Info.MessageSource.Sender.CopyFrom(build_jid(phone, "s.whatsapp.net"))
    ev.Info.MessageSource.IsFromMe = from_me
    ev.Info.MessageSource.IsGroup = is_group
    ev.Message.conversation = text
    return ev


def make_voice_event(ptt=True, seconds=30, from_me=False, is_group=False, phone=PHONE):
    """Bangun event voice note WhatsApp palsu (PTT, tanpa teks)."""
    ev = MessageEv()
    ev.Info.MessageSource.Chat.CopyFrom(build_jid(phone, "s.whatsapp.net"))
    ev.Info.MessageSource.Sender.CopyFrom(build_jid(phone, "s.whatsapp.net"))
    ev.Info.MessageSource.IsFromMe = from_me
    ev.Info.MessageSource.IsGroup = is_group
    ev.Message.audioMessage.PTT = ptt
    ev.Message.audioMessage.seconds = seconds
    ev.Message.audioMessage.mimetype = "audio/ogg; codecs=opus"
    return ev


def fresh_user():
    """Nomor unik agar state pelajaran antar skenario tidak saling menimpa."""
    fresh_user.counter = getattr(fresh_user, "counter", 0) + 1
    return f"6281000000{fresh_user.counter:02d}"


def insert_message(phone, subject, role, ts):
    """Tulis langsung ke database test dengan timestamp tertentu."""
    db = database.SessionLocal()
    try:
        db.add(
            database.ConversationModel(
                user_id=phone,
                username=phone,
                subject=subject,
                role=role,
                message="pesan uji",
                timestamp=ts,
            )
        )
        db.commit()
    finally:
        db.close()


def fake_ai(subject_key, system_prompt, history, user_message):
    """Ganti get_ai_reply agar tes tidak memanggil API berbayar.

    Kalau prompt meminta KUNCI (pembuatan soal kuis), kembalikan soal dengan
    kunci jawaban; selain itu balas teks biasa.
    """
    if "KUNCI: X" in (user_message or ""):
        return "Berapa hasil 2 + 2?\nA. 3\nB. 4\nC. 5\nD. 6\nKUNCI: B"
    return f"AI uji: {user_message}"


def main():
    database.init_db()  # buat tabel di database test
    client = FakeClient()
    # Ganti get_ai_reply di SEMUA modul yang mengimpornya (whatsapp_bot & quiz).
    wb.get_ai_reply = fake_ai
    quiz.get_ai_reply = fake_ai
    # Ganti transkripsi suara dengan stub — tes tidak boleh memanggil Groq.
    wb.stt.transcribe_audio = lambda audio_bytes, filename="voice.ogg": "berapa hasil dua tambah dua"
    wb._current_client = client

    results = []

    def run(name, ev, expect=None, expect_absent=None):
        client.sent.clear()
        wb.on_message(client, ev)
        if not client.sent:
            ok = expect is None
            results.append((name, ok, "OK (diabaikan, sesuai desain)" if ok else f"harus mengirim pesan: {expect}"))
            return
        # Kuis bisa mengirim >1 pesan (feedback + soal berikutnya); cek SEMUA.
        replies = [msg for _, msg in client.sent]
        joined = "\n---\n".join(replies)
        ok = True
        detail = f"OK ({len(replies)} pesan)"
        if expect and expect not in joined:
            ok = False
            detail = f"harus mengandung {expect!r}, ternyata: {joined[:100]!r}"
        if ok and expect_absent and expect_absent in joined:
            ok = False
            detail = f"tidak boleh mengandung {expect_absent!r}"
        results.append((name, ok, detail))

    def belajar(phone):
        """Skenario bantu: pilih pelajaran dulu untuk pengguna tertentu."""
        run(f"(setup) pilih pelajaran {phone[-2:]}", make_event("1", phone=phone), expect="Matematika")

    # --- Alur dasar (setiap skenario memakai nomor pengguna baru, supaya
    # state pelajaran antar uji tidak saling memengaruhi) ---
    run("chat tanpa pelajaran -> minta pilih", make_event("2+2 berapa?", phone=fresh_user()), expect="Pilih dulu")
    run("perintah menu", make_event("menu", phone=fresh_user()), expect="memilih pelajaran")
    run("perintah mulai (alias)", make_event("mulai", phone=fresh_user()), expect="memilih pelajaran")
    run("pilih pelajaran 1", make_event("1", phone=fresh_user()), expect="Matematika")
    run("pilih pelajaran 4", make_event("4", phone=fresh_user()), expect="IPAS")
    run("pilih pelajaran 6", make_event("6", phone=fresh_user()), expect="Agama Kristen")

    # Chat bebas & kuis: butuh pelajaran aktif dulu.
    p = fresh_user(); belajar(p)
    run("chat bebas", make_event("kenapa langit biru?", phone=p), expect="AI uji: kenapa langit biru?")

    # --- Mode suara (voice note) ---
    run("voice tanpa pelajaran -> minta pilih", make_voice_event(phone=fresh_user()), expect="Pilih dulu")
    p = fresh_user(); belajar(p)
    run(
        "voice note -> transkripsi + echo",
        make_voice_event(phone=p),
        expect="Kak Moana mendengar: *\"berapa hasil dua tambah dua\"*",
    )
    p = fresh_user(); belajar(p)
    run(
        "voice note -> handoff ke alur chat/AI",
        make_voice_event(phone=p),
        expect="AI uji: berapa hasil dua tambah dua",
    )

    # Transkripsi kosong (tidak ada kata terdeteksi).
    wb.stt.transcribe_audio = lambda audio_bytes, filename="voice.ogg": ""
    p = fresh_user(); belajar(p)
    run(
        "voice note tanpa kata -> minta ulang",
        make_voice_event(phone=p),
        expect="tidak mendengar kata-katanya",
    )
    # Kembalikan stub normal untuk sisa tes.
    wb.stt.transcribe_audio = lambda audio_bytes, filename="voice.ogg": "berapa hasil dua tambah dua"
    p = fresh_user(); belajar(p)
    run(
        "voice note kepanjangan (>2 menit) ditolak",
        make_voice_event(seconds=200, phone=p),
        expect="kepanjangan",
    )
    run(
        "file audio biasa (non-PTT) ditolak",
        make_voice_event(ptt=False, phone=fresh_user()),
        expect="belum bisa baca file audio",
    )
    run(
        "voice dari diri sendiri diabaikan",
        make_voice_event(from_me=True, phone=fresh_user()),
        expect=None,
    )
    run(
        "voice di grup diabaikan",
        make_voice_event(is_group=True, phone=fresh_user()),
        expect=None,
    )

    # --- Kuis adaptif dengan penilaian jawaban ---
    # MAX_QUESTIONS = 5; jawaban tanpa huruf tidak dihitung sebagai soal.
    p = fresh_user(); belajar(p)
    run("kuis mulai", make_event("kuis", phone=p), expect="Kuis Adaptif")
    run("kuis jawab benar (+10)", make_event("B", phone=p), expect="BENAR")
    run("kuis jawab salah (+0)", make_event("A", phone=p), expect="Belum tepat")
    run("kuis jawab teks tanpa huruf", make_event("lima belas", phone=p), expect="belum paham jawabanmu")
    run("kuis jawab benar lagi", make_event("jawabannya B", phone=p), expect="BENAR")
    run("kuis jawab benar (soal ke-4)", make_event("B", phone=p), expect="BENAR")
    run("kuis selesai (soal ke-5)", make_event("A", phone=p), expect="Kuis selesai")
    run("kuis selesai -> chat biasa lagi", make_event("A", phone=p), expect="AI uji: A")

    # Bintang/laporan/rapor: tanpa data -> pesan penyemangat (perilaku benar).
    run("bintang (tanpa data)", make_event("bintang", phone=fresh_user()), expect="belum punya bintang")
    run("laporan (tanpa data)", make_event("laporan", phone=fresh_user()), expect="Belum ada riwayat")
    run("rapor (data kurang)", make_event("rapor", phone=fresh_user()), expect="belum cukup")

    # --- Streak belajar harian ---
    run("streak tanpa data", make_event("streak", phone=fresh_user()), expect="belum punya catatan")

    now = datetime.now()
    # User belajar 3 hari berturut-turut (hari ini, kemarin, 2 hari lalu).
    p = fresh_user()
    for d in range(3):
        insert_message(p, "matematika", "user", (now - timedelta(days=d)).isoformat())
    run("streak 3 hari berturut-turut", make_event("streak", phone=p), expect="Streak Belajarmu: 3 hari")

    # Belajar kemarin & 2 hari lalu, TAPI belum hari ini -> streak masih 2
    # (belum putus, karena hari ini masih berjalan).
    p = fresh_user()
    for d in (1, 2):
        insert_message(p, "matematika", "user", (now - timedelta(days=d)).isoformat())
    run("streak berlanjut (belum belajar hari ini)", make_event("streak", phone=p), expect="Streak Belajarmu: 2 hari")

    # Terakhir belajar 3 hari lalu (terputus) -> streak baru mulai.
    p = fresh_user()
    insert_message(p, "matematika", "user", (now - timedelta(days=3)).isoformat())
    run("streak putus (3 hari lalu)", make_event("streak", phone=p), expect="Streak-mu baru mulai")

    # Alias "semangat" juga membuka streak.
    run("streak (alias semangat)", make_event("semangat", phone=p), expect="Streak-mu baru mulai")

    # --- Logika pengingat harian (reminders.py) ---
    reminders.REMINDER_ENABLED = True
    now_hour = datetime.now().hour
    # Paksa "sekarang" berada dalam jendela kirim [jam_sekarang, jam_sekarang+2).
    reminders.REMINDER_HOUR = now_hour
    reminders.REMINDER_MAX_HOUR = (now_hour + 2) % 24
    sent = set()

    # User yang aktif 3 hari berturut-turut dan SUDAH belajar hari ini -> tidak diingatkan.
    p_aktif = fresh_user()
    for d in range(3):
        insert_message(p_aktif, "matematika", "user", (now - timedelta(days=d)).isoformat())
    targets = reminders.reminder_job_once(sent, platform="whatsapp")
    ok_aktif = all(uid != p_aktif for uid, _ in targets)
    results.append(("reminder tidak untuk user yang sudah belajar hari ini", ok_aktif, "OK" if ok_aktif else "harus diingatkan"))

    # User yang terakhir belajar 2 hari lalu -> diingatkan.
    p_lupa = fresh_user()
    insert_message(p_lupa, "matematika", "user", (now - timedelta(days=2)).isoformat())
    targets = reminders.reminder_job_once(sent, platform="whatsapp")
    names = [uid for uid, _ in targets]
    results.append(("reminder pilih user yang lupa belajar", p_lupa in names, "OK" if p_lupa in names else "harus diingatkan"))

    # Sekali diingatkan hari ini -> tidak diingatkan lagi (anti-spam).
    targets2 = reminders.reminder_job_once(sent, platform="whatsapp")
    ok_spam = all(uid != p_lupa for uid, _ in targets2)
    results.append(("reminder anti-spam (1x/hari)", ok_spam, "OK" if ok_spam else "tidak boleh diingatkan 2x"))

    # Saat di luar jendela jam -> tidak ada target.
    reminders.REMINDER_HOUR = (now_hour + 3) % 24
    reminders.REMINDER_MAX_HOUR = (now_hour + 4) % 24
    targets3 = reminders.reminder_job_once(set(), platform="whatsapp")
    results.append(("reminder nonaktif di luar jam", targets3 == [], "OK" if targets3 == [] else "harus kosong"))

    # Filter platform: user Telegram (bukan nomor 62...) tidak diingatkan bot WhatsApp.
    p_tg = "123456789"  # bentuk user_id Telegram
    insert_message(p_tg, "matematika", "user", (now - timedelta(days=2)).isoformat())
    targets4 = reminders.reminder_job_once(set(), platform="whatsapp")
    ok_filt = all(uid != p_tg for uid, _ in targets4)
    results.append(("reminder WhatsApp mengabaikan user Telegram", ok_filt, "OK" if ok_filt else "harus diabaikan"))
    # Sebaliknya, bot Telegram mengabaikan nomor WhatsApp.
    targets5 = reminders.reminder_job_once(set(), platform="telegram")
    ok_filt2 = all(uid != p_lupa for uid, _ in targets5)
    results.append(("reminder Telegram mengabaikan user WhatsApp", ok_filt2, "OK" if ok_filt2 else "harus diabaikan"))

    p = fresh_user(); belajar(p)
    run("reset", make_event("reset", phone=p), expect="awal lagi")
    run("help", make_event("help", phone=fresh_user()), expect="Perintah")
    run("bantuan (alias)", make_event("bantuan", phone=fresh_user()), expect="Perintah")

    # --- Batas & perilaku khusus ---
    run("pesan dari diri sendiri diabaikan", make_event("menu", from_me=True, phone=fresh_user()), expect=None)
    run("pesan grup diabaikan", make_event("menu", is_group=True, phone=fresh_user()), expect=None)
    run("pesan kosong", make_event("", phone=fresh_user()), expect="belum bisa baca")
    p = fresh_user(); belajar(p)
    run("angka 7 (di luar daftar) -> chat", make_event("7", phone=p), expect="AI uji: 7")

    # --- Kegagalan transkripsi voice note ---
    def gagal_transkripsi(audio_bytes, filename="voice.ogg"):
        raise RuntimeError("Groq mati")

    wb.stt.transcribe_audio = gagal_transkripsi
    p = fresh_user(); belajar(p)
    run("voice note gagal transkripsi -> pesan ramah", make_voice_event(phone=p), expect="belum bisa kudengar")
    # Kembalikan stub normal untuk sisa tes.
    wb.stt.transcribe_audio = lambda audio_bytes, filename="voice.ogg": "berapa hasil dua tambah dua"

    # Angka saat pelajaran aktif harus jadi chat, bukan ganti pelajaran.
    p = fresh_user(); belajar(p)
    run("angka saat pelajaran aktif -> chat", make_event("5", phone=p), expect="AI uji: 5")

    # --- Parser perintah langsung ---
    parse_cases = [
        ("menu", ("menu", None)),
        ("/menu", ("menu", None)),
        ("kuis", ("kuis", None)),
        ("streak", ("streak", None)),
        ("semangat", ("streak", None)),
        ("1", ("pilih_subject", 1)),
        ("6", ("pilih_subject", 6)),
        ("7", ("chat", "7")),
        ("2+2 berapa?", ("chat", "2+2 berapa?")),
    ]
    for raw, expected in parse_cases:
        got = wb.parse_command(raw, subject_active=False)
        ok = got == expected
        results.append((f"parse({raw!r})", ok, "OK" if ok else f"harus {expected}, ternyata {got}"))

    # --- Whitelist akses bot ---
    admin = "6281111111111"
    wb.whitelist.ENABLED = True
    wb.whitelist.ADMIN_WHATSAPP = admin
    wb.whitelist._BASE_WHATSAPP = set()
    wb.whitelist._BASE_TELEGRAM = set()

    run("whitelist: non-admin ditolak sopan", make_event("menu", phone=fresh_user()), expect="khusus untuk siswa")
    run("whitelist: non-admin voice ditolak", make_voice_event(phone=fresh_user()), expect="khusus untuk siswa")
    run("whitelist: admin dilayani", make_event("menu", phone=admin), expect="memilih pelajaran")

    # Admin menambah nomor lewat perintah teks.
    run("whitelist: tambah nomor", make_event("tambah 0812-3456-7890", phone=admin), expect="6281234567890 berhasil didaftarkan")
    run("whitelist: nomor baru sudah boleh", make_event("menu", phone="6281234567890"), expect="memilih pelajaran")
    run("whitelist: daftar menampilkan nomor", make_event("daftar", phone=admin), expect="6281234567890")
    run("whitelist: tambah duplikat", make_event("tambah 6281234567890", phone=admin), expect="sudah ada")
    run("whitelist: hapus nomor", make_event("hapus 6281234567890", phone=admin), expect="dihapus dari whitelist")
    run("whitelist: nomor dihapus -> ditolak lagi", make_event("menu", phone="6281234567890"), expect="khusus untuk siswa")
    run("whitelist: non-admin tidak bisa tambah", make_event("tambah 6280000000000", phone="6289999999999"), expect="khusus untuk siswa")
    run("whitelist: format tambah salah", make_event("tambah", phone=admin), expect="tambah <nomor>")
    run("whitelist: nomor tidak valid ditolak", make_event("tambah 22", phone=admin), expect="Nomor tidak valid")

    # Nomor dari env var juga diterima.
    wb.whitelist._BASE_WHATSAPP = {"6285555555555"}
    run("whitelist: nomor dari env dilayani", make_event("menu", phone="6285555555555"), expect="memilih pelajaran")
    wb.whitelist._BASE_WHATSAPP = set()

    # Kembalikan whitelist ke nonaktif supaya tes lain tidak terpengaruh.
    wb.whitelist.ENABLED = False
    wb.whitelist.ADMIN_WHATSAPP = ""

    # --- Keamanan halaman /qr ---
    handler = wb.BotHTTPHandler.__new__(wb.BotHTTPHandler)
    handler._is_connected = lambda: False
    wb.QR_TOKEN = "rahasia"
    for path, expected in [("/qr", False), ("/qr?token=salah", False), ("/qr?token=rahasia", True)]:
        handler.path = path
        got = wb.BotHTTPHandler._qr_allowed(handler)
        ok = got == expected
        results.append((f"qr {path} (token={wb.QR_TOKEN!r})", ok, "OK" if ok else f"harus {expected}, ternyata {got}"))
    handler._is_connected = lambda: True
    handler.path = "/qr?token=rahasia"
    got = wb.BotHTTPHandler._qr_allowed(handler)
    results.append(("qr ditolak setelah login", got is False, "OK" if got is False else "harus False"))

    # --- Keamanan endpoint /pair (pakai proteksi token yang sama) ---
    handler._is_connected = lambda: False
    for path, expected in [("/pair", False), ("/pair?phone=628123&token=salah", False), ("/pair?phone=628123&token=rahasia", True)]:
        handler.path = path
        got = wb.BotHTTPHandler._qr_allowed(handler)
        ok = got == expected
        results.append((f"pair {path}", ok, "OK" if ok else f"harus {expected}, ternyata {got}"))

    # --- Laporan hasil ---
    print("=" * 60)
    print("HASIL TES OFFLINE BOT WHATSAPP")
    print("=" * 60)
    failed = 0
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {name}")
        if not ok:
            print(f"         -> {detail}")
    print("=" * 60)
    total = len(results)
    print(f"Total: {total} | Lulus: {total - failed} | Gagal: {failed}")
    if failed:
        print("ADA YANG GAGAL — periksa detail di atas.")
    else:
        print("SEMUA TES LULUS! 🎉")

    # Bersihkan database test (data uji tidak ikut ke database asli).
    try:
        database.SessionLocal.remove()
    except Exception:
        pass
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(TEST_DB + suffix):
            os.remove(TEST_DB + suffix)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
