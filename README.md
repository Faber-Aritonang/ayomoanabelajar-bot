# 🌟 Ayo, Moana Belajar! - Telegram & WhatsApp AI Tutor

![Version](https://img.shields.io/badge/version-v1.4.6-blue.svg)
![Python](https://img.shields.io/badge/python-3.14-green.svg)
![Platform](https://img.shields.io/badge/platform-Telegram%20%26%20WhatsApp-success.svg)

Bot edukatif berbasis AI yang dirancang untuk menjadi pendamping belajar anak SD yang interaktif, adaptif, dan terukur. Proyek ini dibangun dengan mengedepankan efisiensi alur belajar dan pencatatan data kemajuan siswa secara *real-time*. Tersedia di **dua platform**: **Telegram** dan **WhatsApp** — keduanya berbagi materi, prompt guru, dan database riwayat belajar yang sama.

## ✨ Fitur Utama Saat Ini (v1.4.5)

- 🔒 **Whitelist Akses Bot**: Opsional — saat diaktifkan, hanya nomor/user yang terdaftar yang bisa memakai bot (nomor lain ditolak dengan pesan ramah). Daftar dikelola via env var + perintah admin langsung dari chat, tanpa perlu deploy ulang.
- 🔥 **Streak Belajar Harian**: Bot mencatat hari belajar berturut-turut anak dan menampilkannya lewat `/streak` (Telegram) atau `streak` (WhatsApp) dengan pesan penyemangat — memotivasi anak untuk belajar setiap hari.
- ⏰ **Pengingat Belajar Otomatis**: Setiap hari pada jam yang bisa diatur (default **16:00 WIB**, env `REMINDER_HOUR`), bot mengirim pengingat ramah ke anak yang aktif tapi belum belajar hari itu — maksimal 1× sehari, anti-spam.
- 🎤 **Mode Suara (Telegram & WhatsApp)**: Anak bisa bertanya dengan **pesan suara** (voice note) — bot mentranskripsi otomatis (Groq Whisper, Bahasa Indonesia) lalu menjawab seperti pesan teks. Ideal untuk anak SD yang lebih nyaman bicara daripada mengetik.
- 🤖 **AI Chat Tutor**: Pendamping belajar interaktif dengan *prompt* khusus untuk berbagai mata pelajaran (Matematika, Bahasa Indonesia, Bahasa Inggris, IPAS, Pancasila, Agama Kristen).
- 📈 **Kuis Adaptif Berpoin (Smart Evaluation)**: Sistem evaluasi cerdas yang membaca riwayat obrolan siswa untuk menyesuaikan tingkat kesulitan soal secara otomatis. Setiap jawaban benar **+10 poin**, salah **0 poin**; skor tiap sesi tersimpan di database untuk dipantau orang tua.
- ⭐ **Sistem Gamifikasi**: Perintah `/bintang` (Telegram) atau `bintang` (WhatsApp) untuk memberikan *reward* visual berdasarkan tingkat keaktifan guna memotivasi konsistensi belajar anak.
- 📊 **Laporan Kemajuan Terstruktur**: Fitur `/laporan` (Telegram) atau `laporan` (WhatsApp) menggunakan integrasi ORM untuk menyajikan rekapitulasi data aktivitas belajar secara instan bagi pemantauan orang tua.
- 📑 **Rapor AI Naratif**: Fitur `/rapor` (Telegram) atau `rapor` (WhatsApp) yang membaca seluruh riwayat percakapan anak lintas pelajaran untuk menyusun evaluasi komprehensif yang spesifik bagi orang tua.
- 🗂️ **Dasbor Navigasi**: Fitur `/menu` untuk memandu pengguna mengakses dan menggunakan seluruh kemampuan interaktif bot dengan mudah.

## 🔒 Mengaktifkan Whitelist

Fitur ini **nonaktif secara default** (semua orang bisa pakai bot). Untuk mengaktifkan:

1. Set env var di `.env` / dashboard Render:
   - `BOT_WHITELIST_ENABLED=1`
   - `BOT_ADMIN_WHATSAPP=<nomormu>` dan/atau `BOT_ADMIN_TELEGRAM=<user_id Telegrammu>` (cari user_id via @userinfobot)
   - Opsional, daftar awal: `WA_WHITELIST=628xxx,628yyy` dan `TG_WHITELIST=123,456`
2. Restart/deploy. Admin otomatis selalu dilayani dan bisa mengelola daftar langsung dari chat:
   - **WhatsApp** (kirim ke bot): `tambah 0812xxxx` / `hapus 0812xxxx` / `daftar`
   - **Telegram**: `/tambah 123456789` / `/hapus 123456789` / `/daftar`

> Nomor di luar daftar akan mendapat balasan ramah dan tidak dilayani. Pengingat harian juga hanya dikirim ke pengguna terdaftar.

## 🛠️ Teknologi & Arsitektur Sistem

- **Bahasa**: Python 3.14 (dipin **g** lewat `.python-version`)

- **Database**: Integrasi *seamless* antara SQLite (Lokal) & PostgreSQL (**Neon** cloud) menggunakan **SQLAlchemy ORM** — data tersimpan permanen, tidak hilang saat redeploy.
- **Framework Telegram**: `python-telegram-bot` v22
- **Framework WhatsApp**: `Neonize` (wrapper Python untuk `whatsmeow`)
- **AI**: Anthropic Claude (Haiku 4.5)
- **Infrastruktur**: Render (Webhook Deployment)

## 💬 Bot WhatsApp

Bot WhatsApp tersedia di file **`whatsapp_bot.py`**, berbagi `llm.py`, `subjects.py`, dan `database.py` dengan bot Telegram.

> ⚠️ **Catatan penting**: Bot WhatsApp memakai library tidak resmi (Neonize) yang mengemulasi klien WhatsApp Web. Ini **melanggar Ketentuan Layanan WhatsApp** — nomor HP yang dipakai berisiko diblokir kapan saja. Gunakan nomor yang tidak penting dan hindari pengiriman massal. Baca lengkap di [WHATSAPP.md](WHATSAPP.md).

### Perintah di WhatsApp (tidak ada tombol, semua lewat teks)

| Perintah | Fungsi |
|---|---|
| `menu` / `mulai` | Daftar pelajaran — ketik angkanya (1–6) untuk memilih |
| `1` … `6` | Pilih pelajaran |
| *(teks bebas)* | Chat/bertanya ke Kak Moana |
| 🎤 *(voice note)* | Tanya dengan suara — ditranskripsi otomatis (Groq Whisper) |
| `kuis` / `soal` | Kuis adaptif pelajaran aktif |
| `bintang` | Lihat koleksi bintang ⭐ |
| `streak` / `semangat` | Lihat streak belajar harian 🔥 |
| `tambah <nomor>` / `hapus <nomor>` / `daftar` | *(Admin)* Kelola whitelist langsung dari chat |
| `laporan` | Rekap keaktifan belajar (untuk orang tua) |
| `rapor` | Rapor evaluasi AI mingguan (untuk orang tua) |
| `reset` | Mulai obrolan baru |
| `help` / `bantuan` | Bantuan |

### Menjalankan bot WhatsApp

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 whatsapp_bot.py
```

Login pertama kali: scan QR dari `http://localhost:10000/qr` (atau Pairing Code di log). Sesi tersimpan di `wa_session.db` — restart tidak perlu scan ulang.

### Menguji bot WhatsApp tanpa HP

```bash
python3 test_whatsapp_bot.py
```

Skrip ini mensimulasikan 40+ skenario pesan masuk (menu, pilih pelajaran, chat, kuis adaptif dengan evaluasi jawaban benar/salah, bintang, laporan, rapor, reset, keamanan `/qr`, dll.) tanpa memerlukan koneksi WhatsApp atau biaya API. Pakai database uji terpisah, jadi data asli tidak tersentuh.

## 📝 Riwayat Pembaruan (Changelog)

- **[v1.4.6] - Pembaruan Terkini**
  - **Database permanen (Neon Postgres)**: `DATABASE_URL` kini dipakai kedua bot via **Neon** (free tier, cloud) — riwayat chat, streak, bintang, dan skor kuis **tidak hilang lagi** saat redeploy/restart (sebelumnya tersimpan di SQLite filesystem Render yang sementara).
  - **Fix crash di Python 3.14**: ganti driver `psycopg2-binary` (tidak kompatibel dengan Python 3.14) ke **`psycopg[binary]` v3**; `database.py` otomatis memakai `postgresql+psycopg://`.
  - **Versi Python eksplisit**: `runtime.txt` dihapus (tidak lagi didukung Render) → diganti **`.python-version`** (`3.14.3`).
- **[v1.4.5]**
  - **Whitelist Akses Bot**: `whitelist.py` (logika bersama) + tabel `whitelist` di database. Aktifkan dengan `BOT_WHITELIST_ENABLED=1`; daftar tetap via `WA_WHITELIST`/`TG_WHITELIST`, daftar dinamis via perintah admin (`tambah`/`hapus`/`daftar` di WhatsApp, `/tambah`/`/hapus`/`/daftar` di Telegram). Nomor tidak terdaftar ditolak dengan pesan ramah.
- **[v1.4.4]**
  - **Streak Belajar Harian**: hari belajar berturut-turut dihitung dari riwayat database, ditampilkan via `/streak` (Telegram) / `streak` (WhatsApp).
  - **Pengingat Belajar Otomatis**: `reminders.py` (logika bersama) + JobQueue di Telegram & thread di WhatsApp. Kirim pengingat ke anak aktif yang belum belajar hari ini, 1×/hari (jam diatur `REMINDER_HOUR`, default 16).
- **[v1.4.3]**
  - **Mode Suara untuk WhatsApp**: kirim voice note di WhatsApp, bot transkripsikan lewat **Groq Whisper** (sama seperti Telegram) lalu jawab seperti pesan teks. Deteksi voice note via protobuf `audioMessage` (PTT) + `client.download_any`; file audio biasa (lagu) ditolak dengan pesan ramah.
- **[v1.4.2]**
  - **Mode Suara untuk Telegram**: kirim voice note, bot transkripsikan lewat **Groq Whisper** (gratis, Bahasa Indonesia) lalu jawab seperti pesan teks. `stt.py` dipakai bersama; `GROQ_API_KEY` di `.env` / env vars Render.
- **[v1.4.1]**
  - **Kuis Adaptif Berpoin**: jawaban kuis kini dievaluasi otomatis (benar **+10 poin**, salah **0 poin**), skor disimpan ke `quiz_scores`, dan kunci jawaban disembunyikan dari anak (logika bersama di `quiz.py` untuk Telegram & WhatsApp).
  - Menghapus handler `/menu` ganda di `telegram_bot.py`.
  - Menyamakan versi Python (`runtime.txt` → 3.12) dan menghapus file lama `bot_database.db`.
  - **Stabilisasi deploy**: keep-alive self-ping di `whatsapp_bot.py` agar service Render free tier tidak tertidur (idle 15 menit).
- **[v1.4.0]**
  - Merilis **Bot WhatsApp** (`whatsapp_bot.py`) dengan fitur yang sama dengan Telegram.
  - Menambahkan skrip pengujian otomatis `test_whatsapp_bot.py`.
  - Dokumentasi deploy WhatsApp ke Render (`WHATSAPP.md`).
- **[v1.3.0]**
  - Merilis fitur `/rapor` untuk evaluasi mingguan naratif menggunakan AI.
  - Menambahkan dasbor `/menu` sebagai pusat kendali navigasi pengguna.
- **[v1.2.0]**
  - Mengubah logika `/kuis` menjadi Sistem Evaluasi Adaptif berbasis riwayat obrolan.
  - Merilis fitur `/bintang` (Gamifikasi Keaktifan).
  - Menyempurnakan penyimpanan konteks memori pada kuis.
- **[v1.1.0]**
  - Implementasi *database relasional* dengan SQLAlchemy.
  - Merilis fitur `/laporan` untuk memantau metrik interaksi siswa.
- **[v1.0.0]**
  - Rilis awal arsitektur dasar chatbot AI dan integrasi menu mata pelajaran.
