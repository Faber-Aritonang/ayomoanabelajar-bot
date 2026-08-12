"""
whatsapp_bot.py
================
Bot WhatsApp "Ayo, Moana Belajar!" — versi WhatsApp dari telegram_bot.py.

Dibangun di atas **Neonize** (wrapper Python untuk library Go "whatsmeow").
Ini adalah library TIDAK RESMI yang mengemulasi klien WhatsApp Web, jadi:

  ⚠️ Melanggar Ketentuan Layanan WhatsApp — nomor HP yang dipakai berisiko
     diblokir/di-ban kapan saja oleh Meta. Gunakan nomor yang tidak penting,
     dan jangan untuk spam/broadcast massal (itu memperbesar risiko ban).

Cara pakai (lokal):
    source venv/bin/activate
    pip install -r requirements.txt
    python3 whatsapp_bot.py

    Lalu scan QR yang muncul di terminal, atau buka http://localhost:10000/qr
    dari HP (satu jaringan yang sama) dan scan dari sana.
    Alternatif: buka WhatsApp > Perangkat Tertaut > Hubungkan dengan Nomor
    Telepon, lalu masukkan Pairing Code yang tampil di terminal/QR page.

Perintah yang dikenali (WhatsApp tidak punya tombol, semua lewat teks):
    menu / mulai            -> daftar pelajaran (ketik angkanya untuk memilih)
    kuis / soal             -> kuis adaptif pelajaran aktif
    bintang                 -> koleksi bintang keaktifan
    laporan                 -> laporan kemajuan (untuk orang tua)
    rapor                   -> rapor evaluasi AI mingguan (untuk orang tua)
    help / bantuan          -> bantuan
    reset                   -> mulai obrolan baru
"""

import json
import logging
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

from dotenv import load_dotenv

import database
import quiz
from llm import get_ai_reply
from subjects import get_subject, list_subjects

load_dotenv()

from neonize import NewClient
from neonize.proto.Neonize_pb2 import Message as MessageEv
from neonize.utils import JIDToNonAD

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_NAME = "Ayo, Moana Belajar!"
HISTORY_LIMIT = 10  # jumlah pesan terakhir yang dikirim sebagai konteks ke LLM
SESSION_DB = os.getenv("WA_SESSION_DB", "wa_session.db")
PORT = int(os.getenv("PORT", "10000"))

# State per pengguna (nomor telepon -> data). Riwayat chat tetap di database;
# dict ini hanya menyimpan pelajaran aktif & penanda reset, seperti user_data
# di python-telegram-bot.
_user_states: dict[str, dict] = {}
_states_lock = threading.Lock()

# QR terbaru (PNG) untuk ditampilkan lewat web, diisi oleh callback QR.
_latest_qr_png: bytes | None = None
_current_client: NewClient | None = None

# Token opsional untuk melindungi halaman /qr. Kalau diisi, /qr hanya bisa
# dibuka dengan ?token=<nilai>. Berguna kalau bot di-deploy di URL publik
# (Render) supaya orang lain tidak bisa scan QR dan membajak sesi WhatsApp.
QR_TOKEN = os.getenv("WA_QR_TOKEN", "").strip()

# Keep-alive: Render free tier mematikan service setelah ~15 menit tanpa
# request masuk, yang memutus koneksi WhatsApp. Thread ini mem-ping URL
# publik service sendiri (/health) tiap 10 menit supaya service tetap hidup.
# RENDER_EXTERNAL_URL diisi otomatis oleh Render; kosong saat jalan lokal.
KEEP_ALIVE_INTERVAL = 600  # detik
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")


# --------------------------------------------------------------------------
# Helper kecil
# --------------------------------------------------------------------------

def _state(phone: str) -> dict:
    with _states_lock:
        return _user_states.setdefault(phone, {})


def _subject_menu_text() -> str:
    """Daftar pelajaran bernomor, karena WhatsApp tidak punya tombol."""
    lines = [f"🎓 *{BOT_NAME}* 🎓", "", "Halo, Adik! 👋 Aku Kak Moana, teman belajar kelas 3 SD. 😊", ""]
    lines.append("Ketik *angka* di bawah ini untuk memilih pelajaran:")
    lines.append("")
    for i, (key, data) in enumerate(list_subjects(), start=1):
        lines.append(f"{i}. {data['emoji']} {data['name']}")
    lines.append("")
    lines.append("Contoh: ketik *1* untuk Matematika.")
    lines.append("Atau ketik *menu* kapan saja untuk kembali ke sini.")
    return "\n".join(lines)


