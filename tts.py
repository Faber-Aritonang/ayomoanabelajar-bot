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

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"

# Pilihan suara disimpan di database dengan nama Edge TTS lama. Pemetaan ini
# menjaga preferensi pengguna yang sudah ada tetap berlaku setelah pindah ke
# ElevenLabs, sekaligus menjadi cadangan bila ElevenLabs tidak dikonfigurasi.
EDGE_VOICES = {"perempuan": "id-ID-GadisNeural", "laki-laki": "id-ID-ArdiNeural"}
VOICE_KEYS = {edge: key for key, edge in EDGE_VOICES.items()}

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


def voice_choice(voice: str) -> str:
    """Ubah nama suara lama atau baru menjadi kunci "perempuan"/"laki-laki"."""
    value = (voice or "").strip()
    if value in EDGE_VOICES:
        return value
    return VOICE_KEYS.get(value, "perempuan")


def _env_value(name: str) -> str:
    """Baca env dan buang spasi serta kutip yang ikut ter-paste."""
    value = os.getenv(name, "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _elevenlabs_voice_id(choice: str) -> str:
    env_name = "ELEVENLABS_VOICE_ID_MALE" if choice == "laki-laki" else "ELEVENLABS_VOICE_ID_FEMALE"
    return _env_value(env_name)


def elevenlabs_status(choice: str) -> tuple[bool, str]:
    """Cek kesiapan ElevenLabs tanpa membocorkan isi API key."""
    if not _env_value("ELEVENLABS_API_KEY"):
        return False, "ELEVENLABS_API_KEY kosong"
    voice_id = _elevenlabs_voice_id(choice)
    if not voice_id:
        env_name = "ELEVENLABS_VOICE_ID_MALE" if choice == "laki-laki" else "ELEVENLABS_VOICE_ID_FEMALE"
        return False, f"{env_name} kosong"
    return True, _env_value("ELEVENLABS_MODEL_ID") or ELEVENLABS_DEFAULT_MODEL


def voice_engine(choice: str) -> str:
    """Nama mesin yang akan dipakai untuk pilihan suara ini."""
    return "ElevenLabs" if elevenlabs_status(choice)[0] else "Edge TTS"


def log_elevenlabs_status() -> None:
    """Catat kesiapan ElevenLabs saat bot mulai, tanpa menampilkan secret."""
    for choice in EDGE_VOICES:
        ready, info = elevenlabs_status(choice)
        if ready:
            logger.info("TTS %s: ElevenLabs aktif (model %s)", choice, info)
        else:
            logger.warning("TTS %s: ElevenLabs nonaktif (%s), memakai Edge TTS", choice, info)


def _elevenlabs_config(choice: str) -> tuple[str, str, str] | None:
    """Kembalikan (api_key, voice_id, model_id), atau None bila belum diisi."""
    api_key = _env_value("ELEVENLABS_API_KEY")
    voice_id = _elevenlabs_voice_id(choice)
    if not api_key or not voice_id:
        return None
    model_id = _env_value("ELEVENLABS_MODEL_ID") or ELEVENLABS_DEFAULT_MODEL
    return api_key, voice_id, model_id


async def _elevenlabs_audio(text: str, voice_id: str, api_key: str, model_id: str) -> bytes:
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ELEVENLABS_TTS_URL}/{voice_id}",
            params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
            headers={"xi-api-key": api_key},
            json={"text": text, "model_id": model_id},
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", {})
                message = detail.get("message") if isinstance(detail, dict) else detail
            except Exception:
                message = response.text[:200]
            raise RuntimeError(f"HTTP {response.status_code}: {message or 'tanpa detail'}")
        audio_bytes = response.content
    if not audio_bytes:
        raise ValueError("ElevenLabs menghasilkan audio kosong")
    return audio_bytes


async def text_to_speech(
    text: str, language: str = "id", voice: str = "id-ID-GadisNeural"
) -> Optional[bytes]:
    """Ubah teks menjadi MP3: ElevenLabs, lalu Edge TTS, lalu gTTS."""
    if not text or not text.strip():
        logger.warning("Teks kosong")
        return None
    text = prepare_speech_text(text.strip())
    choice = voice_choice(voice)

    config = _elevenlabs_config(choice)
    if config:
        api_key, voice_id, model_id = config
        try:
            audio_bytes = await _elevenlabs_audio(text, voice_id, api_key, model_id)
            logger.info("ElevenLabs berhasil (%s bytes, suara %s)", len(audio_bytes), choice)
            return audio_bytes
        except Exception as e:
            logger.warning("ElevenLabs gagal, memakai Edge TTS: %s", e)

    if edge_tts is not None:
        try:
            chunks = []
            async for chunk in edge_tts.Communicate(text, EDGE_VOICES[choice]).stream():
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
    """Cek apakah setidaknya satu mesin TTS siap dipakai."""
    if edge_tts is not None or gTTS is not None:
        return True
    return bool(
        _env_value("ELEVENLABS_API_KEY")
        and (_elevenlabs_voice_id("perempuan") or _elevenlabs_voice_id("laki-laki"))
    )


def create_voice_file(audio_bytes: bytes, filename: str = "voice.mp3") -> str:
    """Buat file temporary untuk dikirim sebagai voice note."""
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"telegram_voice_{uuid.uuid4().hex}.mp3")

    with open(temp_path, "wb") as f:
        f.write(audio_bytes)

    logger.debug("Buat file voice di %s", temp_path)
    return temp_path
