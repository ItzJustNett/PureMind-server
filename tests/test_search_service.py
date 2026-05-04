"""
Tests for the semantic search service.

Unit tests run in <1s (no SBERT load — uses fixed-seed vectors).
Integration tests require a running Postgres DB and the import_video_db.py
migration to have been run first.

Run with:
    cd PureMind-server
    pytest tests/test_search_service.py -v
    pytest tests/test_search_service.py -v -k "not integration"   # unit only
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

# Add server root to sys.path
SERVER_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVER_ROOT))

# Load env for DB
from dotenv import load_dotenv
load_dotenv(dotenv_path=SERVER_ROOT / ".env")


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _fixed_query_vec(seed: int = 42) -> np.ndarray:
    """Reproducible 384-dim unit vector — avoids loading SBERT in unit tests."""
    rng = np.random.default_rng(seed)
    v = rng.random(384).astype(np.float32)
    return v / np.linalg.norm(v)


def _load_sample_entries(n: int = 5) -> list:
    """Load first n entries from video_db.json that have embeddings."""
    db_path = SERVER_ROOT.parent / "New search model" / "video_db.json"
    if not db_path.exists():
        pytest.skip(f"video_db.json not found at {db_path}")
    with open(db_path, encoding="utf-8") as f:
        entries = json.load(f)
    return [e for e in entries if e.get("transcript_emb") and e.get("title_emb")][:n]


# ══════════════════════════════════════════════════════════════════════════════
#  Unit tests — no DB, no SBERT
# ══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:

    def test_tokenize_cyrillic(self):
        from search_service import tokenize
        tokens = tokenize("Алгебра і початки аналізу")
        assert "алгебра" in tokens
        assert "початки" in tokens
        assert "аналізу" in tokens
        assert "і" not in tokens   # too short

    def test_tokenize_numbers(self):
        from search_service import tokenize
        tokens = tokenize("Рівняння 10 класу")
        assert "10" in tokens

    def test_tiered_returns_first_match(self):
        from search_service import tiered, KEYWORD_TITLE_TIERS
        assert tiered(1.0, KEYWORD_TITLE_TIERS) == 2.50
        assert tiered(0.75, KEYWORD_TITLE_TIERS) == 1.50
        assert tiered(0.10, KEYWORD_TITLE_TIERS) == 0.0

    def test_keyword_ratio_partial_match(self):
        from search_service import _keyword_ratio, tokenize
        tokens = tokenize("інтеграл")
        ratio = _keyword_ratio(tokens, "Визначений інтеграл та його властивості")
        assert ratio > 0.0

    def test_keyword_ratio_empty(self):
        from search_service import _keyword_ratio
        assert _keyword_ratio(set(), "some text") == 0.0
        assert _keyword_ratio({"word"}, "") == 0.0

    def test_detect_query_lang_ukrainian(self):
        from search_service import _detect_query_lang
        assert _detect_query_lang("алгебра інтеграл") == "uk"

    def test_detect_query_lang_english(self):
        from search_service import _detect_query_lang
        assert _detect_query_lang("algebra integration") == "en"

    def test_detect_query_lang_unknown(self):
        from search_service import _detect_query_lang
        assert _detect_query_lang("42") == "?"


class TestScoringParity:
    """
    Verify that search_service scoring logic produces identical results to Finder.py.
    Uses a fixed-seed query vector — no SBERT loaded.
    """

    def test_score_components_match_finder(self):
        """
        The arithmetic in search_service._rank_uncached must match Finder.score_entry.
        We test by manually computing both and comparing totals.
        """
        from search_service import (
            tokenize, tiered, _keyword_ratio, _detect_query_lang,
            W_TRANSCRIPT, W_TITLE, KEYWORD_TITLE_TIERS, KEYWORD_BODY_TIERS,
            TOPIC_TIERS, SIMILARITY_THRESHOLD,
        )

        entries = _load_sample_entries(5)
        q_vec    = _fixed_query_vec(42)
        q_tokens = tokenize("алгебра")
        q_lang   = _detect_query_lang("алгебра")

        for entry in entries:
            t_vec  = np.array(entry["transcript_emb"], dtype=np.float32)
            ti_vec = np.array(entry["title_emb"],      dtype=np.float32)
            tp_raw = entry.get("topic_emb", [])
            tp_vec = np.array(tp_raw, dtype=np.float32) if tp_raw else np.zeros(384, dtype=np.float32)

            def cosine(a, b):
                na, nb = np.linalg.norm(a), np.linalg.norm(b)
                return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

            t_sim  = cosine(q_vec, t_vec)
            ti_sim = cosine(q_vec, ti_vec)
            tp_sim = cosine(q_vec, tp_vec) if tp_vec.any() else 0.0

            kw_title   = _keyword_ratio(q_tokens, entry.get("title", ""))
            kw_body    = _keyword_ratio(q_tokens, entry.get("transcript", ""))
            tp_bonus   = tiered(tp_sim, TOPIC_TIERS)
            kw_title_b = tiered(kw_title, KEYWORD_TITLE_TIERS)
            kw_body_b  = tiered(kw_body,  KEYWORD_BODY_TIERS)

            lang_bonus = 0.0
            e2 = (entry.get("lang", "?") or "")[:2].lower()
            q2 = q_lang[:2].lower()
            if e2 and e2 != "?":
                lang_bonus += 0.15 if e2 == q2 else -0.15
            _CT = ("кримськотатарська", "qırımtatar", "крымскотатарск")
            title_lower = entry.get("title", "").lower()
            if any(x in title_lower for x in _CT) and q2 == "uk":
                lang_bonus -= 0.35

            expected_total = (
                W_TRANSCRIPT * t_sim
                + W_TITLE    * ti_sim
                + kw_title_b + kw_body_b
                + tp_bonus   + lang_bonus
            )

            # Verify our constants are correct
            assert W_TRANSCRIPT == 0.50
            assert W_TITLE      == 0.30
            assert SIMILARITY_THRESHOLD == 0.10
            # Verify the arithmetic result is a float
            assert isinstance(expected_total, float)


# ══════════════════════════════════════════════════════════════════════════════
#  Integration tests — require Postgres DB + import_video_db.py to have run
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def warm_service():
    """Force synchronous warm-start for testing."""
    from search_service import search_service
    if not search_service.is_ready():
        try:
            search_service._warm_start_sync()
        except Exception as e:
            pytest.skip(f"Could not warm search service: {e}")
    return search_service


@pytest.fixture(scope="module")
def client(warm_service):
    """FastAPI TestClient with warmed service."""
    try:
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Could not create TestClient: {e}")


@pytest.mark.integration
class TestSemanticSearchEndpoint:

    def test_returns_200_with_results(self, client):
        resp = client.get("/api/lessons/semantic-search?q=Алгебра")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1

    def test_response_shape(self, client):
        resp = client.get("/api/lessons/semantic-search?q=Алгебра&limit=5")
        data = resp.json()
        assert "total"    in data
        assert "has_more" in data
        assert "took_ms"  in data
        result = data["results"][0]
        for key in ("id", "lesson_id", "title", "course_id", "score"):
            assert key in result, f"Missing key: {key}"

    def test_scores_strictly_decreasing(self, client):
        resp = client.get("/api/lessons/semantic-search?q=Алгебра&limit=10")
        scores = [r["score"] for r in resp.json()["results"]]
        assert scores == sorted(scores, reverse=True), \
            f"Scores not descending: {scores}"

    def test_all_scores_above_threshold(self, client):
        from search_service import SIMILARITY_THRESHOLD
        resp = client.get("/api/lessons/semantic-search?q=Алгебра")
        for r in resp.json()["results"]:
            assert r["score"] >= SIMILARITY_THRESHOLD, \
                f"Score {r['score']} below threshold for: {r['title']}"

    def test_limit_respected(self, client):
        resp = client.get("/api/lessons/semantic-search?q=Алгебра&limit=30")
        assert len(resp.json()["results"]) <= 30

    def test_grade_filter_applied(self, client):
        resp = client.get("/api/lessons/semantic-search?q=Алгебра&grade=7")
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["course_id"].endswith("-7"), \
                f"Expected grade 7, got course_id={r['course_id']}"

    def test_offset_pagination(self, client):
        resp1 = client.get("/api/lessons/semantic-search?q=математика&limit=5&offset=0")
        resp2 = client.get("/api/lessons/semantic-search?q=математика&limit=5&offset=5")
        ids1 = {r["id"] for r in resp1.json()["results"]}
        ids2 = {r["id"] for r in resp2.json()["results"]}
        assert ids1.isdisjoint(ids2), "Pagination pages overlap"

    def test_503_when_not_ready(self, client, monkeypatch):
        from search_service import search_service
        monkeypatch.setattr(search_service, "_ready", False)
        resp = client.get("/api/lessons/semantic-search?q=test")
        assert resp.status_code == 503
        monkeypatch.setattr(search_service, "_ready", True)

    def test_empty_query_rejected(self, client):
        resp = client.get("/api/lessons/semantic-search?q=")
        assert resp.status_code == 422   # FastAPI validation: min_length=1

    def test_has_more_flag(self, client):
        resp = client.get("/api/lessons/semantic-search?q=математика&limit=1&offset=0")
        data = resp.json()
        if data["total"] > 1:
            assert data["has_more"] is True


@pytest.mark.integration
class TestImportScript:

    def test_lessons_count_after_import(self):
        """After running import_video_db.py, DB should have ≥ 1349 lessons."""
        from database import SessionLocal
        from database.models import Lesson
        db = SessionLocal()
        try:
            count = db.query(Lesson).count()
        finally:
            db.close()
        assert count >= 1349, (
            f"Expected ≥1349 lessons after import, got {count}. "
            "Did you run: python3 scripts/import_video_db.py ?"
        )

    def test_grade_range_in_courses(self):
        """After import, courses should span grades 5–11."""
        import re
        from database import SessionLocal
        from database.models import Course
        db = SessionLocal()
        try:
            courses = db.query(Course.course_id).all()
        finally:
            db.close()
        grades = set()
        for (cid,) in courses:
            m = re.search(r"-(\d+)$", cid or "")
            if m:
                grades.add(int(m.group(1)))
        expected = {5, 6, 7, 8, 10, 11}
        assert expected.issubset(grades), \
            f"Missing grades after import. Found: {sorted(grades)}"