def parse_command(text: str, subject_active: bool = False):
    """Ubah teks WhatsApp menjadi (jenis perintah, nilai).

    WhatsApp tidak mengenal slash command, jadi kita kenali kata-kata kunci
    Bahasa Indonesia. Nomor 1..N hanya dipakai untuk memilih pelajaran kalau
    belum ada pelajaran yang aktif — supaya jawaban kuis berupa angka (mis.
    "1" saat menjawab soal pilihan ganda) tidak ikut mengubah pelajaran.
    """
    t = (text or "").strip().lower().replace("/", "")

    keywords = {
        "start": ("start", None),
        "mulai": ("start", None),
        "menu": ("menu", None),
        "ganti": ("menu", None),
        "kuis": ("kuis", None),
        "soal": ("kuis", None),
        "latihan": ("kuis", None),
        "bintang": ("bintang", None),
        "laporan": ("laporan", None),
        "rapor": ("rapor", None),
        "help": ("help", None),
        "bantuan": ("help", None),
        "reset": ("reset", None),
    }
    if t in keywords:
        return keywords[t]

    # Angka = pilih pelajaran, tapi hanya saat belum ada pelajaran aktif.
    if not subject_active and t.isdigit():
        n = int(t)
        if 1 <= n <= len(list_subjects()):
            return ("pilih_subject", n)

    return ("chat", text)


def _phone_of(ev: MessageEv) -> str:
    """Nomor pengirim yang stabil (bukan LID), dipakai sebagai user_id."""
    sender = ev.Info.MessageSource.Sender
    try:
        jid = JIDToNonAD(sender)
    except Exception:
        jid = sender
    return jid.User


# --------------------------------------------------------------------------
# Fitur utama (dipindah-pakai dari telegram_bot.py, disesuaikan teks-only)
# --------------------------------------------------------------------------

def _send(client: NewClient, ev: MessageEv, text: str):
    """Kirim balasan ke chat asal pesan, aman dari kegagalan jaringan."""
    try:
        client.send_message(ev.Info.MessageSource.Chat, text)
    except Exception as e:
        logger.error("Gagal mengirim pesan: %s", e)


def handle_start(client, ev, phone):
    _state(phone).pop("subject", None)
    _state(phone).pop("quiz", None)  # keluar dari kuis yang sedang berjalan
    _send(client, ev, _subject_menu_text())


def handle_menu(client, ev, phone):
    _send(client, ev, _subject_menu_text())


def handle_help(client, ev, phone):
    text = (
        "*Perintah yang bisa dipakai:*\n"
        "• menu / mulai - pilih pelajaran\n"
        "• kuis / soal - latihan soal adaptif\n"
        "• bintang - lihat koleksi bintangmu ⭐\n"
        "• laporan - rekap keaktifan (untuk orang tua)\n"
        "• rapor - evaluasi AI mingguan (untuk orang tua)\n"
        "• reset - mulai obrolan baru\n\n"
        "Setelah pilih pelajaran, langsung ketik pertanyaanmu ya! 😊"
    )
    _send(client, ev, text)


def handle_reset(client, ev, phone):
    st = _state(phone)
    subject_key = st.get("subject")
    if not subject_key:
        _send(client, ev, "Belum ada pelajaran yang dipilih. Ketik *menu* dulu ya!")
        return
    st["reset_marker"] = True
    st.pop("quiz", None)  # keluar dari kuis yang sedang berjalan
    subject_name = get_subject(subject_key)["name"]
    _send(client, ev, f"Oke, obrolan {subject_name} kita mulai dari awal lagi ya! 🔄")


def handle_pick_subject(client, ev, phone, number):
    subjects = list_subjects()
    key, data = subjects[number - 1]
    st = _state(phone)
    st["subject"] = key
    st["reset_marker"] = True  # mulai konteks segar tiap ganti pelajaran
    st.pop("quiz", None)  # pelajaran baru = kuis baru
    _send(
        client,
        ev,
        f"{data['emoji']} Oke! Sekarang kita belajar *{data['name']}* ya.\n"
        "Langsung tanya apa saja seputar pelajaran ini, atau ketik *kuis* "
        "untuk latihan soal!",
    )


