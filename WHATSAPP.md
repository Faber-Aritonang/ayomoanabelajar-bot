# 💬 Bot WhatsApp "Ayo, Moana Belajar!"

Versi WhatsApp dari bot edukasi yang sama dengan versi Telegram. Kode berbagi
`llm.py`, `subjects.py`, dan `database.py` — jadi materi, prompt guru, dan
riwayat belajar anak **sama** untuk kedua platform.

> ⚠️ **PENTING — BACA DULU**
> Bot ini memakai **Neonize** (wrapper Python untuk library Go `whatsmeow`),
> yang **bukan API resmi WhatsApp**. Library ini mengemulasi klien WhatsApp
> Web, sehingga **melanggar Ketentuan Layanan WhatsApp/Meta**.
> **Konsekuensi: nomor HP yang dipakai bisa diblokir/di-ban kapan saja.**
> Gunakan nomor yang tidak penting, jangan untuk spam/broadcast massal, dan
> perhatikan batas kewajaran pengiriman pesan.

---

## ✨ Fitur (sama dengan Telegram)

WhatsApp tidak punya tombol inline keyboard, jadi semua perintah diketik:

| Perintah | Fungsi |
|---|---|
| `menu` atau `mulai` | Daftar pelajaran — ketik angkanya (1–6) untuk memilih |
| `1` … `6` | Pilih pelajaran (Matematika, Bahasa Indonesia, dll.) |
| *(teks bebas)* | Chat/bertanya ke Kak Moana |
| `kuis` atau `soal` | Kuis adaptif pelajaran aktif (naik/turun level sesuai kemampuan) |
| `bintang` | Lihat koleksi bintang keaktifan ⭐ |
| `laporan` | Rekap keaktifan belajar (untuk orang tua) |
| `rapor` | Rapor evaluasi AI mingguan (untuk orang tua) |
| `reset` | Mulai obrolan baru (lupakan konteks sebelumnya) |
| `help` atau `bantuan` | Bantuan |

---

## 🚀 Menjalankan (Lokal — disarankan untuk pemakaian pribadi)

```bash
source venv/bin/activate
pip install -r requirements.txt   # menginstal neonize + dependensinya
python3 whatsapp_bot.py
```

**Login pertama kali (cukup sekali):**

1. Jalankan `python3 whatsapp_bot.py`.
2. QR code tampil di terminal **dan** di halaman web `http://localhost:10000/qr`
   (buka dari HP di jaringan yang sama, lalu scan).
3. Alternatif tanpa scan: buka WhatsApp HP → **Perangkat Tertaut** →
   **Hubungkan dengan Nomor Telepon**, lalu masukkan **Pairing Code** yang
   tampil di log terminal.
4. Setelah tersambung, sesi tersimpan otomatis di `wa_session.db` — restart
   **tidak** perlu scan ulang (selama file DB masih ada).

Cek status: buka `http://localhost:10000/status` di browser.

---

## ☁️ Deploy di Render (untuk 24/7)

### Prasyarat & peringatan
- Render **free tier mematikan service setelah ~15 menit idle** (spin-down).
  Saat mati, koneksi WhatsApp terputus dan **sesi tersimpan di file DB bisa
  hilang** karena filesystem free tier tidak persisten antar-restart.
- Karena itu, untuk produksi yang stabil disarankan:
  - **UptimeRobot** (gratis) di-set ping ke `https://app-kamu.onrender.com/health`
    setiap ~5 menit agar service tidak pernah idle; **dan**
  - pakai **plan berbayar** (Starter, ~$7/bln) agar filesystem persisten dan
    sesi WhatsApp tidak hilang saat redeploy.
- Tanpa plan berbayar, kamu mungkin harus **scan ulang QR setelah setiap
  restart**. Ini bukan bug — ini keterbatasan free tier.

### Langkah deploy
1. Buat **Web Service** baru di Render, hubungkan repo ini.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `python3 whatsapp_bot.py`
4. **Env vars** (dari dashboard Render):
   - `ANTHROPIC_API_KEY` (wajib, untuk AI)
   - `TELEGRAM_BOT_TOKEN` (tidak wajib untuk WhatsApp; hanya kalau mau
     Telegram juga jalan di service ini)
   - `WA_SESSION_DB=wa_session.db`
   - `WA_QR_TOKEN=<string acak panjang>` (sangat disarankan — URL Render itu
     publik, token ini melindungi halaman `/qr` dari orang lain yang ingin
     membajak sesi WhatsApp kamu)
   - `DATABASE_URL` (PostgreSQL yang sudah dipakai bot Telegram, agar riwayat
     belajar anak tersambung antar platform — opsional)
5. Buka `https://app-kamu.onrender.com/qr?token=<nilai WA_QR_TOKEN>` dari HP,
   scan QR-nya (atau pakai Pairing Code dari log Render). **Lakukan ini
   segera setelah deploy**, karena free tier akan mati setelah 15 menit idle.
   Setelah login sukses, `/qr` otomatis ditolak (403) dan QR tidak lagi
diekspos.
6. Pasang UptimeRobot ke `/health` supaya service tetap hidup.

> ℹ️ **Port:** Render menyuntikkan `PORT` otomatis; HTTP server di
> `whatsapp_bot.py` sudah membaca `PORT` dari environment, jadi tidak perlu
> set manual.

---

## 🔁 Menjalankan Telegram & WhatsApp bersamaan

Keduanya bisa hidup di satu mesin (mis. jalankan dua terminal, atau satu
service Render dengan perintah `sh -c 'python3 telegram_bot.py & python3 whatsapp_bot.py'`).
Karena berbagi `database.py`, riwayat belajar anak akan tersambung.

---

## 🛠️ Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| QR tidak muncul di `/qr` | Tunggu beberapa detik lalu muat ulang; cek log server. Jika pakai `WA_QR_TOKEN`, pastikan URL-nya `.../qr?token=...`. |
| `/qr` mengembalikan 403 | Bot sudah login (tidak perlu QR lagi) atau token salah. Cek `/status` untuk `connected: true`. |
| Nomor di-ban/diblokir | Risiko bawaan library tidak resmi. Tidak ada solusi 100% selain pakai API resmi (Meta Cloud API). |
| Sesi hilang di Render | Filesystem free tier tidak persisten. Upgrade plan berbayar atau scan ulang. |
| Koneksi putus tiba-tiba | WhatsApp memutus sesi lama; bot whatsmeow biasanya reconnect otomatis. Jika tidak, restart service. |
| `ImportError` neonize | Pastikan `pip install -r requirements.txt` sukses; prebuilt wheel hanya untuk linux x86_64 (Render & kebanyakan laptop OK). |
