"""
Semantic search service using SBERT (paraphrase-multilingual-MiniLM-L12-v2).

Scoring logic ported verbatim from New search model/Finder.py.
Do NOT import Finder.py — it has CLI-only side-effects (argparse, dotenv print, etc.).

This module exposes a singleton `search_service`. Call `await search_service.warm_start()`
once in the FastAPI lifespan block. The endpoint returns HTTP 503 until ready.
"""

import asyncio
import functools
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
VIDEO_DB_PATH = Path(__file__).parent.parent / "New search model" / "video_db.json"

# ── SBERT model name ──────────────────────────────────────────────────────────
SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ── Scoring constants (verbatim from Finder.py) ───────────────────────────────
W_TRANSCRIPT = 0.50   # cosine(query, transcript_emb) weight
W_TITLE      = 0.30   # cosine(query, title_emb) weight

KEYWORD_TITLE_TIERS = [
    (1.00, 2.50),
    (0.75, 1.50),
    (0.50, 0.70),
    (0.33, 0.30),
]
KEYWORD_BODY_TIERS = [
    (1.00, 0.40),
    (0.75, 0.25),
    (0.50, 0.12),
    (0.25, 0.05),
]
TOPIC_TIERS = [
    (0.80, 0.30),
    (0.70, 0.18),
    (0.60, 0.09),
    (0.50, 0.04),
]
SIMILARITY_THRESHOLD = 0.10


# ══════════════════════════════════════════════════════════════════════════════
#  Scoring helpers (copied from Finder.py — not imported)
# ══════════════════════════════════════════════════════════════════════════════

def tokenize(text: str) -> set:
    """Lowercase tokens: Cyrillic/Latin words ≥3 chars + standalone numbers."""
    words   = re.findall(r"[а-яА-ЯіІїЇєЄa-zA-ZäöüÄÖÜß]{3,}", text)
    numbers = re.findall(r"\b\d+\b", text)
    return set(w.lower() for w in words) | set(numbers)


def tiered(value: float, tiers: list) -> float:
    """Return bonus for first tier whose threshold value meets."""
    for threshold, bonus in tiers:
        if value >= threshold:
            return bonus
    return 0.0


def _keyword_ratio(query_tokens: set, text: str) -> float:
    """Fraction of query tokens that appear as substring in text."""
    if not query_tokens or not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for qt in query_tokens if qt in text_lower)
    return hits / len(query_tokens)


def _detect_query_lang(text: str) -> str:
    """Detect query language: 'uk', 'ru', 'en', or '?'."""
    if not text:
        return "?"
    cyr = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    if cyr < 3 and lat < 3:
        return "?"
    if lat > cyr:
        return "en"
    if any(c in "іїєґІЇЄҐ" for c in text):
        return "uk"
    return "ru"


def _extract_youtube_id(url: str) -> Optional[str]:
    for pat in [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?]|$)",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
    ]:
        m = re.search(pat, url or "")
        if m:
            return m.group(1)
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  SemanticSearchService
# ══════════════════════════════════════════════════════════════════════════════