def handle_chat(client, ev, phone, text):
    st = _state(phone)
    subject_key = st.get("subject")
    if not subject_key:
        _send(
            client,
            ev,
            "Pilih dulu mau belajar apa, ya, Adik!\n\n" + _subject_menu_text(),
        )
        return

    subject = get_subject(subject_key)

    # Kalau kuis sedang berjalan, pesan ini adalah JAWABAN kuis.
    if st.get("quiz"):
        handle_quiz_answer(client, ev, phone, text, subject_key, subject)
        return

    if st.pop("reset_marker", False):
        history = []
    else:
        history = database.get_recent_messages(phone, subject_key, limit=HISTORY_LIMIT)

    reply = get_ai_reply(subject_key, subject["system_prompt"], history, text)

    database.save_message(phone, phone, subject_key, "user", text)
    database.save_message(phone, phone, subject_key, "assistant", reply)

    _send(client, ev, reply)


def handle_quiz(client, ev, phone):
    st = _state(phone)
    subject_key = st.get("subject")
    if not subject_key:
        _send(client, ev, "Pilih dulu mau belajar apa ya, Adik! Ketik *menu*.")
        return

    subject = get_subject(subject_key)
    subject_name = subject["name"]

    # Mulai sesi kuis baru (skor direset).
    st.pop("quiz", None)

    history = database.get_recent_messages(phone, subject_key, limit=6)
    question_text = quiz.start_quiz(st, subject_key, subject, history)

    if not question_text:
        _send(client, ev, "Maaf, Kak Moana sedang kesulitan menyiapkan kuis saat ini. Coba lagi ya!")
        return

    database.save_message(phone, phone, subject_key, "assistant", question_text)
    _send(client, ev, f"📝 *Kuis Adaptif ({subject_name})*\n\n{question_text}")


def handle_quiz_answer(client, ev, phone, answer_text, subject_key, subject):
    """Proses jawaban anak untuk kuis yang sedang berjalan (WhatsApp)."""
    st = _state(phone)

    feedback, need_next, summary = quiz.answer_quiz(st, answer_text)

    if summary:  # sesi selesai — simpan skor ke database
        database.save_quiz_score(phone, phone, subject_key, summary["score"], summary["total"])

    database.save_message(phone, phone, subject_key, "user", answer_text)
    database.save_message(phone, phone, subject_key, "assistant", feedback)
    _send(client, ev, feedback)

    if need_next == "NEXT":
        history = database.get_recent_messages(phone, subject_key, limit=6)
        question_text = quiz.start_quiz(st, subject_key, subject, history)
        if question_text:
            database.save_message(phone, phone, subject_key, "assistant", question_text)
            _send(client, ev, f"📝 *Kuis Adaptif ({subject['name']})*\n\n{question_text}")
        else:
            _send(client, ev, "Maaf, Kak Moana sedang kesulitan menyiapkan soal berikutnya. Coba lagi ya!")


def handle_stars(client, ev, phone):
    progress = database.get_user_progress(phone)

    if not progress:
        _send(
            client,
            ev,
            "Kamu belum punya bintang, nih. Yuk mulai mengobrol dan jawab kuis "
            "dari Kak Moana untuk mengumpulkan bintang! 🌟",
        )
        return

    total_interaksi = sum(count for _, count, _ in progress)
    total_bintang = total_interaksi // 5  # 1 bintang untuk setiap 5 interaksi

    if total_bintang == 0:
        butuh = 5 - (total_interaksi % 5)
        _send(
            client,
            ev,
            f"Semangat! Kamu butuh {butuh} interaksi lagi untuk mendapatkan Bintang pertamamu! 🌟",
        )
        return

    teks_bintang = "⭐" * total_bintang
    pesan = (
        f"🎉 *Koleksi Bintang Keaktifanmu!* 🎉\n\n"
        f"Luar biasa! Kamu sudah belajar sangat rajin dan berhasil mengumpulkan:\n"
        f"{teks_bintang} ({total_bintang} Bintang)\n\n"
        "Terus semangat belajar bersama Kak Moana ya! 🚀"
    )
    _send(client, ev, pesan)


def handle_report(client, ev, phone):
    progress = database.get_user_progress(phone)

    if not progress:
        _send(
            client,
            ev,
            "Belum ada riwayat aktivitas belajar yang tercatat. Yuk, mulai belajar dengan *menu*!",
        )
        return

    text = "📊 *Laporan Kemajuan Belajar Siswa*\n\n"
    for subject, count, _ in progress:
        text += f"• *{subject.capitalize()}*: {count} interaksi obrolan/soal\n"

    quiz_rows = database.get_quiz_summary(phone)
    if quiz_rows:
        text += "\n🎯 *Skor Kuis:*\n"
        for subject, total_poin, total_soal in quiz_rows:
            text += f"• *{subject.capitalize()}*: {total_poin} poin dari {total_soal} soal\n"

    text += "\nTerus semangat mendampingi proses belajar anak! 😊"
    _send(client, ev, text)


