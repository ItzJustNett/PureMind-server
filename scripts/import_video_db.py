#!/usr/bin/env python3
"""
Import video_db.json into PostgreSQL lessons/courses tables.

Parses grade and subject from Ukrainian video titles, generates deterministic
lesson_id slugs, and upserts into Postgres. Idempotent — safe to re-run.

Usage:
    python3 scripts/import_video_db.py [--dry-run]
"""

import json
import logging
import re
import sys
from pathlib import Path

# Add server root to path so we can import database modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from database import SessionLocal
from database.models import Course, Lesson

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Path to video_db.json (sibling folder) ────────────────────────────────────
VIDEO_DB_PATH = Path(__file__).parent.parent.parent / "New search model" / "video_db.json"

# ── Cyrillic → Latin transliteration (matches SUBJECT_NAMES keys in page.tsx) ─
TRANSLIT = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'h',  'ґ': 'g',  'д': 'd',
    'е': 'e',  'є': 'ye', 'ж': 'zh', 'з': 'z',  'и': 'y',  'і': 'i',
    'ї': 'yi', 'й': 'y',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
    'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',  'у': 'u',
    'ф': 'f',  'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ь': '',   'ю': 'yu', 'я': 'ya', 'ъ': '',   'ё': 'yo', 'э': 'e',
    "ʼ": '',   "'": '',   "'": '',   "′": '',
}

# ── Subject name (Ukrainian) → course slug (must match SUBJECT_NAMES in page.tsx) ─
SUBJECT_MAP = {
    "Українська мова":                      "ukrayinska-mova",
    "Кримськотатарська мова та література":  "krymskotатarska-mova",
    "Англійська мова":                      "anhliyska-mova",
    "Алгебра і початки аналізу":            "alhebra-i-pochatky-analizu",
    "Алгебра і початки математичного аналізу": "alhebra-i-pochatky-analizu",
    "Алгебра":                              "alhebra-i-pochatky-analizu",
    "Основи здоров'я":                      "osnovy-zdorovya",
    "Основи здоровя":                       "osnovy-zdorovya",
    "Біологія і екологія":                  "biolohiya-i-ekolohiya",
    "Біологія":                             "biolohiya-i-ekolohiya",
    "Українська література":                "ukrayinska-literatura",
    "Географія":                            "heohrafiya",
    "Фізика":                               "fizyka",
    "Хімія":                                "khimiya",
    "Геометрія":                            "heometriya",
    "Математика":                           "matematyka",
    "Всесвітня історія":                    "vsesvitnya-istoriya",
    "Зарубіжна література":                 "zarubizhna-literatura",
    "Мистецтво":                            "mystetstvo",
    "Технології":                           "tekhnolohiyi",
    "Природознавство":                      "pryrodoznavstvo",
    "Інформатика":                          "informatyka",
    "Громадянська освіта":                  "hromadyanska-osvita",
    "Іноземна мова":                        "anhliyska-mova",
    "Суспільствознавство":                  "suspilstvoznavstvo",
    "Правознавство":                        "pravoznavstvo",
    "Основи правознавства":                 "pravoznavstvo",
    "Зарубіжна":                            "zarubizhna-literatura",
    "Трудове навчання":                     "trudove-navchannya",
    "Музичне мистецтво":                    "muzychne-mystetstvo",
    "Образотворче мистецтво":               "obrazotvorche-mystetstvo",
    "Інтегрований курс":                    "intehrovanyy-kurs",
    "Правознавство (практичний курс)":      "pravoznavstvo",
    "Фізична культура":                     "fizychna-kultura",
    "Захист України":                       "zakhyst-ukrayiny",
    "Економіка":                            "ekonomika",
    "Астрономія":                           "astronomiya",
    "Фізика і астрономія":                  "fizyka",
    "Іноземна мова (англійська)":           "anhliyska-mova",
    "Іноземна мова (французька)":          "frantsuzka-mova",
    "Іноземна мова (німецька)":            "nimetska-mova",
    "Іноземна мова (іспанська)":           "ispanska-mova",
    "Українознавство":                      "ukrayinoznavstvo",
}

# ── Regex to extract grade + subject from title ────────────────────────────────
# Matches: "10 клас. Фізика. Тема уроку..." or "7 клас, Алгебра. ..."
TITLE_REGEX = re.compile(
    r"^\s*(\d+)\s*клас[.,]?\s*(.+?)(?:\.\s|\.$|$)",
    re.IGNORECASE,
)


def slugify(text: str) -> str:
    """Transliterate Cyrillic text to URL-safe Latin slug."""
    text = text.lower()
    out = "".join(TRANSLIT.get(c, c) for c in text)
    out = re.sub(r"[^a-z0-9]+", "-", out)
    return out.strip("-")


def extract_youtube_id(url: str) -> str | None:
    """Extract 11-char YouTube video ID from various URL formats."""
    for pat in [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?]|$)",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
    ]:
        m = re.search(pat, url or "")
        if m:
            return m.group(1)
    return None


def make_lesson_id(title: str, youtube_id: str) -> str:
    """Generate a deterministic, collision-safe lesson_id slug."""
    return slugify(title)[:80].rstrip("-") + "-" + youtube_id[:6]


def normalize_subject(raw: str) -> str:
    """Strip trailing grade/class info and normalize whitespace."""
    # e.g. "Алгебра і початки аналізу" — already clean in most titles
    # but sometimes ends in grade: "Фізика. 10 клас" → strip the "10 клас" bit
    raw = raw.strip().rstrip(".")
    raw = re.sub(r"\s+", " ", raw)
    return raw


