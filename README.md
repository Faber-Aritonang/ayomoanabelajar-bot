# 🌟 Ayo, Moana Belajar! - Telegram & WhatsApp AI Tutor

![Version](https://img.shields.io/badge/version-v1.4.6-blue.svg)
![Python](https://img.shields.io/badge/python-3.14-green.svg)
![Platform](https://img.shields.io/badge/platform-Telegram%20%26%20WhatsApp-success.svg)

Bot edukatif berbasis AI untuk mendampingi belajar anak SD kelas 3. Anak memilih mata pelajaran, bertanya lewat teks atau voice note, lalu berlatih dengan kuis adaptif. Tersedia di **Telegram** dan **WhatsApp** — keduanya berbagi materi, prompt guru, dan database riwayat belajar yang sama.

## ✨ Fitur Utama (v1.4.6)

- 🤖 **AI Chat Tutor**: Pendamping belajar dengan prompt khusus per mata pelajaran, dibimbing langkah demi langkah (bukan langsung memberi jawaban PR).
- 📈 **Kuis Adaptif Berpoin**: 5 soal pilihan ganda per sesi. Tingkat kesulitan menyesuaikan riwayat obrolan; jawaban benar **+10 poin**, salah **0 poin**. Kunci jawaban tidak pernah ditampilkan ke anak, dan skor tersimpan di database.
- ⭐ **Gamifikasi Bintang**: `/bintang` (Telegram) atau `bintang` (WhatsApp) menampilkan koleksi bintang — 1 bintang untuk setiap 5 interaksi belajar.
- 🔥 **Streak Belajar Harian**: Hari belajar berturut-turut dihitung dari riwayat database dan ditampilkan lewat `/streak` / `streak`.
- 🎤 **Mode Suara (dua arah)**: Voice note ditranskripsi otomatis dengan **Groq Whisper** (Bahasa Indonesia, maksimal 2 menit), lalu dijawab seperti pesan teks. Balasan percakapan juga dikirim sebagai voice note.
  - Telegram: pilih suara lewat `/suara`, `/suara perempuan` (`id-ID-GadisNeural`), atau `/suara laki-laki` (`id-ID-ArdiNeural`). Pilihan disimpan per pengguna di database.
  - WhatsApp: suara tetap perempuan `id-ID-GadisNeural`; pilihan suara belum tersedia.
  - TTS memakai **Edge TTS** tanpa API key, dengan **gTTS** sebagai cadangan. Keduanya butuh internet; jika audio gagal, balasan teks tetap dikirim.
  - Notasi matematika umum (pecahan, akar, pangkat, operasi hitung, kurung) dibacakan dengan kata-kata khusus untuk suara. Teks balasan tidak diubah.
- 📊 **Laporan Kemajuan**: `/laporan` / `laporan` menampilkan jumlah interaksi per pelajaran dan rekap skor kuis untuk orang tua.
- 📑 **Rapor AI Naratif**: `/rapor` / `rapor` menganalisis 20 interaksi terakhir lintas pelajaran dan menyusun evaluasi untuk orang tua.
- 🗂️ **Menu Navigasi**: `/menu` (Telegram) atau `menu` (WhatsApp) untuk memilih pelajaran dan melihat perintah.
- 🔒 **Whitelist Akses**: Opsional. Saat aktif, hanya pengguna terdaftar yang dilayani; daftar bisa dikelola admin langsung dari chat tanpa deploy ulang.
- ⏰ **Pengingat Belajar**: Dalam jendela jam tertentu (default 16:00–21:00 waktu server), anak yang aktif 7 hari terakhir tapi belum belajar hari itu menerima satu pengingat. Maksimal 1× sehari, dan hanya untuk pengguna yang lolos whitelist.

## 📚 Mata Pelajaran

Matematika, Bahasa Indonesia, Bahasa Inggris, IPAS, Pendidikan Pancasila, dan Pendidikan Agama Kristen — masing-masing dengan prompt guru di `subjects.py`. Materi buku cetak opsional dibaca dari `materials/<pelajaran>.md` (lokal) atau `/etc/secrets/<pelajaran>.md` (Render Secret Files); file materi tidak ikut di-commit karena alasan hak cipta.

## 💬 Perintah Telegram

| Perintah | Fungsi |
|---|---|
| `/start` | Mulai dari awal dan pilih pelajaran lewat tombol |
| `/menu` | Dasbor navigasi dan ganti pelajaran |
| `/kuis` | Mulai kuis adaptif pelajaran aktif |
| `/bintang` | Lihat koleksi bintang ⭐ |
| `/streak` | Lihat streak belajar harian 🔥 |
| `/laporan` | Rekap keaktifan dan skor kuis (orang tua) |
| `/rapor` | Rapor evaluasi AI (orang tua) |
| `/suara perempuan` / `/suara laki-laki` | Pilih suara balasan |
| `/reset` | Mulai obrolan baru (riwayat tetap tersimpan) |
| `/help` | Bantuan |
| `/tambah`, `/hapus`, `/daftar` | *(Admin)* Kelola whitelist |
| 🎤 *(voice note)* | Tanya dengan suara — ditranskripsi otomatis |

## 💬 Perintah WhatsApp

WhatsApp tidak punya tombol inline, jadi semua perintah diketik.

| Perintah | Fungsi |
|---|---|
| `menu` / `mulai` / `ganti` | Daftar pelajaran — ketik angkanya (1–6) untuk memilih |
| `1` … `6` | Pilih pelajaran |
| *(teks bebas)* | Chat/bertanya ke Kak Moana |
| 🎤 *(voice note)* | Tanya dengan suara — ditranskripsi otomatis (Groq Whisper) |
| `kuis` / `soal` / `latihan` | Kuis adaptif pelajaran aktif |
| `bintang` | Lihat koleksi bintang ⭐ |
| `streak` / `semangat` | Lihat streak belajar harian 🔥 |
| `laporan` | Rekap keaktifan belajar (orang tua) |
| `rapor` | Rapor evaluasi AI (orang tua) |
| `reset` | Mulai obrolan baru |
| `help` / `bantuan` | Bantuan |
| `tambah <nomor>` / `hapus <nomor>` / `daftar` | *(Admin)* Kelola whitelist |

## 🔒 Whitelist Akses

Nonaktif secara default (semua orang bisa memakai bot). Untuk mengaktifkan:

1. Set env var di `.env` / dashboard Render:
   - `BOT_WHITELIST_ENABLED=1`
   - `BOT_ADMIN_WHATSAPP=<nomormu>` dan/atau `BOT_ADMIN_TELEGRAM=<user_id Telegrammu>` (cari user_id via @userinfobot)
   - Opsional, daftar awal: `WA_WHITELIST=628xxx,628yyy` dan `TG_WHITELIST=123,456`
2. Restart/deploy. Admin selalu dilayani dan bisa mengelola daftar dari chat:
   - **WhatsApp**: `tambah 0812xxxx` / `hapus 0812xxxx` / `daftar`
   - **Telegram**: `/tambah 123456789` / `/hapus 123456789` / `/daftar`

> Nomor/user di luar daftar mendapat balasan ramah dan tidak dilayani. Pengingat harian juga tidak dikirim ke mereka.

## 🛠️ Teknologi

- **Bahasa**: Python 3.14 (dipin lewat `.python-version`)
- **Database**: SQLite (lokal) atau PostgreSQL/Neon (cloud) via **SQLAlchemy 2** dan driver **psycopg v3** (`psycopg[binary]`); `database.py` otomatis menyesuaikan skema URL Postgres
- **Framework Telegram**: `python-telegram-bot` v22 (webhook di Render, polling di lokal)
- **Framework WhatsApp**: `Neonize` (wrapper Python untuk `whatsmeow`)
- **AI**: Anthropic Claude Haiku 4.5
- **STT**: Groq Whisper (`whisper-large-v3-turbo`)
- **TTS**: Edge TTS + gTTS
- **Infrastruktur**: Render (Blueprint tersedia di `render.yaml`)

## 📁 Struktur Berkas

| Berkas | Isi |
|---|---|
| `telegram_bot.py` | Bot Telegram: handler, tombol, webhook/polling, health check |
| `whatsapp_bot.py` | Bot WhatsApp: handler Neonize, QR/pairing, keep-alive, health check |
| `llm.py` | Wrapper Anthropic Claude + pemuatan materi |
| `subjects.py` | Prompt guru untuk 6 mata pelajaran |
| `database.py` | Model & query SQLAlchemy (riwayat, skor, whitelist, suara) |
| `quiz.py` | Logika kuis adaptif bersama |
| `stt.py` | Transkripsi voice note via Groq |
| `tts.py` | Text-to-speech + pelafalan matematika |
| `whitelist.py` | Logika whitelist bersama |
| `reminders.py` | Logika pengingat belajar bersama |
| `test_whatsapp_bot.py` | Simulasi offline bot WhatsApp |
| `test_telegram_voice.py` | Unit test suara, database, dan log Telegram |

## 🚀 Menjalankan Lokal

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # lalu isi token & API key
```

Lalu jalankan salah satu (atau keduanya di terminal terpisah):

```bash
python3 telegram_bot.py
python3 whatsapp_bot.py
```

### Bot WhatsApp

Login pertama kali: scan QR dari `http://localhost:10000/qr` (atau buka dari HP di jaringan yang sama), atau gunakan Pairing Code yang tampil di log. Sesi tersimpan di `wa_session.db`, jadi restart tidak perlu scan ulang selama file itu ada. Cek status koneksi di `http://localhost:10000/status`.

> ⚠️ Bot WhatsApp memakai library tidak resmi (Neonize) yang mengemulasi klien WhatsApp Web. Ini **melanggar Ketentuan Layanan WhatsApp** — nomor yang dipakai berisiko diblokir. Gunakan nomor yang tidak penting dan hindari pengiriman massal. Detail: [WHATSAPP.md](WHATSAPP.md).

## ⚙️ Variabel Environment

| Variabel | Wajib | Keterangan |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram | Token dari @BotFather |
| `ANTHROPIC_API_KEY` | Ya | Kunci API Claude |
| `GROQ_API_KEY` | Mode suara | Transkripsi voice note (gratis di console.groq.com) |
| `DATABASE_URL` | Disarankan | Postgres/Neon; tanpa ini memakai `chatbot.db` SQLite lokal |
| `RENDER_EXTERNAL_URL` | Render | Diisi otomatis; dipakai webhook Telegram dan keep-alive WhatsApp |
| `PORT` | Render | Diisi otomatis; HTTP server WhatsApp & health check |
| `WA_SESSION_DB` | — | Default `wa_session.db` |
| `WA_QR_TOKEN` | Disarankan saat publik | Melindungi halaman `/qr` dan `/pair` |
| `BOT_WHITELIST_ENABLED` | — | `1` untuk mengaktifkan whitelist |
| `BOT_ADMIN_WHATSAPP`, `BOT_ADMIN_TELEGRAM` | — | Admin whitelist |
| `WA_WHITELIST`, `TG_WHITELIST` | — | Daftar awal (dipisah koma) |
| `REMINDER_ENABLED` | — | `0` untuk mematikan pengingat |
| `REMINDER_HOUR`, `REMINDER_MAX_HOUR` | — | Jendela pengiriman; default `16`–`21` **waktu server** |
| `REMINDER_ACTIVE_DAYS` | — | Default 7 hari |

> ℹ️ **Zona waktu pengingat**: server Render umumnya UTC. Untuk pengingat pukul 16:00 WIB, set `REMINDER_HOUR=9` (16:00 WIB = 09:00 UTC). Default `16` berarti pukul 16:00 UTC bila tidak diubah.

## ☁️ Deploy ke Render

1. Push repo ke GitHub, lalu di Render pilih **New > Blueprint** dan hubungkan repo (`render.yaml` sudah berisi dua service: Telegram dan WhatsApp).
2. Isi env var rahasia di dashboard: `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `WA_QR_TOKEN`.
3. Untuk bot WhatsApp, buka `https://<service>.onrender.com/qr?token=<WA_QR_TOKEN>` lalu scan. Setelah login berhasil, `/qr` otomatis ditolak.
4. Versi Python mengikuti `.python-version` (`3.14.3`). Database Neon membuat riwayat, streak, bintang, dan skor kuis tetap ada setelah redeploy.

Catatan free tier: filesystem tidak persisten, sehingga `wa_session.db` bisa hilang saat redeploy/restart dan perlu scan ulang. Bot WhatsApp mem-ping `/health` sendiri tiap 10 menit lewat `RENDER_EXTERNAL_URL` agar service tidak tertidur; UptimeRobot ke `/health` bisa dipakai sebagai lapisan tambahan.

## 🧪 Tes Offline

```bash
python3 test_whatsapp_bot.py      # 54 skenario, 89 pemeriksaan
python3 test_telegram_voice.py    # 6 unit test
```

`test_whatsapp_bot.py` menyimulasikan pesan masuk (menu, pilih pelajaran, chat, kuis benar/salah, bintang, streak, laporan, rapor, voice note, whitelist, QR/pairing, pengingat) tanpa koneksi WhatsApp atau biaya API. Kedua tes memakai database terpisah dan tidak menyentuh data asli.

## 📝 Changelog

- **[v1.4.6]**
  - **Database permanen (Neon Postgres)**: `DATABASE_URL` dipakai kedua bot, sehingga riwayat chat, streak, bintang, dan skor kuis tidak hilang saat redeploy.
  - **Dukungan Python 3.14**: driver diganti ke `psycopg[binary]` v3; `database.py` otomatis memakai `postgresql+psycopg://`.
  - **Versi Python eksplisit**: `.python-version` (`3.14.3`) menggantikan `runtime.txt` yang tidak lagi didukung Render.
- **[v1.4.5]**
  - **Whitelist akses**: tabel `whitelist` + perintah admin dari chat; pengguna di luar daftar ditolak dengan pesan ramah.
- **[v1.4.4]**
  - **Streak belajar harian** dan **pengingat otomatis** (maksimal 1× sehari, jendela jam bisa diatur).
- **[v1.4.3]**
  - **Mode suara WhatsApp**: voice note ditranskripsi Groq Whisper lalu dijawab sebagai teks dan voice note.
- **[v1.4.2]**
  - **Mode suara Telegram**: voice note ditranskripsi lewat Groq Whisper.
- **[v1.4.1]**
  - **Kuis adaptif berpoin**: evaluasi jawaban otomatis (+10/0), skor tersimpan, kunci jawaban disembunyikan.
  - Keep-alive self-ping agar service Render free tier tidak tertidur.
- **[v1.4.0]**
  - Rilis bot WhatsApp dengan fitur setara Telegram, plus skrip tes offline.

> Rilis lama (v1.0–v1.3) tersedia di riwayat commit GitHub.