def handle_rapor(client, ev, phone):
    _send(
        client,
        ev,
        "⏳ Mohon tunggu sebentar ya, Kak Moana sedang menganalisis data untuk menyusun Rapor Evaluasi Adik...",
    )

    recent_history = database.get_all_recent_messages(phone, limit=20)

    if len(recent_history) < 5:
        _send(
            client,
            ev,
            "Data aktivitas belajar belum cukup untuk dianalisis. Yuk, ajak Adik berlatih lebih banyak lagi bersama Kak Moana! 🚀",
        )
        return

    history_text = ""
    for msg in recent_history:
        pengirim = "Anak" if msg["role"] == "user" else "Tutor AI"
        history_text += f"[{msg['subject'].upper()}] {pengirim}: {msg['content']}\n"

    system_prompt = (
        "Kamu adalah konsultan pendidikan yang ahli memberikan umpan balik "
        "(feedback) positif dan konstruktif kepada orang tua."
    )
    user_prompt = (
        "Berikut adalah transkrip riwayat percakapan belajar seorang siswa SD "
        f"dengan tutor AI-nya baru-baru ini:\n\n{history_text}\n\n"
        "TUGAS:\n"
        "Buatkan ringkasan evaluasi (rapor naratif) maksimal 2 paragraf pendek "
        "untuk orang tua siswa.\n"
        "1. Sebutkan apa yang sudah dipahami dengan baik berdasarkan riwayat.\n"
        "2. Sebutkan konsep yang masih perlu pengulangan/perbaikan (jika ada).\n"
        "3. Berikan saran praktis dan actionable yang bisa dilakukan ayah/ibunya di rumah.\n\n"
        "Gunakan nada bicara yang profesional, hangat, dan suportif. Hindari "
        "pengantar basa-basi, langsung ke isi rapor."
    )

    try:
        rapor_text = get_ai_reply("umum", system_prompt, [], user_prompt)
        _send(client, ev, f"📑 *RAPOR EVALUASI MINGGUAN AI* 📑\n\n{rapor_text}")
    except Exception as e:
        logger.error("Error rapor: %s", e)
        _send(client, ev, "Maaf, terjadi kesalahan teknis saat menyusun rapor. Coba lagi nanti ya.")


# --------------------------------------------------------------------------
# Event handler Neonize
# --------------------------------------------------------------------------

def on_message(client: NewClient, ev: MessageEv):
    """Dipanggil untuk setiap pesan masuk. Abaikan pesan sendiri & grup."""
    try:
        if ev.Info.MessageSource.IsFromMe:
            return
        if ev.Info.MessageSource.IsGroup:
            return  # bot hanya melayani chat pribadi (anak/orang tua)

        phone = _phone_of(ev)

        # Ambil teks dari pesan biasa atau extended text (link preview, dll)
        text = ""
        if ev.Message.conversation:
            text = ev.Message.conversation
        elif ev.Message.extendedTextMessage.text:
            text = ev.Message.extendedTextMessage.text

        text = (text or "").strip()
        if not text:
            _send(client, ev, "Aku belum bisa baca itu. Ketik pertanyaanmu ya! 😊")
            return

        # Angka hanya dianggap "pilih pelajaran" saat belum ada pelajaran aktif.
        subject_active = bool(_state(phone).get("subject"))
        cmd, value = parse_command(text, subject_active=subject_active)

        if cmd == "start":
            handle_start(client, ev, phone)
        elif cmd == "menu":
            handle_menu(client, ev, phone)
        elif cmd == "help":
            handle_help(client, ev, phone)
        elif cmd == "reset":
            handle_reset(client, ev, phone)
        elif cmd == "pilih_subject":
            handle_pick_subject(client, ev, phone, value)
        elif cmd == "kuis":
            handle_quiz(client, ev, phone)
        elif cmd == "bintang":
            handle_stars(client, ev, phone)
        elif cmd == "laporan":
            handle_report(client, ev, phone)
        elif cmd == "rapor":
            handle_rapor(client, ev, phone)
        else:
            handle_chat(client, ev, phone, text)

    except Exception as e:
        logger.exception("Error memproses pesan masuk: %s", e)
        try:
            _send(client, ev, "Ups, ada yang tidak beres di sistem Kak Moana. Coba kirim pesannya lagi ya! 🙏")
        except Exception:
            pass


