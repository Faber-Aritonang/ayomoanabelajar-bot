"""Text-to-speech untuk balasan suara bot Telegram."""

import asyncio
import logging
import os
import re
import tempfile
import uuid
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import edge_tts
except ImportError:
    edge_tts = None
    logger.info("Edge TTS tidak tersedia")

try:
    from gtts import gTTS
except ImportError:
    gTTS = None
    logger.info("gTTS tidak tersedia")


def _read_math_block(text: str) -> str:
    """Bacakan rumus yang secara eksplisit ditandai sebagai matematika."""
    for command, spoken in {
        r"\times": " kali ", r"\cdot": " kali ", r"\div": " dibagi ",
        r"\leq": " lebih kecil atau sama dengan ", r"\geq": " lebih besar atau sama dengan ",
    }.items():
        text = text.replace(command, spoken)

    # Ulangi untuk pecahan/akar bersarang yang memakai kurung kurawal seimbang.
    fraction = r"\\(?:dfrac|tfrac|frac)\{([^{}]*)\}\{([^{}]*)\}"
    root = r"\\sqrt\{([^{}]*)\}"
    while re.search(fraction, text) or re.search(root, text):
        text = re.sub(fraction, r" pecahan \1 per \2 selesai pecahan ", text)
        text = re.sub(root, r" akar dari \1 selesai akar ", text)
    text = re.sub(r"\^\{([^{}]+)\}", r" pangkat \1 ", text)
    text = re.sub(r"\^([\w]+)", r" pangkat \1 ", text)
    text = re.sub(r"(?<=\d)(?=[a-zA-Z](?![a-zA-Z]))", " kali ", text)
    operators = {
        "+": "tambah", "-": "kurang", "−": "kurang", "×": "kali",
        "*": "kali", "÷": "dibagi", "/": "per", "=": "sama dengan",
        "<": "lebih kecil dari", ">": "lebih besar dari",
    }
    text = re.sub(r"[+\-−×*÷/=<>]", lambda m: f" {operators[m.group()]} ", text)
    text = text.replace("(", " buka kurung ").replace(")", " tutup kurung ")
    return re.sub(r"\s+", " ", text).strip()


def prepare_speech_text(text: str) -> str:
    """Siapkan pelafalan matematika hanya untuk suara; teks asli tidak berubah."""
    # Blok LaTeX eksplisit juga boleh memuat variabel dan pecahan bersarang.
    text = re.sub(
        r"\$\$(.+?)\$\$|\$(?!\s)([^$\n]+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]",
        lambda m: _read_math_block(next(group for group in m.groups() if group is not None)),
        text, flags=re.DOTALL,
    )
    # Notasi LaTeX umum juga sering muncul tanpa pembatas dolar.
    text = re.sub(
        r"\\(?:dfrac|tfrac|frac)\{[^{}]*\}\{[^{}]*\}|\\sqrt\{[^{}]*\}",
        lambda m: _read_math_block(m.group()), text,
    )
    # Pecahan campuran, misalnya 1 1/2 = satu dan satu per dua.
    text = re.sub(r"(?<![\w./])(\d+)\s+(\d+/\d+)(?![\w/])", r"\1 dan \2", text)
    # Kurung pada ekspresi numerik dibaca agar urutan operasi tetap jelas.
    text = re.sub(
        r"\((?=[\d\s()+*/×÷−=<>.\-]*\d)[\d\s()+*/×÷−=<>.\-]+\)",
        lambda m: _read_math_block(m.group()), text,
    )
    operators = {
        "+": "tambah", "-": "kurang", "−": "kurang",
        "×": "kali", "x": "kali", "*": "kali",
        "÷": "dibagi", ":": "dibagi", "/": "per",
        "=": "sama dengan", "<": "lebih kecil dari", ">": "lebih besar dari",
    }
    text = re.sub(
        r"(?<=tutup kurung)\s*([+\-−×x*÷:/=<>])\s*(?=\d)",
        lambda m: f" {operators[m.group(1)]} ", text,
    )
    number = r"\d+(?:[.,]\d+)?"
    expression = rf"(?<![\w./]){number}(?:\s*[+\-−×x*÷:/=<>]\s*{number})+(?![\w/]|\.\d)"

    def read_expression(match):
        value = match.group()
        # Jangan mengubah tanggal atau waktu yang lazim ditulis tanpa spasi.
        if (re.fullmatch(r"\d{1,4}[/\-]\d{1,2}[/\-]\d{1,4}", value)
                or re.fullmatch(r"\d{1,2}:\d{2}", value)):
            return value
        return re.sub(
            r"\s*([+\-−×x*÷:/=<>])\s*",
            lambda op: f" {operators[op.group(1)]} ",
            value,
        )

    text = re.sub(expression, read_expression, text)
    text = re.sub(r"(?<=\d)\s*(?:\^2|²)(?!\d)", " pangkat dua", text)
    text = re.sub(r"(?<=\d)\s*(?:\^3|³)(?!\d)", " pangkat tiga", text)
    text = re.sub(r"(?<=\d)\s*\^(\d+)", r" pangkat \1", text)
    text = re.sub(r"(?<=\d)\s*%", " persen", text)
    return text


def _gtts_audio(text: str, language: str) -> bytes:
    buffer = BytesIO()
    gTTS(text=text, lang=language, slow=False).write_to_fp(buffer)
    return buffer.getvalue()


async def text_to_speech(
    text: str, language: str = "id", voice: str = "id-ID-GadisNeural"
) -> Optional[bytes]:
    """Ubah teks menjadi MP3: Edge TTS dahulu, lalu gTTS jika gagal."""
    if not text or not text.strip():
        logger.warning("Teks kosong")
        return None
    text = prepare_speech_text(text.strip())

    if edge_tts is not None:
        try:
            chunks = []
            async for chunk in edge_tts.Communicate(text, voice).stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            audio_bytes = b"".join(chunks)
            if not audio_bytes:
                raise ValueError("Edge TTS menghasilkan audio kosong")
            logger.info("Edge TTS berhasil (%s bytes)", len(audio_bytes))
            return audio_bytes
        except Exception as e:
            logger.warning("Edge TTS gagal, mencoba gTTS: %s", e)

    if gTTS is not None:
        try:
            audio_bytes = await asyncio.to_thread(_gtts_audio, text, language)
            if not audio_bytes:
                raise ValueError("gTTS menghasilkan audio kosong")
            logger.info("gTTS fallback berhasil (%s bytes)", len(audio_bytes))
            return audio_bytes
        except Exception as e:
            logger.error("gTTS gagal: %s", e)

    logger.error("Tidak ada TTS yang berhasil")
    return None


def is_tts_available() -> bool:
    """Cek apakah setidaknya satu library TTS terpasang."""
    return edge_tts is not None or gTTS is not None


def create_voice_file(audio_bytes: bytes, filename: str = "voice.mp3") -> str:
    """Buat file temporary untuk dikirim sebagai voice note."""
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"telegram_voice_{uuid.uuid4().hex}.mp3")

    with open(temp_path, "wb") as f:
        f.write(audio_bytes)

    logger.debug("Buat file voice di %s", temp_path)
    return temp_path
