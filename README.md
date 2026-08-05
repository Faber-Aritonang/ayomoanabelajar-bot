# 🌟 Ayo, Moana Belajar! - Telegram AI Tutor

![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-green.svg)

Bot Telegram edukatif berbasis AI yang dirancang untuk menjadi pendamping belajar anak SD yang interaktif, adaptif, dan terukur. Proyek ini dibangun dengan mengedepankan efisiensi alur belajar dan pencatatan data kemajuan siswa secara *real-time*.

## ✨ Fitur Utama Saat Ini (v1.2.0)

- 🤖 **AI Chat Tutor**: Pendamping belajar interaktif dengan *prompt* khusus untuk berbagai mata pelajaran (Matematika, Bahasa Indonesia, Bahasa Inggris, IPAS, Pancasila).
- 📈 **Kuis Adaptif (Smart Evaluation)**: Sistem evaluasi cerdas yang membaca riwayat obrolan siswa untuk menyesuaikan tingkat kesulitan soal secara otomatis (menghindari kebosanan atau frustrasi pada anak).
- 📊 **Laporan Kemajuan Terstruktur**: Fitur `/laporan` menggunakan integrasi ORM untuk menyajikan rekapitulasi data aktivitas belajar secara instan bagi pemantauan orang tua.
- ⭐ **Sistem Gamifikasi**: Fitur `/bintang` untuk memberikan *reward* visual berdasarkan tingkat keaktifan guna memotivasi konsistensi belajar anak.

## 🛠️ Teknologi & Arsitektur Sistem

- **Bahasa**: Python 3
- **Database**: Integrasi *seamless* antara SQLite (Lokal) & PostgreSQL (Cloud Render) menggunakan **SQLAlchemy ORM**.
- **Framework**: `python-telegram-bot`
- **Infrastruktur**: Render (Webhook Deployment)

## 📝 Riwayat Pembaruan (Changelog)

- **[v1.2.0] - Pembaruan Terkini**
  - Mengubah logika `/kuis` menjadi Sistem Evaluasi Adaptif berbasis riwayat obrolan.
  - Merilis fitur `/bintang` (Gamifikasi Keaktifan).
  - Menyempurnakan penyimpanan konteks memori pada kuis.
- **[v1.1.0]**
  - Implementasi *database relasional* dengan SQLAlchemy.
  - Merilis fitur `/laporan` untuk memantau metrik interaksi siswa.
- **[v1.0.0]**
  - Rilis awal arsitektur dasar chatbot AI dan integrasi menu mata pelajaran.