def on_qr(client: NewClient, data_qr: bytes):
    """Simpan QR terbaru (PNG) supaya bisa discan dari halaman /qr."""
    global _latest_qr_png
    try:
        import segno

        qr = segno.make_qr(data_qr)
        buf = BytesIO()
        qr.save(buf, kind="png", scale=4, border=2)
        _latest_qr_png = buf.getvalue()
        logger.info("QR code baru tersedia — buka /qr atau scan dari terminal.")
        # Tampilkan juga versi ASCII di log terminal (berguna saat lokal).
        qr.terminal(compact=True)
    except Exception as e:
        logger.error("Gagal membuat PNG QR: %s", e)
        _latest_qr_png = None


def on_paircode(client: NewClient, code: str, connected: bool):
    if connected:
        logger.info("Terautentikasi dengan pair code: %s", code)
    else:
        logger.info("Pairing Code (WhatsApp > Perangkat Tertaut > Hubungkan dengan Nomor Telepon): %s", code)


# --------------------------------------------------------------------------
# HTTP server kecil — syarat port Render + halaman QR + health check
# --------------------------------------------------------------------------

class BotHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # diamkan log request default
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _is_connected(self) -> bool:
        """Status koneksi sebenarnya diambil dari objek client Neonize."""
        client = _current_client
        return bool(client and client.connected)

    def _qr_allowed(self) -> bool:
        """Halaman /qr hanya boleh diakses jika sudah login atau token cocok."""
        if self._is_connected():
            return False  # sudah login, QR tidak perlu lagi & jangan diekspos
        if not QR_TOKEN:
            return True
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        import urllib.parse

        params = urllib.parse.parse_qs(query)
        return params.get("token", [""])[0] == QR_TOKEN

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/health" or path == "/":
            self._json({"status": "ok", "connected": self._is_connected()})

        elif path == "/status":
            self._json(
                {
                    "name": BOT_NAME,
                    "connected": self._is_connected(),
                    "session_db": SESSION_DB,
                    "logged_in": self._is_connected(),
                }
            )

        elif path == "/qr":
            if not self._qr_allowed():
                self._json(
                    {"error": "forbidden", "hint": "Bot sudah login, atau butuh ?token=..."},
                    status=403,
                )
                return
            if _latest_qr_png:
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(_latest_qr_png)))
                self.end_headers()
                self.wfile.write(_latest_qr_png)
            else:
                self._json(
                    {
                        "error": "QR belum tersedia",
                        "hint": "Coba muat ulang dalam beberapa detik, atau pakai Pairing Code dari log server.",
                    },
                    status=404,
                )
        else:
            self._json({"error": "not found"}, status=404)


def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), BotHTTPHandler)
    logger.info("HTTP server (QR/status) berjalan di port %s", PORT)
    server.serve_forever()


def keep_alive_loop():
    """Ping /health sendiri tiap beberapa menit agar service Render tidak tidur.

    Hanya aktif kalau RENDER_EXTERNAL_URL tersedia (dipakai di Render); saat
    jalan lokal variabel ini kosong dan loop langsung berhenti.
    """
    if not RENDER_EXTERNAL_URL:
        logger.info("Keep-alive nonaktif (RENDER_EXTERNAL_URL kosong — bukan di Render).")
        return
    logger.info("Keep-alive aktif: ping %s/health tiap %s detik.", RENDER_EXTERNAL_URL, KEEP_ALIVE_INTERVAL)
    while True:
        time.sleep(KEEP_ALIVE_INTERVAL)
        try:
            with urllib.request.urlopen(f"{RENDER_EXTERNAL_URL}/health", timeout=10) as resp:
                logger.info("Keep-alive ping -> HTTP %s", resp.status)
        except Exception as e:
            logger.warning("Keep-alive ping gagal: %s", e)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    global _current_client

    database.init_db()
    logger.info("%s (WhatsApp) sedang memulai...", BOT_NAME)

    # HTTP server jalan di thread terpisah (juga memenuhi syarat port Render).
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    # Keep-alive agar service Render free tier tidak tertidur (idle 15 menit).
    threading.Thread(target=keep_alive_loop, daemon=True).start()

    # Sesi tersimpan otomatis di SESSION_DB — restart tidak perlu scan ulang
    # (selama file DB masih ada, lihat WHATSAPP.md untuk catatan Render).
    client = NewClient(SESSION_DB)
    _current_client = client
    client.event.qr(on_qr)
    client.event.paircode(on_paircode)
    client.event(MessageEv)(on_message)

    logger.info("Menghubungkan ke WhatsApp... (scan QR atau pasang Pairing Code)")
    try:
        client.connect()
    except KeyboardInterrupt:
        logger.info("Dihentikan pengguna.")
    except Exception as e:
        logger.exception("Koneksi WhatsApp gagal: %s", e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
