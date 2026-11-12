# 🤝 Panduan Kontributor

Dokumen ini menjelaskan struktur proyek dan pola implementasi **mode suara** (STT + TTS) yang dipakai bersama oleh bot Telegram dan WhatsApp. Isinya menggantikan catatan terpisah yang sebelumnya duplikat.

## Menyiapkan Lingkungan

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # isi token dan API key
```

Python yang dipakai produksi adalah **3.14** (lihat `.python-version`). Untuk mode suara, `GROQ_API_KEY` wajib diisi untuk transkripsi. TTS memakai ElevenLabs bila `ELEVENLABS_API_KEY` dan voice ID diisi; tanpa itu Edge TTS tetap berjalan tanpa API key.

## Peta Modul

| Berkas | Tanggung jawab |
|---|---|
| `telegram_bot.py` | Handler Telegram, tombol, webhook/polling, pengiriman voice note |
| `whatsapp_bot.py` | Handler Neonize, deteksi PTT, konversi Ogg Opus, pengiriman voice note |
| `stt.py` | Transkripsi audio ke teks via Groq Whisper |
| `tts.py` | ElevenLabs (opsional), Edge TTS + fallback gTTS, pelafalan matematika, file sementara |
| `llm.py` | Panggilan Claude dan pemuatan materi |
| `subjects.py` | Prompt guru per mata pelajaran |
| `database.py` | Riwayat, skor kuis, whitelist, preferensi suara Telegram |
| `quiz.py`, `reminders.py`, `whitelist.py` | Logika bersama kedua platform |

## Alur Mode Suara

### 1. Voice note masuk (STT)

**Telegram** — `handle_voice`:
1. Pastikan pelajaran sudah dipilih.
2. Tolak voice note lebih dari **120 detik**.
3. Unduh audio (`get_file` → `download_as_bytearray`).
4. `stt.transcribe_audio(bytes)` memanggil Groq (`whisper-large-v3-turbo`, bahasa `id`).
5. Tampilkan transkrip ke anak, lalu lanjutkan ke `process_text` seperti pesan teks biasa.

**WhatsApp** — `handle_voice`:
1. `on_message` hanya memproses `audioMessage` dengan `PTT=True`; file audio biasa ditolak dengan pesan ramah.
2. Pastikan pelajaran sudah dipilih dan durasi ≤ 120 detik.
3. Unduh lewat `client.download_any`, transkripsi dengan `stt.transcribe_audio`.
4. Tampilkan transkrip, lalu panggil `handle_chat`.

Kegagalan transkripsi ditangkap di masing-masing handler dan dijawab dengan pesan ramah — jangan biarkan exception mematikan pemrosesan pesan.

### 2. Balasan suara (TTS)

**Telegram** — `process_text` → `send_voice_reply`:
1. Teks balasan selalu dikirim lebih dulu (`reply_text`).
2. Jika `tts.is_tts_available()`, pilih suara dari database (`database.get_telegram_voice`); nilai lama `id-ID-GadisNeural` / `id-ID-ArdiNeural` dipetakan ke suara perempuan / laki-laki.
3. `tts.text_to_speech(...)` mencoba ElevenLabs lebih dulu (bila `ELEVENLABS_API_KEY` dan voice ID untuk pilihan itu tersedia), lalu Edge TTS, lalu gTTS. Hasilnya MP3.
4. `tts.create_voice_file` menulis file sementara, lalu `bot.send_voice` mengirimnya.
5. File sementara dihapus di blok `finally`.

**WhatsApp** — `handle_chat` → `_send_voice_reply`:
1. Teks dikirim lebih dulu.
2. TTS dijalankan lewat `asyncio.run` karena handler Neonize sinkron. WhatsApp memakai suara perempuan, yang berarti voice ID `ELEVENLABS_VOICE_ID_FEMALE` bila ElevenLabs aktif.
3. `_voice_note_audio` mengubah MP3 menjadi **Ogg Opus** dengan ffmpeg dari `imageio-ffmpeg` dan menghitung durasi dari granule position.
4. Audio diunggah (`client.upload`) lalu dikirim sebagai `AudioMessage` dengan `PTT=True`, `mimetype="audio/ogg; codecs=opus"`.
5. Semua kegagalan hanya dicatat di log; balasan teks tetap sampai ke pengguna.

### 3. Pelafalan matematika

`tts.prepare_speech_text` hanya mengubah teks yang **dibacakan**, bukan teks balasan. Fungsi ini menangani pecahan, akar, pangkat, persen, operasi hitung, dan kurung. Notasi LaTeX kompleks di luar pola yang dikenal akan dibaca apa adanya, jadi jangan menambah dukungan setengah-setengah tanpa tes.

## Pola Implementasi

1. **Lazy import untuk dependensi opsional.** `tts.py` mengimpor `edge_tts` dan `gTTS` di dalam `try/except ImportError`; bot tetap bisa jalan tanpa TTS. Selalu cek `is_tts_available()` sebelum memanggil TTS.
2. **Modul bersama, bukan duplikasi.** STT, TTS, kuis, pengingat, dan whitelist dipakai kedua bot. Perbedaan platform hanya di lapisan handler/pengiriman.
3. **Graceful degradation.** Kirim teks dulu, anggap suara sebagai bonus. Kegagalan TTS, unggah, atau konversi tidak boleh membatalkan balasan teks.
4. **Bersihkan sumber daya.** Telegram memakai file sementara dan menghapusnya di `finally`. WhatsApp memproses audio di memori lewat pipe ffmpeg.
5. **Preferensi per pengguna disimpan di database.** Pilihan suara Telegram ada di tabel `telegram_voice_preferences`; WhatsApp belum punya pilihan suara.
6. **Echo transkrip.** Tampilkan hasil STT ke anak agar ia bisa mengoreksi salah dengar sebelum jawaban diproses.
7. **Konfigurasi lewat environment.** API key, model STT, dan bahasa dibaca dari env (lihat `.env.example`), bukan di-hardcode.

## Jebakan yang Sering Muncul

- **Groq wajib untuk STT.** Tanpa `GROQ_API_KEY`, transkripsi melempar error; tangkap dan beri pesan ramah. Batas gratis sekitar 2.000 request/hari.
- **Hanya voice note (PTT).** Di WhatsApp, rekaman audio biasa bukan voice note dan akan ditolak. Di Telegram, handler hanya terpasang untuk `filters.VOICE`.
- **Batas 2 menit.** Diterapkan di kedua platform sebelum unduh/transkripsi.
- **ElevenLabs butuh API key dan voice ID.** `ELEVENLABS_API_KEY` serta voice ID pria/wanita dibaca dari environment; `ELEVENLABS_MODEL_ID` opsional dengan default `eleven_multilingual_v2`. Jangan pernah menaruh key di kode atau log; bila panggilan gagal, `tts.py` mencatat peringatan tanpa isi respons dan lanjut ke Edge TTS.
- **Edge TTS tidak resmi.** Layanan daring Microsoft ini dipakai sebagai cadangan bila ElevenLabs belum diisi atau gagal. gTTS adalah cadangan terakhir dan tidak bisa memilih suara. Semuanya butuh internet.
- **Jangan menunggu TTS tanpa batas.** `stt.py` memakai timeout 60 detik; konversi ffmpeg WhatsApp memakai timeout 60 detik. Pertahankan timeout saat menambah panggilan jaringan.
- **Jangan log token atau API key.** Telegram sudah memasang formatter yang meredaksi `TELEGRAM_BOT_TOKEN`; ikuti pola itu untuk secret baru.
- **Filesystem Render tidak persisten.** `wa_session.db` bisa hilang saat redeploy di free tier, sehingga perlu scan ulang. Riwayat belajar sebaiknya di `DATABASE_URL` (Postgres/Neon).
- **Risiko WhatsApp.** Neonize bukan API resmi dan melanggar Ketentuan Layanan WhatsApp. Gunakan nomor yang tidak penting dan hindari broadcast massal. Lihat [WHATSAPP.md](WHATSAPP.md).

## Menambah Pilihan Suara Telegram

1. Tambahkan kunci pilihan ke `VOICE_CHOICES` di `telegram_bot.py`. Nilainya tetap nama Edge TTS agar preferensi lama di database tidak perlu migrasi.
2. Petakan kunci itu ke voice ID ElevenLabs di `EDGE_VOICES` / `_elevenlabs_voice_id` pada `tts.py`, dan sediakan variabel environment untuk voice ID barunya.
3. Tanpa voice ID ElevenLabs, pilihan tersebut otomatis memakai suara Edge TTS-nya; gTTS mengabaikan pilihan suara.
4. Perbarui `/suara`, `/help`, dan `.env.example` bila format perintah atau variabel berubah.

## Checklist Sebelum Mengirim Perubahan

- [ ] `python3 test_whatsapp_bot.py` lulus (64 skenario, 103 pemeriksaan).
- [ ] `python3 test_telegram_voice.py` lulus (10 unit test).
- [ ] `python3 test_telegram_bot.py` lulus (37 unit test handler & perintah).
- [ ] Workflow GitHub Actions `Tests` lulus untuk push terakhir.
- [ ] Perubahan mode suara ditangani di kedua platform, atau keterbatasannya didokumentasikan.
- [ ] Balasan teks tetap terkirim saat STT/TTS gagal.
- [ ] File sementara dibersihkan dan tidak ada secret yang masuk log.
- [ ] README/WHATSAPP.md diperbarui bila env var atau perilaku pengguna berubah.