def find_subject_slug(subject_raw: str) -> str | None:
    """Look up a clean subject string in SUBJECT_MAP (exact, then prefix)."""
    cleaned = normalize_subject(subject_raw)

    # Exact match first
    if cleaned in SUBJECT_MAP:
        return SUBJECT_MAP[cleaned]

    # Try stripping trailing parenthesised notes: "Фізика (рівень стандарту)" → "Фізика"
    base = re.sub(r"\s*\(.*\)\s*$", "", cleaned).strip()
    if base in SUBJECT_MAP:
        return SUBJECT_MAP[base]

    # Prefix match (longest wins)
    best = None
    best_len = 0
    for key, slug in SUBJECT_MAP.items():
        if cleaned.startswith(key) and len(key) > best_len:
            best, best_len = slug, len(key)
    return best


def run_import(dry_run: bool = False) -> None:
    if not VIDEO_DB_PATH.exists():
        logger.error(f"video_db.json not found at {VIDEO_DB_PATH}")
        sys.exit(1)

    logger.info(f"Loading {VIDEO_DB_PATH} …")
    with open(VIDEO_DB_PATH, encoding="utf-8") as f:
        video_entries = json.load(f)
    logger.info(f"Loaded {len(video_entries)} entries from video_db.json")

    db = SessionLocal()
    try:
        # Build map: youtube_id → existing Lesson row
        existing_lessons = db.query(Lesson).all()
        yt_to_lesson: dict[str, Lesson] = {}
        for lesson in existing_lessons:
            yt_id = extract_youtube_id(lesson.youtube_link or "")
            if yt_id:
                yt_to_lesson[yt_id] = lesson

        logger.info(
            f"Found {len(existing_lessons)} existing lessons, "
            f"{len(yt_to_lesson)} have parseable YouTube IDs"
        )

        # Build map: course_id_str → Course row (for get-or-create)
        existing_courses = db.query(Course).all()
        course_map: dict[str, Course] = {c.course_id: c for c in existing_courses}

        counters = dict(imported=0, reconciled=0, skipped=0, unparsable=0, batch=0)

        for entry in video_entries:
            title = (entry.get("title") or "").strip()
            youtube_id = entry.get("video_id", "")

            if not title or not youtube_id:
                counters["unparsable"] += 1
                continue

            # Parse grade + subject from title
            m = TITLE_REGEX.match(title)
            if not m:
                counters["unparsable"] += 1
                logger.debug(f"No grade/subject match: {title[:80]}")
                continue

            grade_str = m.group(1)
            subject_raw = m.group(2).strip()
            subject_slug = find_subject_slug(subject_raw)

            if subject_slug is None:
                counters["skipped"] += 1
                logger.debug(f"Unknown subject '{subject_raw}' in: {title[:80]}")
                continue

            course_id_str = f"{subject_slug}-{grade_str}"
            youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"

            if dry_run:
                logger.info(f"[DRY] would upsert: {course_id_str} | {make_lesson_id(title, youtube_id)} | {title[:60]}")
                counters["imported"] += 1
                continue

            # Get or create Course
            if course_id_str not in course_map:
                course = Course(
                    course_id=course_id_str,
                    title=f"{normalize_subject(subject_raw)} — {grade_str} клас",
                    description=f"Відеоуроки з предмету «{normalize_subject(subject_raw)}», {grade_str} клас",
                )
                db.add(course)
                db.flush()  # get course.id without full commit
                course_map[course_id_str] = course

            course = course_map[course_id_str]

            if youtube_id in yt_to_lesson:
                # Existing row — update metadata, preserve lesson_id slug
                lesson = yt_to_lesson[youtube_id]
                changed = False
                if lesson.title != title:
                    lesson.title = title
                    changed = True
                if lesson.course_id != course.id:
                    lesson.course_id = course.id
                    changed = True
                if lesson.youtube_link != youtube_url:
                    lesson.youtube_link = youtube_url
                    changed = True
                if changed:
                    counters["reconciled"] += 1
            else:
                # New row
                lesson_id_slug = make_lesson_id(title, youtube_id)
                # Ensure uniqueness (in case of slug collision, append more of the youtube_id)
                candidate = lesson_id_slug
                existing_slugs = {les.lesson_id for les in existing_lessons}
                suffix_len = 6
                while candidate in existing_slugs and suffix_len < 11:
                    suffix_len += 1
                    candidate = slugify(title)[:80].rstrip("-") + "-" + youtube_id[:suffix_len]

                lesson = Lesson(
                    lesson_id=candidate,
                    course_id=course.id,
                    title=title,
                    youtube_link=youtube_url,
                )
                db.add(lesson)
                yt_to_lesson[youtube_id] = lesson
                existing_lessons.append(lesson)
                counters["imported"] += 1

            counters["batch"] += 1
            if counters["batch"] % 100 == 0:
                db.commit()
                logger.info(
                    f"  Progress: imported={counters['imported']} "
                    f"reconciled={counters['reconciled']} "
                    f"skipped={counters['skipped']} "
                    f"unparsable={counters['unparsable']}"
                )

        if not dry_run:
            db.commit()

        logger.info(
            f"\nImport complete:\n"
            f"  imported    = {counters['imported']}\n"
            f"  reconciled  = {counters['reconciled']}\n"
            f"  skipped     = {counters['skipped']}\n"
            f"  unparsable  = {counters['unparsable']}\n"
            f"  total processed = {len(video_entries)}"
        )

        if not dry_run:
            total = db.query(Lesson).count()
            courses = db.query(Course).count()
            logger.info(f"\nDB now has {total} lessons across {courses} courses")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import video_db.json into PostgreSQL")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse only — do not write to database")
    args = parser.parse_args()
    run_import(dry_run=args.dry_run)
