"""
quiz.py
=======
Logika **Kuis Adaptif** bersama untuk bot Telegram & WhatsApp.

Alur kerja:
1. ``start_quiz`` menyiapkan soal pilihan ganda (A–D) lewat AI. AI diminta
   menulis kunci jawaban di baris "KUNCI: X"; baris itu di-parse lalu dihapus
   dari teks yang ditampilkan ke anak (kunci tetap rahasia).
2. Saat anak menjawab, ``answer_quiz`` mengevaluasi jawaban secara rule-based
   (mencari huruf A–D pada jawaban anak). **Benar = +10 poin, salah = +0.**
3. Satu sesi maksimal 5 soal. Setelah selesai, skor dikembalikan agar bot
   menyimpannya ke tabel ``quiz_scores`` lewat ``database.save_quiz_score``.

Modul ini murni (pure): hanya bekerja pada dict state yang diberikan, jadi
bisa dipakai oleh `context.user_data` (Telegram) maupun `_user_states`
(WhatsApp) tanpa perubahan.
"""

import re

from llm import get_ai_reply

MAX_QUESTIONS = 5        # jumlah soal per sesi kuis
POINTS_CORRECT = 10      # poin untuk jawaban benar

# Baris kunci jawaban dari AI, mis. "KUNCI: B" / "Kunci jawaban: C".
_KUNCI_RE = re.compile(r"(?i)^(?:kunci|kunci jawaban|jawaban(?: benar)?)\s*:?\s*([a-d])\b")
# Fallback: kunci yang ditulis AI tidak di awal baris / format lain, mis.
# "Kunci jawabannya adalah B" atau "kunci: B" di tengah teks.
_KUNCI_ANYWHERE_RE = re.compile(r"(?i)kunci(?:\s*jawaban)?(?:nya)?\s*(?:adalah|yaitu|:\s*|\s*-\s*)\s*([a-d])\b")
# Huruf jawaban pada jawaban anak, mis. "B", "b.", "jawabannya C".
_ANSWER_RE = re.compile(r"(?i)(?:jawaban(?:ku|nya)?\s*(?:adalah|yaitu)?\s*[:.\-]?\s*)?\b([a-d])\b")


def _parse_question(raw: str):
    """Pisahkan teks soal dari baris kunci jawaban.

    Return: (teks_soal, huruf_kunci) — kunci None kalau AI tidak menulis KUNCI.
    """
    key = None
    kept = []
    for line in (raw or "").splitlines():
        m = _KUNCI_RE.match(line.strip())
        if m:
            key = m.group(1).upper()
            continue
        # Safety net: buang baris yang ternyata berisi kunci jawaban dalam
        # format apa pun, agar kunci tidak pernah bocor ke soal yang tampil.
        fallback = _KUNCI_ANYWHERE_RE.search(line)
        if fallback:
            if key is None:
                key = fallback.group(1).upper()
            continue
        kept.append(line)
    return "\n".join(kept).strip(), key


def _ask_question(subject_key: str, subject: dict, history: list) -> str:
    """Minta AI membuat 1 soal pilihan ganda (dengan kunci tersembunyi)."""
    subject_name = subject["name"]
    prompt = (
        f"Buatkan 1 soal latihan pilihan ganda untuk mata pelajaran {subject_name} "
        "untuk anak kelas 3 SD. Berikan 4 pilihan jawaban berlabel A, B, C, dan D.\n\n"
        "INSTRUKSI ADAPTIF PENTING: Evaluasi pemahaman anak dari riwayat obrolan "
        "yang diberikan. Jika anak sering salah atau bingung, berikan soal yang "
        "lebih dasar dan mudah. Jika anak menjawab dengan cepat dan benar, "
        "berikan soal yang 1 tingkat lebih sulit (Level Up).\n\n"
        "Format jawaban:\n"
        "- Tulis soal dan pilihan A sampai D.\n"
        "- Di baris PALING AKHIR, tulis persis: KUNCI: X  (ganti X dengan huruf "
        "jawaban yang benar: A, B, C, atau D).\n"
        "- JANGAN sebut kunci jawaban di bagian soal maupun pilihan jawaban."
    )
    return get_ai_reply(subject_key, subject["system_prompt"], history, prompt)


