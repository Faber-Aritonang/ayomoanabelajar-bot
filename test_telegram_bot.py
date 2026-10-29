"""Tes offline handler dan perintah bot Telegram.

Semua panggilan ke AI, Telegram, dan Groq diganti mock, dan database memakai
file SQLite sementara. Tes bisa dijalankan tanpa token bot atau koneksi internet.

Cara jalankan:
    python3 test_telegram_bot.py
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
import llm
import telegram_bot

USER_ID = 123456789


def make_voice(duration=10, audio=b"OggS-audio"):
    """Voice note palsu: get_file() -> download_as_bytearray()."""
    file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(audio)))
    return SimpleNamespace(duration=duration, get_file=AsyncMock(return_value=file))


class TelegramHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=".")
        self.engine = create_engine(f"sqlite:///{Path(self.temp_dir.name) / 'telegram.db'}")
        database.Base.metadata.create_all(self.engine)
        self.session_patch = patch.object(
            database, "SessionLocal", sessionmaker(bind=self.engine)
        )
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(lambda: self.engine.dispose())

        self.message = SimpleNamespace(
            text="",
            reply_text=AsyncMock(),
            reply_markdown=AsyncMock(),
            voice=None,
        )
        self.update = SimpleNamespace(
            message=self.message,
            effective_message=self.message,
            effective_user=SimpleNamespace(id=USER_ID, username="anak_uji", first_name="Anak"),
            effective_chat=SimpleNamespace(id=999),
            callback_query=None,
        )
        self.context = SimpleNamespace(
            args=[],
            user_data={},
            bot=SimpleNamespace(
                send_chat_action=AsyncMock(),
                send_voice=AsyncMock(),
                send_message=AsyncMock(),
            ),
        )
        self.voice_reply = AsyncMock()
        for patcher in (
            patch.object(telegram_bot, "send_voice_reply", self.voice_reply),
            patch.object(telegram_bot.tts, "is_tts_available", return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_callback(self, data, user_id=USER_ID):
        query = SimpleNamespace(
            from_user=SimpleNamespace(id=user_id),
            data=data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=self.message,
        )
        self.update.callback_query = query
        return query

    def add_messages(self, count, subject="matematika", role="user"):
        for i in range(count):
            database.save_message(USER_ID, "anak_uji", subject, role, f"pesan {i}")

    # --- Perintah dasar -------------------------------------------------

    async def test_start_mereset_state_dan_menampilkan_enam_pelajaran(self):
        self.context.user_data.update(subject="matematika", quiz={"key": "A"})
        await telegram_bot.start(self.update, self.context)
        self.assertNotIn("subject", self.context.user_data)
        self.assertNotIn("quiz", self.context.user_data)
        text = self.message.reply_markdown.await_args.args[0]
        self.assertIn("Selamat datang", text)
        markup = self.message.reply_markdown.await_args.kwargs["reply_markup"]
        labels = [button.text for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(labels), 6)
        self.assertIn("Matematika", labels[0])

    async def test_help_dan_menu_menampilkan_perintah_utama(self):
        await telegram_bot.help_command(self.update, self.context)
        bantuan = self.message.reply_markdown.await_args.args[0]
        for command in ("/start", "/menu", "/streak", "/reset", "/suara", "/help"):
            self.assertIn(command, bantuan)

        await telegram_bot.menu_command(self.update, self.context)
        menu = self.message.reply_markdown.await_args.args[0]
        for command in ("/start", "/kuis", "/bintang", "/streak", "/suara", "/laporan", "/rapor"):
            self.assertIn(command, menu)
        markup = self.message.reply_markdown.await_args.kwargs["reply_markup"]
        callbacks = [b.callback_data for row in markup.inline_keyboard for b in row]
        self.assertEqual(callbacks, ["voice:perempuan", "voice:laki-laki"])

    async def test_suara_valid_disimpan_dan_pilihan_tidak_dikenal_ditolak(self):
        self.context.args = ["robot"]
        await telegram_bot.voice_command(self.update, self.context)
        self.assertIsNone(database.get_telegram_voice(USER_ID))
        self.assertIn("reply_markup", self.message.reply_text.await_args.kwargs)

        self.context.args = ["laki-laki"]
        await telegram_bot.voice_command(self.update, self.context)
        self.assertEqual(database.get_telegram_voice(USER_ID), "id-ID-ArdiNeural")
        self.assertIn("laki-laki", self.message.reply_text.await_args.args[0])

        self.context.args = ["perempuan"]
        await telegram_bot.voice_command(self.update, self.context)
        self.assertEqual(database.get_telegram_voice(USER_ID), "id-ID-GadisNeural")

    async def test_reset_butuh_pelajaran_lalu_keluar_dari_kuis(self):
        await telegram_bot.reset(self.update, self.context)
        self.assertIn("Ketik /start", self.message.reply_text.await_args.args[0])

        self.context.user_data.update(subject="ipas", quiz={"key": "B"})
        await telegram_bot.reset(self.update, self.context)
        self.assertTrue(self.context.user_data["reset_marker"])
        self.assertNotIn("quiz", self.context.user_data)
        self.assertIn("IPAS", self.message.reply_text.await_args.args[0])

    async def test_streak_kosong_dan_setelah_belajar_hari_ini(self):
        await telegram_bot.streak_command(self.update, self.context)
        self.assertIn("belum punya catatan belajar", self.message.reply_text.await_args.args[0])

        self.add_messages(1)
        await telegram_bot.streak_command(self.update, self.context)
        self.assertIn("1 hari berturut-turut", self.message.reply_markdown.await_args.args[0])

    # --- Kuis -----------------------------------------------------------

    async def test_kuis_butuh_pelajaran_dan_menyimpan_soal(self):
        await telegram_bot.kuis_command(self.update, self.context)
        self.assertIn("Pilih dulu", self.message.reply_text.await_args.args[0])

        self.context.user_data["subject"] = "matematika"
        with patch.object(telegram_bot.quiz, "start_quiz", return_value="Berapa 2 + 2?") as start:
            await telegram_bot.kuis_command(self.update, self.context)
        start.assert_called_once()
        teks = self.message.reply_text.await_args.args[0]
        self.assertIn("Kuis Adaptif (Matematika)", teks)
        self.assertIn("Berapa 2 + 2?", teks)
        riwayat = database.get_recent_messages(USER_ID, "matematika", limit=1)
        self.assertEqual(riwayat[0]["content"], "Berapa 2 + 2?")

    async def test_kuis_gagal_menyiapkan_soal_dibalas_ramah(self):
        self.context.user_data["subject"] = "matematika"
        with patch.object(telegram_bot.quiz, "start_quiz", return_value=None):
            await telegram_bot.kuis_command(self.update, self.context)
        self.assertIn("kesulitan menyiapkan kuis", self.message.reply_text.await_args.args[0])

    async def test_jawaban_kuis_menyimpan_skor_akhir(self):
        self.context.user_data.update(subject="matematika", quiz={"key": "B"})

        def answer_and_finish(state, answer_text):
            state.pop("quiz", None)  # tiru answer_quiz saat sesi selesai
            return "🎉 BENAR! +10 poin", None, {"score": 10, "total": 5}

        with patch.object(telegram_bot.quiz, "answer_quiz", side_effect=answer_and_finish):
            await telegram_bot.process_text(self.update, self.context, "B")
        self.assertIn("BENAR", self.message.reply_markdown.await_args.args[0])
        self.assertEqual(
            [(s, p, t) for s, p, t in database.get_quiz_summary(USER_ID)],
            [("matematika", 10, 5)],
        )
        self.assertNotIn("quiz", self.context.user_data)

    async def test_jawaban_kuis_benar_menambah_poin_dan_lanjut_soal(self):
        self.context.user_data.update(
            subject="matematika",
            quiz={
                "subject": "matematika",
                "key": "B",
                "score": 0,
                "total": 0,
                "question": "Soal lama",
            },
        )
        next_question = "Soal berikutnya: 3 + 4?\nA. 6\nB. 7\nKUNCI: B"
        with patch.object(telegram_bot.quiz, "get_ai_reply", return_value=next_question):
            await telegram_bot.process_text(self.update, self.context, "B")

        feedback = self.message.reply_markdown.await_args_list[0].args[0]
        self.assertIn("BENAR", feedback)
        self.assertIn("+10 poin", feedback)
        self.assertIn("*10* poin", feedback)
        self.assertNotIn("KUNCI", feedback)
        self.assertEqual(self.context.user_data["quiz"]["score"], 10)
        self.assertEqual(self.context.user_data["quiz"]["total"], 1)

        soal = self.message.reply_markdown.await_args_list[1].args[0]
        self.assertIn("Kuis Adaptif (Matematika)", soal)
        self.assertIn("Soal berikutnya: 3 + 4?", soal)
        self.assertNotIn("KUNCI", soal)
        self.assertEqual(database.get_quiz_summary(USER_ID), [])

    async def test_jawaban_kuis_salah_tidak_menambah_poin_dan_menyimpan_skor(self):
        self.context.user_data.update(
            subject="matematika",
            quiz={
                "subject": "matematika",
                "key": "C",
                "score": 20,
                "total": 4,
                "question": "Soal terakhir",
            },
        )
        await telegram_bot.process_text(self.update, self.context, "A")

        feedback = self.message.reply_markdown.await_args.args[0]
        self.assertIn("Belum tepat", feedback)
        self.assertIn("Jawaban yang benar adalah *C*", feedback)
        self.assertIn("*20* poin", feedback)
        self.assertIn("Kuis selesai", feedback)
        self.assertNotIn("+10", feedback)
        self.assertNotIn("quiz", self.context.user_data)
        self.assertEqual(
            [tuple(row) for row in database.get_quiz_summary(USER_ID)],
            [("matematika", 20, 5)],
        )

    async def test_jawaban_kuis_tanpa_huruf_a_sampai_d_tidak_mengubah_skor(self):
        self.context.user_data.update(
            subject="matematika",
            quiz={
                "subject": "matematika",
                "key": "B",
                "score": 10,
                "total": 1,
                "question": "Soal aktif",
            },
        )
        for answer in ("2", "E", "belum tahu"):
            with self.subTest(answer=answer):
                await telegram_bot.process_text(self.update, self.context, answer)
                feedback = self.message.reply_markdown.await_args.args[0]
                self.assertIn("belum paham jawabanmu", feedback)
                self.assertIn("Ketik hurufnya saja", feedback)
                self.assertNotIn("poin", feedback)
                self.assertEqual(self.context.user_data["quiz"]["score"], 10)
                self.assertEqual(self.context.user_data["quiz"]["total"], 1)
                self.assertEqual(self.context.user_data["quiz"]["key"], "B")
                self.assertEqual(database.get_quiz_summary(USER_ID), [])
        self.assertEqual(self.message.reply_markdown.await_count, 3)

    async def test_jawaban_kuis_mencampur_huruf_dan_penjelasan(self):
        cases = [
            ("B karena 2 + 2 memang 4", True),
            ("Jawabannya b, sebab 3 + 4 = 7", True),
            ("Menurut saya A karena 2 + 4 = 7", False),
            ("c. karena hasilnya delapan", False),
        ]
        next_question = "Soal lanjutan: 5 + 1?\nA. 5\nB. 6\nKUNCI: B"
        with patch.object(telegram_bot.quiz, "get_ai_reply", return_value=next_question):
            for answer, benar in cases:
                with self.subTest(answer=answer):
                    self.context.user_data["subject"] = "matematika"
                    self.context.user_data["quiz"] = {
                        "subject": "matematika",
                        "question": "Soal aktif",
                        "key": "B",
                        "score": 0,
                        "total": 0,
                    }
                    self.message.reply_markdown.reset_mock()
                    await telegram_bot.process_text(self.update, self.context, answer)

                    feedback = self.message.reply_markdown.await_args_list[0].args[0]
                    if benar:
                        self.assertIn("BENAR", feedback)
                        self.assertIn("+10 poin", feedback)
                        self.assertEqual(self.context.user_data["quiz"]["score"], 10)
                    else:
                        self.assertIn("Belum tepat", feedback)
                        self.assertIn("Jawaban yang benar adalah *B*", feedback)
                        self.assertNotIn("+10 poin", feedback)
                        self.assertEqual(self.context.user_data["quiz"]["score"], 0)

                    self.assertEqual(self.context.user_data["quiz"]["total"], 1)
                    self.assertIn(
                        "Kuis Adaptif (Matematika)",
                        self.message.reply_markdown.await_args_list[1].args[0],
                    )
                    self.assertEqual(database.get_quiz_summary(USER_ID), [])

    async def test_jawaban_kuis_dengan_lebih_dari_satu_huruf(self):
        # Aturan saat ini: huruf A-D pertama yang ditemukan dipakai menilai.
        cases = [
            ("B atau C", True),
            ("A atau B", False),
            ("Jawabannya C, walaupun B juga mungkin", False),
            ("pilih B, bukan D", True),
        ]
        next_question = "Soal lanjutan: 6 + 1?\nA. 6\nB. 7\nKUNCI: B"
        with patch.object(telegram_bot.quiz, "get_ai_reply", return_value=next_question):
            for answer, benar in cases:
                with self.subTest(answer=answer):
                    self.context.user_data["subject"] = "matematika"
                    self.context.user_data["quiz"] = {
                        "subject": "matematika",
                        "question": "Soal aktif",
                        "key": "B",
                        "score": 0,
                        "total": 0,
                    }
                    self.message.reply_markdown.reset_mock()
                    await telegram_bot.process_text(self.update, self.context, answer)

                    feedback = self.message.reply_markdown.await_args_list[0].args[0]
                    if benar:
                        self.assertIn("BENAR", feedback)
                        self.assertEqual(self.context.user_data["quiz"]["score"], 10)
                    else:
                        self.assertIn("Belum tepat", feedback)
                        self.assertIn("Jawaban yang benar adalah *B*", feedback)
                        self.assertEqual(self.context.user_data["quiz"]["score"], 0)
                    self.assertEqual(self.context.user_data["quiz"]["total"], 1)
                    self.assertEqual(database.get_quiz_summary(USER_ID), [])

    # --- Laporan, bintang, rapor ---------------------------------------

    async def test_laporan_kosong_dan_berisi_rekap(self):
        await telegram_bot.laporan_command(self.update, self.context)
        self.assertIn("Belum ada riwayat", self.message.reply_text.await_args.args[0])

        self.add_messages(2)
        database.save_quiz_score(USER_ID, "anak_uji", "matematika", 10, 5)
        await telegram_bot.laporan_command(self.update, self.context)
        laporan = self.message.reply_markdown.await_args.args[0]
        self.assertIn("Matematika*: 2 interaksi", laporan)
        self.assertIn("10 poin dari 5 soal", laporan)

    async def test_bintang_bertambah_setiap_lima_interaksi(self):
        await telegram_bot.bintang_command(self.update, self.context)
        self.assertIn("belum punya bintang", self.message.reply_text.await_args.args[0])

        self.add_messages(3)
        await telegram_bot.bintang_command(self.update, self.context)
        self.assertIn("butuh 2 interaksi lagi", self.message.reply_text.await_args.args[0])

        self.add_messages(2)
        await telegram_bot.bintang_command(self.update, self.context)
        self.assertIn("1 Bintang", self.message.reply_markdown.await_args.args[0])

    async def test_rapor_butuh_data_dan_menangani_kegagalan_ai(self):
        self.add_messages(2)
        await telegram_bot.rapor_command(self.update, self.context)
        self.assertIn("belum cukup", self.message.reply_text.await_args.args[0])

        self.add_messages(3)
        # rapor_command mengimpor get_ai_reply dari llm di dalam fungsi.
        with patch.object(llm, "get_ai_reply", return_value="Ringkasan rapor uji."):
            await telegram_bot.rapor_command(self.update, self.context)
        self.assertIn("RAPOR EVALUASI", self.message.reply_markdown.await_args.args[0])
        self.assertIn("Ringkasan rapor uji.", self.message.reply_markdown.await_args.args[0])

        with patch.object(llm, "get_ai_reply", side_effect=RuntimeError("AI mati")):
            await telegram_bot.rapor_command(self.update, self.context)
        self.assertIn("kesalahan teknis", self.message.reply_text.await_args.args[0])

    # --- Admin whitelist ------------------------------------------------

    async def test_admin_whitelist_menolak_non_admin(self):
        self.message.text = "/tambah 987654321"
        self.context.args = ["987654321"]
        with patch.object(telegram_bot.whitelist, "is_admin", return_value=False):
            await telegram_bot.admin_whitelist_command(self.update, self.context)
        self.assertIn("hanya untuk admin", self.message.reply_text.await_args.args[0])
        self.assertFalse(database.whitelist_contains("987654321", "telegram"))

    async def test_admin_whitelist_tambah_daftar_dan_hapus(self):
        with patch.object(telegram_bot.whitelist, "is_admin", return_value=True):
            self.message.text = "/tambah 987654321"
            self.context.args = ["987654321"]
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("berhasil didaftarkan", self.message.reply_text.await_args.args[0])
            self.assertTrue(database.whitelist_contains("987654321", "telegram"))

            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("sudah ada", self.message.reply_text.await_args.args[0])

            self.message.text = "/daftar"
            self.context.args = []
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("987654321", self.message.reply_markdown.await_args.args[0])

            self.message.text = "/tambah bukan_angka"
            self.context.args = ["bukan_angka"]
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("harus berupa angka", self.message.reply_text.await_args.args[0])

            self.message.text = "/hapus 987654321"
            self.context.args = ["987654321"]
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("dihapus dari whitelist", self.message.reply_text.await_args.args[0])
            self.assertFalse(database.whitelist_contains("987654321", "telegram"))

    async def test_admin_whitelist_kosong_dan_hapus_tidak_ada(self):
        with patch.object(telegram_bot.whitelist, "is_admin", return_value=True), \
             patch.object(telegram_bot.whitelist, "base_list", return_value=[]):
            self.message.text = "/daftar"
            self.context.args = []
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("Whitelist Telegram kosong", self.message.reply_text.await_args.args[0])

            self.message.text = "/hapus 987654321"
            self.context.args = ["987654321"]
            await telegram_bot.admin_whitelist_command(self.update, self.context)
            self.assertIn("tidak ada di whitelist", self.message.reply_text.await_args.args[0])

    # --- Whitelist & tombol --------------------------------------------

    async def test_filter_whitelist_dan_penolakan_ramah(self):
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=False):
            self.assertFalse(telegram_bot.WL_FILTER.check_update(self.update))
            await telegram_bot.reject_not_whitelisted(self.update, self.context)
            self.assertEqual(
                self.message.reply_text.await_args.args[0], telegram_bot.whitelist.REJECT_TEXT
            )
            query = self.make_callback("subject:matematika")
            await telegram_bot.reject_callback(self.update, self.context)
            query.answer.assert_awaited_with(
                telegram_bot.whitelist.REJECT_TEXT, show_alert=True
            )

        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=True):
            self.assertTrue(telegram_bot.WL_FILTER.check_update(self.update))
            query.answer.reset_mock()
            await telegram_bot.reject_callback(self.update, self.context)
            query.answer.assert_not_awaited()

        self.assertFalse(
            telegram_bot.WL_FILTER.check_update(SimpleNamespace(effective_user=None))
        )

    async def test_pilih_pelajaran_lewat_tombol(self):
        query = self.make_callback("subject:bahasa_indonesia")
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=True):
            await telegram_bot.subject_chosen(self.update, self.context)
        self.assertEqual(self.context.user_data["subject"], "bahasa_indonesia")
        self.assertIn("Bahasa Indonesia", query.edit_message_text.await_args.args[0])
        self.assertNotIn("quiz", self.context.user_data)

        query = self.make_callback("subject:tidak_ada")
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=True):
            await telegram_bot.subject_chosen(self.update, self.context)
        self.assertIn("tidak ditemukan", query.edit_message_text.await_args.args[0])

        self.context.user_data.pop("subject")
        query = self.make_callback("subject:matematika", user_id=555)
        query.edit_message_text.reset_mock()
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=False):
            await telegram_bot.subject_chosen(self.update, self.context)
        query.answer.assert_awaited_with(telegram_bot.whitelist.REJECT_TEXT, show_alert=True)
        query.edit_message_text.assert_not_awaited()

    # --- Pesan teks & suara --------------------------------------------

    async def test_pesan_teks_butuh_pelajaran_lalu_dijawab_dan_disimpan(self):
        self.message.text = "Apa itu fotosintesis?"
        await telegram_bot.handle_message(self.update, self.context)
        self.assertIn("Pilih dulu", self.message.reply_text.await_args.args[0])

        self.context.user_data["subject"] = "ipas"
        with patch.object(telegram_bot, "get_ai_reply", return_value="Tumbuhan memasak makanan."):
            await telegram_bot.handle_message(self.update, self.context)
        self.assertIn("Tumbuhan memasak makanan.", self.message.reply_text.await_args.args[0])
        self.voice_reply.assert_awaited_once()
        riwayat = database.get_recent_messages(USER_ID, "ipas", limit=2)
        self.assertEqual([m["content"] for m in riwayat],
                         ["Apa itu fotosintesis?", "Tumbuhan memasak makanan."])

    async def test_voice_note_ditolak_tanpa_pelajaran_atau_terlalu_panjang(self):
        self.message.voice = make_voice()
        await telegram_bot.handle_voice(self.update, self.context)
        self.assertIn("Pilih dulu", self.message.reply_text.await_args.args[0])

        self.context.user_data["subject"] = "matematika"
        self.message.voice = make_voice(duration=121)
        await telegram_bot.handle_voice(self.update, self.context)
        self.assertIn("kepanjangan", self.message.reply_text.await_args.args[0])
        self.message.voice.get_file.assert_not_awaited()

    async def test_voice_note_ditranskripsi_lalu_dijawab(self):
        self.context.user_data["subject"] = "matematika"
        self.message.voice = make_voice()
        with patch.object(telegram_bot.stt, "transcribe_audio", return_value="berapa 2 + 2"), \
             patch.object(telegram_bot, "get_ai_reply", return_value="Empat."):
            await telegram_bot.handle_voice(self.update, self.context)
        self.assertIn("Kak Moana mendengar", self.message.reply_markdown.await_args.args[0])
        self.assertIn("berapa 2 + 2", self.message.reply_markdown.await_args.args[0])
        self.assertIn("Empat.", self.message.reply_text.await_args.args[0])
        self.voice_reply.assert_awaited_once()

    async def test_voice_note_gagal_dan_transkripsi_kosong(self):
        self.context.user_data["subject"] = "matematika"
        self.message.voice = make_voice()
        self.message.voice.get_file.side_effect = RuntimeError("unduh gagal")
        await telegram_bot.handle_voice(self.update, self.context)
        self.assertIn("belum bisa kudengar", self.message.reply_text.await_args.args[0])

        self.message.voice = make_voice()
        with patch.object(telegram_bot.stt, "transcribe_audio", return_value=""):
            await telegram_bot.handle_voice(self.update, self.context)
        self.assertIn("tidak mendengar", self.message.reply_text.await_args.args[0])

    # --- Pengingat ------------------------------------------------------

    async def test_pengingat_hanya_dikirim_ke_pengguna_whitelist(self):
        with patch.object(
            telegram_bot.reminders,
            "reminder_job_once",
            return_value=[("123", "Pengingat"), ("456", "Pengingat")],
        ), patch.object(
            telegram_bot.whitelist,
            "is_allowed",
            side_effect=lambda uid, platform: uid == "123",
        ):
            await telegram_bot.reminder_job(self.context)
        self.context.bot.send_message.assert_awaited_once_with(
            chat_id=123, text="Pengingat"
        )


if __name__ == "__main__":
    unittest.main()
