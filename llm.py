"""
llm.py
======
Pembungkus tipis (thin wrapper) untuk memanggil Anthropic API (Claude Haiku 4.5).
Kalau nanti mau ganti model, cukup ubah MODEL_NAME di sini.
"""

import base64
import io
import logging
import os
import re
from pathlib import Path

from anthropic import Anthropic, APIError, APIConnectionError

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500
MATERIALS_DIR = Path(__file__).parent / "materials"
SECRETS_DIR = Path("/etc/secrets")

# Knowledge base gambar: tangkapan layar materi buku yang diisi orang tua/guru.
# Format mengikuti dukungan vision Anthropic; batas jumlah & ukuran menjaga
# request tetap di bawah batas API (32 MB) dan biaya token tetap wajar.
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_MATERIAL_IMAGES = 8
MAX_MATERIAL_IMAGE_BYTES = 2_500_000  # ~2,5 MB per gambar

# PDF materi (mis. hasil scan halaman buku). Claude membaca tiap halaman sebagai
# teks + gambar, jadi PDF scan tetap berguna. Batas halaman ada di sisi API
# (100 halaman untuk context <1M token), jadi pakai PDF ringkas per topik.
MAX_MATERIAL_PDFS = 2
MAX_MATERIAL_PDF_BYTES = 8_000_000  # ~8 MB per PDF

# Kompresi otomatis screenshot. Batas ini sama dengan batas baca Anthropic
# (~1,15 MP, sisi terpanjang 1568 px) supaya teks tetap tajam; token gambar
# dihitung dari piksel, jadi gambar besar tidak memakan puluhan ribu token.
MATERIAL_IMAGE_MAX_EDGE = 1568
MATERIAL_IMAGE_MAX_PIXELS = 1_150_000
MATERIAL_IMAGE_JPEG_QUALITY = 85
MATERIAL_IMAGE_MAX_SOURCE_BYTES = 20_000_000  # batas file mentah yang dibaca

logger = logging.getLogger(__name__)
_image_block_cache: dict = {}
_pdf_block_cache: dict = {}
_client = None


def _strip_markdown(text: str) -> str:
    """
    Bersihkan sisa-sisa simbol Markdown dari balasan, untuk jaga-jaga kalau
    Claude sesekali masih menulis **tebal**, # judul, atau --- garis pemisah
    meski sudah diinstruksikan untuk tidak memakainya. Bot mengirim pesan
    sebagai teks polos (tanpa parse_mode), jadi simbol mentah akan terlihat
    berantakan kalau tidak dibersihkan di sini. Ini jaring pengaman di level
    kode, bukan cuma mengandalkan kepatuhan model terhadap system prompt.
    """
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)              # # Judul -> Judul
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)        # --- -> (hilang)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)              # **tebal** -> tebal
    text = re.sub(r"__(.+?)__", r"\1", text)                  # __tebal__ -> tebal
    text = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)  # *miring* -> miring
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)    # _miring_ -> miring
    text = re.sub(r"`([^`]+)`", r"\1", text)                  # `kode` -> kode
    text = re.sub(r"\n{3,}", "\n\n", text)                    # rapikan baris kosong berlebih
    return text.strip()


def _load_material(subject_key: str) -> str:
    """
    Baca materi buku cetak yang sudah dikurasi untuk mata pelajaran ini.
    Dicari di dua lokasi (yang manapun ditemukan duluan dipakai):
      1. materials/<subject_key>.md   -> dipakai saat bot jalan lokal di laptop.
      2. /etc/secrets/<subject_key>.md -> dipakai saat bot jalan di Render,
         diisi lewat fitur "Secret Files" di dashboard Render (bukan lewat
         GitHub), supaya materi buku tetap privat.
    Kembalikan string kosong kalau tidak ditemukan di keduanya, atau kalau
    isinya masih placeholder (bot tetap jalan normal, cuma tanpa acuan buku).
    """
    candidates = [
        MATERIALS_DIR / f"{subject_key}.md",
        SECRETS_DIR / f"{subject_key}.md",
    ]
    for path in candidates:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text.startswith("<!--") and text.endswith("-->"):
                continue
            return text
    return ""


def _material_paths(subject_key: str, kind: str):
    """Lokasi file materi gambar/PDF untuk pelajaran ini, urut nama file.

    kind: "images" atau "pdf". Pencarian:
      1. materials/<kind>/<subject_key>/        -> lokal / laptop.
      2. /etc/secrets/<kind>/<subject_key>/     -> Render (jika ada folder).
      3. /etc/secrets/<subject_key>__*          -> Render Secret Files yang datar,
         mis. zoologi__01.png atau zoologi__materi.pdf.
    """
    paths = []
    for base in (MATERIALS_DIR, SECRETS_DIR):
        folder = base / kind / subject_key
        if folder.is_dir():
            paths.extend(sorted(p for p in folder.iterdir() if p.is_file()))
    if SECRETS_DIR.is_dir():
        paths.extend(sorted(SECRETS_DIR.glob(f"{subject_key}__*")))
    return paths


