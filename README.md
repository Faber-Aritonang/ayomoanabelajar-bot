# 🌟 Ayo, Moana Belajar! - Telegram & WhatsApp AI Tutor

![Version](https://img.shields.io/badge/version-v1.4.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-green.svg)
![Platform](https://img.shields.io/badge/platform-Telegram%20%26%20WhatsApp-success.svg)

Bot edukatif berbasis AI yang dirancang untuk menjadi pendamping belajar anak SD yang interaktif, adaptif, dan terukur. Proyek ini dibangun dengan mengedepankan efisiensi alur belajar dan pencatatan data kemajuan siswa secara *real-time*. Tersedia di **dua platform**: **Telegram** dan **WhatsApp** — keduanya berbagi materi, prompt guru, dan database riwayat belajar yang sama.

## ✨ Fitur Utama Saat Ini (v1.4.0)

- 🤖 **AI Chat Tutor**: Pendamping belajar interaktif dengan *prompt* khusus untuk berbagai mata pelajaran (Matematika, Bahasa Indonesia, Bahasa Inggris, IPAS, Pancasila, Agama Kristen).
- 📈 **Kuis Adaptif (Smart Evaluation)**: Sistem evaluasi cerdas yang membaca riwayat obrolan siswa untuk menyesuaikan tingkat kesulitan soal secara otomatis (menghindari kebosanan atau frustrasi pada anak).
- ⭐ **Sistem Gamifikasi**: Perintah `/bintang` (Telegram) atau `bintang` (WhatsApp) untuk memberikan *reward* visual berdasarkan tingkat keaktifan guna memotivasi konsistensi belajar anak.
- 📊 **Laporan Kemajuan Terstruktur**: Fitur `/laporan` (Telegram) atau `laporan` (WhatsApp) menggunakan integrasi ORM untuk menyajikan rekapitulasi data aktivitas belajar secara instan bagi pemantauan orang tua.
- 📑 **Rapor AI Naratif**: Fitur `/rapor` (Telegram) atau `rapor` (WhatsApp) yang membaca seluruh riwayat percakapan anak lintas pelajaran untuk menyusun evaluasi komprehensif yang spesifik bagi orang tua.
- 🗂️ **Dasbor Navigasi**: Fitur `/menu` untuk memandu pengguna mengakses dan menggunakan seluruh kemampuan interaktif bot dengan mudah.

## 🛠️ Teknologi & Arsitektur Sistem

- **Bahasa**: Python 3
- **Database**: Integrasi *seamless* antara SQLite (Lokal) & PostgreSQL (Cloud Render) menggunakan **SQLAlchemy ORM**.
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
| `kuis` / `soal` | Kuis adaptif pelajaran aktif |
| `bintang` | Lihat koleksi bintang ⭐ |
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

Skrip ini mensimulasikan 35+ skenario pesan masuk (menu, pilih pelajaran, chat, kuis, bintang, laporan, rapor, reset, keamanan `/qr`, dll.) tanpa memerlukan koneksi WhatsApp atau biaya API.

## 📝 Riwayat Pembaruan (Changelog)

- **[v1.4.0] - Pembaruan Terkini**
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
