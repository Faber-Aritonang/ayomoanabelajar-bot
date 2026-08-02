# Ayo, Moana Belajar! 🎓

Chatbot asisten belajar untuk anak Sekolah Dasar kelas 3 (usia ~9 tahun),
dibangun dengan Python + Anthropic Claude (Haiku 4.5). Saat ini tersedia untuk
**Telegram**; versi **WhatsApp** menyusul di iterasi berikutnya (arsitektur
sudah disiapkan agar keduanya bisa berbagi modul LLM & database yang sama).

Anak memilih mata pelajaran lewat tombol interaktif, lalu bisa mengobrol
bebas dengan "Kak Moana" — persona AI ramah yang membimbing anak berpikir
selangkah demi selangkah, bukan sekadar memberi jawaban instan.

## Mata Pelajaran

- 🔢 Matematika
- 📖 Bahasa Indonesia
- 🇬🇧 Bahasa Inggris
- 🌱 Ilmu Pengetahuan Alam & Sosial (IPAS)
- 🇮🇩 Pendidikan Pancasila
- ✝️ Pendidikan Agama Kristen

Semua materi/system prompt per mata pelajaran ada di satu file
([`subjects.py`](subjects.py)) sehingga mudah disesuaikan tanpa menyentuh
logika bot.

## Fitur

- Menu pemilihan mata pelajaran lewat inline keyboard Telegram
- Percakapan bebas (free-form chat) dengan LLM per mata pelajaran, dengan
  system prompt yang disesuaikan usia & tingkat kelas
- Bot dirancang membimbing anak berpikir (tidak langsung memberi jawaban PR)
- Riwayat percakapan tersimpan di SQLite, dipakai lagi sebagai konteks
  supaya obrolan terasa nyambung
- `/reset` untuk memulai obrolan baru tanpa kehilangan log lama
- `/menu` untuk berpindah mata pelajaran kapan saja
- Penanganan error yang tetap ramah-anak (bukan pesan error teknis mentah)

## Tech Stack

- Python 3
- [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) v22
- [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) (Claude Haiku 4.5) untuk balasan AI
- SQLite untuk penyimpanan riwayat percakapan
- `python-dotenv` untuk manajemen konfigurasi

## Struktur Proyek

```
ayomoanabelajar-bot/
├── telegram_bot.py     # entry point bot Telegram, semua handler
├── llm.py              # pembungkus panggilan ke Anthropic API
├── database.py         # penyimpanan & pengambilan riwayat percakapan (SQLite)
├── subjects.py         # daftar mata pelajaran + system prompt (EDIT DI SINI untuk ubah materi)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup & Menjalankan

```bash
git clone <url-repo-kamu>
cd ayomoanabelajar-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# lalu buka .env, isi TELEGRAM_BOT_TOKEN dan ANTHROPIC_API_KEY milikmu

python3 telegram_bot.py
```

Bot memakai *long polling*, jadi tidak perlu server publik atau tunnel
(ngrok) — cukup jalankan di komputer/server manapun yang punya akses internet.

### Mendapatkan token

- **Telegram bot token**: chat ke [@BotFather](https://t.me/BotFather) di
  Telegram, `/newbot`, ikuti instruksinya.
- **Anthropic API key**: buat di
  [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys).

## Menyesuaikan Materi Pelajaran

Buka [`subjects.py`](subjects.py). Setiap mata pelajaran punya `system_prompt`
sendiri yang bisa diubah bebas — misalnya menambah topik baru, mengganti
tingkat kesulitan, atau mengubah gaya bahasa "Kak Moana". Aturan umum yang
berlaku untuk semua mata pelajaran (nada bicara, batasan konten, dsb) ada di
variabel `_BASE_RULES` di bagian atas file yang sama.

## Rencana Selanjutnya

- [ ] Versi WhatsApp (webhook FastAPI + Meta Cloud API)
- [ ] Kuis singkat otomatis per mata pelajaran
- [ ] Laporan progres belajar sederhana untuk orang tua

## Status

Dibangun sebagai proyek portofolio. Telegram bot sudah berfungsi end-to-end
dengan Claude Haiku 4.5 sebagai LLM.