def start_quiz(state: dict, subject_key: str, subject: dict, history: list, retries: int = 2):
    """Mulai sesi kuis baru (atau siapkan soal berikutnya dalam sesi aktif).

    Mengisi ``state["quiz"]`` dengan konteks sesi (subject, soal, kunci, skor).

    Return: teks soal (tanpa kunci) yang siap ditampilkan, atau None jika AI
    gagal menyiapkan soal (state kuis dibersihkan).
    """
    existing = state.get("quiz") or {}
    state["quiz"] = {
        "subject": subject_key,
        "score": existing.get("score", 0),
        "total": existing.get("total", 0),
    }

    for _ in range(max(1, retries)):
        raw = _ask_question(subject_key, subject, history)
        question, key = _parse_question(raw)
        if key:
            quiz = state["quiz"]
            quiz["question"] = question
            quiz["key"] = key
            return question

    # Gagal menyiapkan soal. Kalau ini sesi BARU (belum ada soal dijawab),
    # bersihkan state. Kalau di tengah sesi, pertahankan skor yang sudah
    # dikumpulkan anak — biarkan state tetap sehingga jawaban berikutnya
    # tetap dievaluasi terhadap soal yang sedang aktif.
    quiz = state.get("quiz") or {}
    if not quiz.get("total"):
        state.pop("quiz", None)
    return None


def answer_quiz(state: dict, answer_text: str):
    """Evaluasi jawaban anak terhadap soal kuis yang sedang aktif.

    Return: (feedback_text, next_question_or_None, summary_or_None)
    - feedback_text      : pesan hasil jawaban (benar/salah + skor berjalan).
    - next_question_or_None: "NEXT" kalau harus lanjut ke soal berikutnya,
      None kalau sesi selesai / jawaban tidak valid.
    - summary_or_None    : dict {"score": int, "total": int} saat sesi selesai,
      None sebaliknya — bot memakainya untuk menyimpan skor ke database.

    Kalau tidak ada kuis aktif, return (None, None, None).
    """
    quiz = state.get("quiz")
    if not quiz:
        return None, None, None

    m = _ANSWER_RE.search(answer_text or "")
    if not m:
        return (
            "Aku belum paham jawabanmu, Adik. Ketik hurufnya saja ya, "
            "misalnya *B* atau *C*. 😊",
            None,
            None,
        )

    letter = m.group(1).upper()
    correct = letter == quiz["key"]
    if correct:
        quiz["score"] += POINTS_CORRECT
    quiz["total"] += 1

    lines = []
    if correct:
        lines.append(f"🎉 *BENAR!* +{POINTS_CORRECT} poin 🎉")
    else:
        lines.append(f"Belum tepat, Adik. Jawaban yang benar adalah *{quiz['key']}*. Tetap semangat! 💪")
    lines.append(f"Skor kamu: *{quiz['score']}* poin (soal ke-{quiz['total']} dari {MAX_QUESTIONS}).")

    if quiz["total"] >= MAX_QUESTIONS:
        score = quiz["score"]
        total = quiz["total"]
        state.pop("quiz", None)
        lines.append("")
        lines.append(
            f"🏁 *Kuis selesai!* Skor akhir kamu: *{score}* dari "
            f"{MAX_QUESTIONS * POINTS_CORRECT} poin. "
            "Hebat sudah berlatih! Ketik *kuis* lagi kapan saja ya! 🚀"
        )
        return "\n".join(lines), None, {"score": score, "total": total}

    lines.append("")
    lines.append("Soal berikutnya:")
    return "\n".join(lines), "NEXT", None