def _prepare_image(data: bytes, media_type: str):
    """Perkecil & kompres gambar materi bila perlu; return (bytes, media_type).

    Gambar besar diperkecil ke maksimal MATERIAL_IMAGE_MAX_EDGE (sisi terpanjang)
    dan MATERIAL_IMAGE_MAX_PIXELS, lalu diubah ke JPEG kualitas 85 tanpa metadata.
    Gambar yang sudah kecil dan ringan dibiarkan apa adanya. Kalau Pillow tidak
    tersedia atau gambarnya rusak, data asli dikembalikan agar bot tetap jalan.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow tidak tersedia — gambar materi dikirim tanpa kompresi")
        return data, media_type

    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            needs_resize = (
                max(width, height) > MATERIAL_IMAGE_MAX_EDGE
                or width * height > MATERIAL_IMAGE_MAX_PIXELS
            )
            if not needs_resize and len(data) <= MAX_MATERIAL_IMAGE_BYTES:
                return data, media_type

            img = ImageOps.exif_transpose(img)
            if getattr(img, "is_animated", False):
                img.seek(0)  # animasi (GIF): cukup frame pertama
            # Latar putih supaya PNG transparan tidak jadi hitam setelah di-JPEG.
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            img = background

            width, height = img.size
            scale = min(
                1.0,
                MATERIAL_IMAGE_MAX_EDGE / max(width, height),
                (MATERIAL_IMAGE_MAX_PIXELS / (width * height)) ** 0.5,
            )
            if scale < 1.0:
                img = img.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.LANCZOS,
                )

            out = io.BytesIO()
            img.save(
                out, format="JPEG",
                quality=MATERIAL_IMAGE_JPEG_QUALITY, optimize=True,
            )
            compressed = out.getvalue()
    except Exception as e:
        logger.warning("Gagal mengompres gambar materi: %s", e)
        return data, media_type

    return (compressed, "image/jpeg") if compressed else (data, media_type)


def _load_material_images(subject_key: str) -> list:
    """Ubah gambar materi menjadi blok image untuk Anthropic API.

    Gambar besar dikompres lewat _prepare_image, lalu hasil base64-nya di-cache
    per file (mtime + ukuran) supaya tidak dikompres ulang di setiap pesan.
    File yang formatnya tidak didukung, kosong, atau masih terlalu besar setelah
    dikompres dilewati dengan peringatan di log — bot tetap menjawab dengan teks
    materi biasa. Maksimal MAX_MATERIAL_IMAGES gambar.
    """
    blocks = []
    seen = set()
    for path in _material_paths(subject_key, "images"):
        media_type = IMAGE_TYPES.get(path.suffix.lower())
        if not media_type or path in seen:
            continue
        seen.add(path)
        if len(blocks) >= MAX_MATERIAL_IMAGES:
            logger.warning(
                "Materi gambar %s dilewati: batas %s gambar per pelajaran",
                subject_key, MAX_MATERIAL_IMAGES,
            )
            break
        try:
            stat = path.stat()
        except OSError as e:
            logger.warning("Gagal membaca gambar materi %s: %s", path, e)
            continue
        if stat.st_size > MATERIAL_IMAGE_MAX_SOURCE_BYTES:
            logger.warning(
                "Gambar materi %s dilewati: %.1f MB (maks sumber %.1f MB)",
                path, stat.st_size / 1_000_000,
                MATERIAL_IMAGE_MAX_SOURCE_BYTES / 1_000_000,
            )
            continue

        cache_key = (
            str(path), stat.st_mtime_ns, stat.st_size,
            MATERIAL_IMAGE_MAX_EDGE, MATERIAL_IMAGE_MAX_PIXELS,
            MATERIAL_IMAGE_JPEG_QUALITY,
        )
        cached = _image_block_cache.get(cache_key)
        if cached is None:
            try:
                data = path.read_bytes()
            except OSError as e:
                logger.warning("Gagal membaca gambar materi %s: %s", path, e)
                continue
            if not data:
                continue
            data, media_type = _prepare_image(data, media_type)
            if len(data) > MAX_MATERIAL_IMAGE_BYTES:
                logger.warning(
                    "Gambar materi %s dilewati: %.1f MB setelah dikompres "
                    "(maks %.1f MB)",
                    path, len(data) / 1_000_000,
                    MAX_MATERIAL_IMAGE_BYTES / 1_000_000,
                )
                continue
            cached = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
            if len(_image_block_cache) >= 64:
                _image_block_cache.clear()  # cegah cache tumbuh tanpa batas
            _image_block_cache[cache_key] = cached
        # Salin dict: cache_control ditempel ke salinan oleh get_ai_reply.
        blocks.append(dict(cached))
    return blocks


def _load_material_pdfs(subject_key: str) -> list:
    """Ubah PDF materi menjadi blok document untuk Anthropic API.

    Claude mengekstrak teks dan mengubah tiap halaman PDF menjadi gambar, jadi
    PDF hasil scan (materi berupa tangkapan layar) tetap terbaca. Hasil base64
    di-cache per file agar tidak di-encode ulang di setiap pesan. File yang
    bukan PDF, kosong, atau lebih besar dari MAX_MATERIAL_PDF_BYTES dilewati.
    """
    blocks = []
    seen = set()
    for path in _material_paths(subject_key, "pdf"):
        if path.suffix.lower() != ".pdf" or path in seen:
            continue
        seen.add(path)
        if len(blocks) >= MAX_MATERIAL_PDFS:
            logger.warning(
                "Materi PDF %s dilewati: batas %s PDF per pelajaran",
                subject_key, MAX_MATERIAL_PDFS,
            )
            break
        try:
            stat = path.stat()
        except OSError as e:
            logger.warning("Gagal membaca PDF materi %s: %s", path, e)
            continue
        if stat.st_size > MAX_MATERIAL_PDF_BYTES:
            logger.warning(
                "PDF materi %s dilewati: %.1f MB (maks %.1f MB)",
                path, stat.st_size / 1_000_000,
                MAX_MATERIAL_PDF_BYTES / 1_000_000,
            )
            continue

        cache_key = ("pdf", str(path), stat.st_mtime_ns, stat.st_size)
        cached = _pdf_block_cache.get(cache_key)
        if cached is None:
            try:
                data = path.read_bytes()
            except OSError as e:
                logger.warning("Gagal membaca PDF materi %s: %s", path, e)
                continue
            if not data:
                continue
            cached = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
            if len(_pdf_block_cache) >= 16:
                _pdf_block_cache.clear()  # cegah cache tumbuh tanpa batas
            _pdf_block_cache[cache_key] = cached
        # Salin dict: cache_control ditempel ke salinan oleh get_ai_reply.
        blocks.append(dict(cached))
    return blocks


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY tidak ditemukan. Cek file .env kamu."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def get_ai_reply(subject_key: str, system_prompt: str, history: list, user_message: str) -> str:
    """
    subject_key   : key mata pelajaran (dipakai untuk cari file materials/<subject_key>.md)
    system_prompt : instruksi guru untuk mata pelajaran yang sedang aktif
    history       : list pesan sebelumnya, format [{"role": "user"/"assistant", "content": "..."}]
    user_message  : pesan baru dari anak

    Return: string balasan dari Claude, atau pesan error ramah-anak kalau gagal.
    """
    client = _get_client()
    messages = history + [{"role": "user", "content": user_message}]

    # Materi (PDF/gambar) ditaruh di AWAL percakapan, bukan di pesan terbaru,
    # supaya cache Anthropic tetap berlaku walau riwayat obrolan terus bertambah.
    # PDF diletakkan sebelum teks (anjuran Anthropic), gambar setelah teks.
    material_pdfs = _load_material_pdfs(subject_key)
    material_images = _load_material_images(subject_key)
    if material_pdfs or material_images:
        material_blocks = material_pdfs + [
            {
                "type": "text",
                "text": (
                    "MATERI RUJUKAN DARI BUKU (berupa gambar dan/atau PDF). "
                    "Baca isi materi berikut, lalu gunakan untuk menjawab pertanyaan "
                    "anak bila relevan. Jangan menyebut bahwa kamu sedang melihat "
                    "gambar atau PDF; cukup jelaskan isinya dengan bahasa sederhana."
                ),
            }
        ] + material_images
        # Cache seluruh blok materi agar tidak diproses ulang di setiap pesan.
        material_blocks[-1]["cache_control"] = {"type": "ephemeral"}
        messages = [
            {"role": "user", "content": material_blocks},
        ] + history + [{"role": "user", "content": user_message}]

    # Susun system prompt sebagai list of blocks. Blok materi ditandai
    # cache_control supaya Anthropic tidak memproses ulang teks materi
    # yang sama di setiap pesan (jauh lebih hemat & lebih cepat).
    system_blocks = [{"type": "text", "text": system_prompt}]
    material_text = _load_material(subject_key)
    if material_text:
        system_blocks.append(
            {
                "type": "text",
                "text": (
                    "MATERI RUJUKAN DARI BUKU CETAK SEKOLAH (jawab berdasarkan isi ini "
                    "kalau relevan dengan pertanyaan anak):\n\n" + material_text
                ),
                "cache_control": {"type": "ephemeral"},
            }
        )

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=messages,
        )
        # response.content adalah list block; ambil semua block teks
        text_parts = [block.text for block in response.content if block.type == "text"]
        reply = "\n".join(text_parts).strip()
        reply = _strip_markdown(reply)
        return reply or "Hmm, Kak Moana belum bisa jawab itu. Coba tanya dengan cara lain, ya! 😊"

    except APIConnectionError:
        return "Wah, koneksi Kak Moana lagi bermasalah. Coba kirim lagi sebentar lagi ya! 🌐"
    except APIError as e:
        return f"Maaf ya, Kak Moana lagi ada gangguan kecil ({e.status_code}). Coba lagi sebentar ya! 🙏"
    except Exception:
        return "Ups, ada yang tidak beres di sistem Kak Moana. Coba kirim pesannya lagi ya! 🙏"