class SemanticSearchService:
    """
    Wraps SBERT model + in-memory numpy corpus.
    Call warm_start() once at startup; search() after that.
    """

    def __init__(self):
        self._ready    = False
        self._model    = None        # SentenceTransformer
        self._T_mat    = None        # np.ndarray [N, 384] transcript embeddings (pre-normed)
        self._Ti_mat   = None        # np.ndarray [N, 384] title embeddings (pre-normed)
        self._Tp_mat   = None        # np.ndarray [N, 384] topic embeddings (pre-normed)
        self._meta: list = []        # parallel list of dicts per row

        # LRU cache on instance method — lru_cache requires hashable self,
        # so we wrap the uncached method manually in __init__.
        self._search_cache = functools.lru_cache(maxsize=128)(self._rank_uncached)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self._ready

    async def warm_start(self) -> None:
        """Non-blocking warm start: runs CPU-heavy work in a thread pool."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._warm_start_sync)
        except Exception as e:
            logger.error(f"semantic search warm_start failed: {e}", exc_info=True)

    def reload_corpus(self) -> int:
        """
        Rebuild in-memory corpus from video_db.json joined to Postgres lessons.
        Returns number of matched rows loaded.
        Called automatically by warm_start; can be called again to refresh.
        """
        return self._build_corpus()

    def search(
        self,
        q: str,
        grade: Optional[str] = None,
        subject: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
    ) -> dict:
        """
        Run semantic search. Returns a dict compatible with the frontend shape:
        {results: [...], total: N, has_more: bool, took_ms: float}
        Each result: {id, lesson_id, title, course_id, youtube_link,
                      xp_reward, difficulty, score, exercises, created_at}
        """
        t0 = time.perf_counter()

        ranked = self._search_cache(q, grade or None, subject or None)
        total  = len(ranked)
        page   = ranked[offset: offset + limit]

        results = []
        for (orig_i, score) in page:
            m = self._meta[orig_i]
            results.append({
                "id":           m["lesson_id"],
                "lesson_id":    m["lesson_id"],
                "title":        m["title"],
                "course_id":    m["course_id"],
                "youtube_link": f"https://www.youtube.com/watch?v={m['youtube_id']}",
                "xp_reward":    None,
                "difficulty":   None,
                "score":        round(score, 4),
                "exercises":    [],
                "created_at":   None,
            })

        return {
            "results":  results,
            "total":    total,
            "has_more": (offset + limit) < total,
            "took_ms":  round((time.perf_counter() - t0) * 1000, 1),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _warm_start_sync(self) -> None:
        """Synchronous warm-start (runs in executor thread)."""
        t0 = time.time()
        logger.info(f"Loading SBERT model: {SBERT_MODEL} …")
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(SBERT_MODEL)
        self._model.encode("")   # warm the tokenizer
        logger.info(f"SBERT loaded in {time.time() - t0:.1f}s, building corpus …")

        n = self._build_corpus()
        self._ready = True
        logger.info(f"semantic search ready (N={n}, total={time.time() - t0:.1f}s)")

    def _build_corpus(self) -> int:
        """Parse video_db.json, join to Postgres, build numpy matrices."""
        from database import SessionLocal
        from database.models import Lesson, Course

        # Load vector DB
        if not VIDEO_DB_PATH.exists():
            logger.error(f"video_db.json not found at {VIDEO_DB_PATH}")
            return 0

        with open(VIDEO_DB_PATH, encoding="utf-8") as f:
            video_entries = json.load(f)
        logger.info(f"video_db.json: {len(video_entries)} entries")

        # Fetch lessons + courses from Postgres
        db = SessionLocal()
        try:
            lesson_rows = db.query(
                Lesson.lesson_id,
                Lesson.title,
                Lesson.youtube_link,
                Lesson.course_id,   # integer FK
            ).all()

            course_rows = db.query(Course.id, Course.course_id).all()
        finally:
            db.close()

        # Build lookup maps
        cid_map: dict[int, str] = {r.id: r.course_id for r in course_rows}

        yt_to_row: dict[str, object] = {}
        for row in lesson_rows:
            yt_id = _extract_youtube_id(row.youtube_link or "")
            if yt_id:
                yt_to_row[yt_id] = row

        logger.info(
            f"Postgres: {len(lesson_rows)} lessons, "
            f"{len(yt_to_row)} with parseable YouTube links"
        )

        # Build matrices + meta
        T_list, Ti_list, Tp_list = [], [], []
        meta: list = []
        orphan_emb = 0

        for entry in video_entries:
            yt_id = entry.get("video_id", "")
            if yt_id not in yt_to_row:
                orphan_emb += 1
                continue

            row = yt_to_row[yt_id]
            t_raw  = entry.get("transcript_emb", [])
            ti_raw = entry.get("title_emb",      [])
            tp_raw = entry.get("topic_emb",       [])

            if not t_raw or not ti_raw:
                orphan_emb += 1
                continue

            def _norm(arr):
                v = np.array(arr, dtype=np.float32)
                n = np.linalg.norm(v)
                return (v / n) if n > 0 else v

            T_list.append(_norm(t_raw))
            Ti_list.append(_norm(ti_raw))
            Tp_list.append(_norm(tp_raw) if tp_raw else np.zeros(384, dtype=np.float32))

            course_str = cid_map.get(row.course_id, "")
            gm = re.search(r"-(\d+)$", course_str)

            meta.append({
                "lesson_id":  row.lesson_id,
                "title":      entry.get("title") or row.title or "",
                "transcript": entry.get("transcript", ""),
                "topics":     entry.get("topics", []),
                "lang":       entry.get("lang", "?"),
                "course_id":  course_str,
                "grade":      gm.group(1) if gm else "",
                "youtube_id": yt_id,
            })

        if not T_list:
            logger.warning(
                "reload_corpus: no rows matched — did you run import_video_db.py first?"
            )
            return 0

        self._T_mat  = np.stack(T_list)
        self._Ti_mat = np.stack(Ti_list)
        self._Tp_mat = np.stack(Tp_list)
        self._meta   = meta

        # Clear LRU cache so stale ranked lists are not returned
        self._search_cache.cache_clear()

        orphan_lesson = max(0, len(yt_to_row) - (len(video_entries) - orphan_emb))
        logger.info(
            f"corpus ready: {len(meta)} rows loaded; "
            f"{orphan_emb} orphan embeddings (no DB lesson); "
            f"~{orphan_lesson} lessons without embeddings"
        )
        return len(meta)

    def _rank_uncached(
        self,
        q: str,
        grade: Optional[str],
        subject: Optional[str],
    ) -> list:
        """
        Score all (pre-filtered) entries for query q.
        Returns list of (meta_index, total_score) sorted descending.
        Results below SIMILARITY_THRESHOLD are excluded.

        Note: wrapped in self._search_cache (lru_cache) — must be called via
        self._search_cache(q, grade, subject), not directly.
        """
        t0 = time.perf_counter()

        q_vec  = np.array(self._model.encode(q), dtype=np.float32)
        q_norm = q_vec / (np.linalg.norm(q_vec) or 1.0)
        q_tokens = tokenize(q)
        q_lang   = _detect_query_lang(q)

        # Pre-filter candidates by grade / subject
        indices = []
        for i, m in enumerate(self._meta):
            if grade   and m["grade"]    != grade:
                continue
            if subject and not m["course_id"].startswith(subject):
                continue
            indices.append(i)

        if not indices:
            return []

        # Vectorised cosine (matrices are pre-normalised → dot product = cosine)
        T_sub  = self._T_mat[indices]
        Ti_sub = self._Ti_mat[indices]
        Tp_sub = self._Tp_mat[indices]

        t_sims  = T_sub  @ q_norm   # shape [K]
        ti_sims = Ti_sub @ q_norm
        tp_sims = Tp_sub @ q_norm

        results = []
        for j, orig_i in enumerate(indices):
            m = self._meta[orig_i]

            t_sim  = float(t_sims[j])
            ti_sim = float(ti_sims[j])
            tp_sim = float(tp_sims[j])

            tp_bonus     = tiered(tp_sim, TOPIC_TIERS)
            kw_title     = _keyword_ratio(q_tokens, m["title"])
            kw_body      = _keyword_ratio(q_tokens, m["transcript"])
            kw_title_b   = tiered(kw_title, KEYWORD_TITLE_TIERS)
            kw_body_b    = tiered(kw_body,  KEYWORD_BODY_TIERS)

            lang_bonus = 0.0
            if q_lang != "?":
                e2 = (m["lang"] or "")[:2].lower()
                q2 = q_lang[:2].lower()
                if e2 and e2 != "?":
                    lang_bonus += 0.15 if e2 == q2 else -0.15
                _CT = ("кримськотатарська", "qırımtatar", "крымскотатарск")
                if any(x in m["title"].lower() for x in _CT) and q2 == "uk":
                    lang_bonus -= 0.35

            total = (
                W_TRANSCRIPT * t_sim
                + W_TITLE    * ti_sim
                + kw_title_b
                + kw_body_b
                + tp_bonus
                + lang_bonus
            )

            if total >= SIMILARITY_THRESHOLD:
                results.append((orig_i, total))

        results.sort(key=lambda x: x[1], reverse=True)
        logger.debug(
            f"_rank_uncached q={q!r} K={len(indices)} "
            f"results={len(results)} took={time.perf_counter()-t0:.3f}s"
        )
        return results


# ── Module-level singleton ────────────────────────────────────────────────────
search_service = SemanticSearchService()
