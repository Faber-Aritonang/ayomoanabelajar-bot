"""Tes offline pilihan suara dan pelafalan matematika Telegram."""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
import telegram_bot
import tts


class DatabaseConnectionTests(unittest.TestCase):
    def test_postgres_engine_enables_pre_ping(self):
        env = dict(os.environ, DATABASE_URL="postgresql://test:test@localhost/test")
        result = subprocess.run(
            [sys.executable, "-c", "import database; assert database.engine.pool._pre_ping"],
            env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stale_pooled_connection_is_replaced_before_write(self):
        engine = create_engine("sqlite://", pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("CREATE TABLE pool_test (value INTEGER)")
                conn.commit()
                stale = conn.connection.driver_connection
            stale.close()  # Simulasikan server yang menutup koneksi idle.
            with engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE pool_test (value INTEGER)")
                conn.exec_driver_sql("INSERT INTO pool_test VALUES (1)")
                self.assertEqual(conn.exec_driver_sql("SELECT value FROM pool_test").scalar_one(), 1)
        finally:
            engine.dispose()


class LoggingTests(unittest.TestCase):
    def test_token_redacted_in_message_and_exception(self):
        token = "123456:example-test-token"
        formatter = telegram_bot.TelegramTokenFormatter("%(levelname)s %(message)s")
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": token}):
            try:
                raise ValueError(f"request for {token} failed")
            except ValueError:
                import sys
                record = logging.LogRecord("httpx", logging.ERROR, __file__, 1,
                                           "request to %s", (f"https://api.telegram.org/bot{token}/getMe",),
                                           sys.exc_info())
            result = formatter.format(record)
        self.assertNotIn(token, result)
        self.assertEqual(result.count("[TOKEN-REDACTED]"), 2)
        self.assertLess(logging.getLogger("httpx").getEffectiveLevel(), logging.CRITICAL)
        self.assertGreaterEqual(logging.getLogger("httpx").getEffectiveLevel(), logging.WARNING)


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=".")
        self.db_url = f"sqlite:///{Path(self.temp_dir.name) / 'voice.db'}"
        self.engine = create_engine(self.db_url)
        database.Base.metadata.create_all(self.engine)
        self.session_patch = patch.object(database, "SessionLocal", sessionmaker(bind=self.engine))
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(lambda: self.engine.dispose())
        self.message = SimpleNamespace(reply_text=AsyncMock(), reply_markdown=AsyncMock())
        self.update = SimpleNamespace(
            message=self.message,
            effective_user=SimpleNamespace(id=123),
            effective_chat=SimpleNamespace(id=456),
        )
        self.context = SimpleNamespace(args=[], user_data={}, bot=SimpleNamespace(send_voice=AsyncMock()))

    async def test_choice_survives_new_database_connection(self):
        self.context.args = ["laki-laki"]
        await telegram_bot.voice_command(self.update, self.context)
        self.assertEqual(database.get_telegram_voice(123), "id-ID-ArdiNeural")
        self.assertIsNone(database.get_telegram_voice(456))
        self.engine.dispose()
        self.assertEqual(database.get_telegram_voice(123), "id-ID-ArdiNeural")
        with patch.object(tts, "text_to_speech", AsyncMock(return_value=b"audio")) as speech:
            await telegram_bot.send_voice_reply(self.update, self.context, "Halo")
            speech.assert_awaited_once_with("Halo", language="id", voice="id-ID-ArdiNeural")
            self.context.bot.send_voice.assert_awaited_once()
        self.context.args = ["perempuan"]
        await telegram_bot.voice_command(self.update, self.context)
        self.assertEqual(database.get_telegram_voice(123), "id-ID-GadisNeural")

    async def test_menu_buttons_and_callback(self):
        await telegram_bot.menu_command(self.update, self.context)
        markup = self.message.reply_markdown.await_args.kwargs["reply_markup"]
        self.assertEqual([b.callback_data for b in markup.inline_keyboard[0]],
                         ["voice:perempuan", "voice:laki-laki"])
        await telegram_bot.voice_command(self.update, self.context)
        self.assertIn("reply_markup", self.message.reply_text.await_args.kwargs)
        query = SimpleNamespace(from_user=SimpleNamespace(id=123), data="voice:laki-laki",
                                answer=AsyncMock(), message=self.message)
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=True):
            await telegram_bot.voice_chosen(SimpleNamespace(callback_query=query), self.context)
        self.assertEqual(database.get_telegram_voice(123), "id-ID-ArdiNeural")
        query.from_user.id = 456
        with patch.object(telegram_bot.whitelist, "is_allowed", return_value=False):
            await telegram_bot.voice_chosen(SimpleNamespace(callback_query=query), self.context)
        self.assertIsNone(database.get_telegram_voice(456))
        query.answer.assert_awaited_with(telegram_bot.whitelist.REJECT_TEXT, show_alert=True)

    async def test_math_is_only_changed_for_speech_and_fallback(self):
        samples = {
            "2 + 3 = 5.": "2 tambah 3 sama dengan 5.",
            "8-3=5, 2×4=8, 12 ÷ 3 = 4": "8 kurang 3 sama dengan 5, 2 kali 4 sama dengan 8, 12 dibagi 3 sama dengan 4",
            "1/2 dan 25% dan 3² dan 4^3": "1 per 2 dan 25 persen dan 3 pangkat dua dan 4 pangkat tiga",
            "17/08/2026 pukul 10:30": "17/08/2026 pukul 10:30",
            "Lihat https://contoh.id/1/2 dan 3.14": "Lihat https://contoh.id/1/2 dan 3.14",
            "1 1/2 + 2/3": "1 dan 1 per 2 tambah 2 per 3",
            "(2 + 3) × 4 = 20": "buka kurung 2 tambah 3 tutup kurung kali 4 sama dengan 20",
            r"$\frac{1}{2} + \frac{3}{4} = \frac{5}{4}$": "pecahan 1 per 2 selesai pecahan tambah pecahan 3 per 4 selesai pecahan sama dengan pecahan 5 per 4 selesai pecahan",
            r"$\frac{1}{\frac{2}{3}}$": "pecahan 1 per pecahan 2 per 3 selesai pecahan selesai pecahan",
            r"$2x + 3 = 9$": "2 kali x tambah 3 sama dengan 9",
            r"$\sqrt{16} = 4$ dan $x^{10}$": "akar dari 16 selesai akar sama dengan 4 dan x pangkat 10",
            "5^12": "5 pangkat 12",
        }
        for text, expected in samples.items():
            with self.subTest(text=text):
                self.assertEqual(tts.prepare_speech_text(text), expected)

        class FailedEdge:
            def __init__(self, text, voice):
                self.text = text
            async def stream(self):
                raise RuntimeError("offline")
                yield

        with patch.object(tts, "edge_tts", SimpleNamespace(Communicate=FailedEdge)), \
             patch.object(tts, "_gtts_audio", return_value=b"audio") as fallback:
            self.assertEqual(await tts.text_to_speech("2 + 3 = 5"), b"audio")
            fallback.assert_called_once_with("2 tambah 3 sama dengan 5", "id")


if __name__ == "__main__":
    unittest.main()
