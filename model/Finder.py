# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  MUST BE THE ABSOLUTE FIRST LINES — before any import that touches TF/Keras ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import os
import sys
os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"   # silence TF C++ INFO/WARNING/ERROR
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"   # silence oneDNN custom-ops message
os.environ["PYTHONUTF8"]            = "1"   # propagate UTF-8 to subprocesses

# ── Unicode safety (must happen before ANY console I/O) ──────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Silence Python-level deprecation warnings from tf-keras ──────────────────
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=r".*oneDNN.*")
warnings.filterwarnings("ignore", message=r".*tf\.losses.*")
warnings.filterwarnings("ignore", message=r".*get_feature_names.*")

# ── Now safe to import everything else ───────────────────────────────────────
import argparse
import json
import re
import time
import uuid
import shutil
from pathlib import Path
from collections import Counter

import numpy as np
import requests
from dotenv import load_dotenv

# ── Load .env (keys for Groq, OpenAI, etc.) ──────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)
    _key = os.environ.get("GROQ_API_KEY", "")
    if "твій_ключ" in _key:
        print("❌ ПОМИЛКА: Скрипт все ще бачить ПРИКЛАД ключа замість справжнього!")
    else:
        print(f"✅ .env завантажено. Ключ починається на: {_key[:10]}...")
else:
    print(f"❌ ПОМИЛКА: Файл .env не знайдено за шляхом: {_env_path}")

# ── Lazy SBERT import (sentence_transformers triggers TF; defer until needed) ─
_sbert_cache    = None
_keybert_cache  = None
_clip_cache: dict = {}

# ── scikit-learn compat shim (safe — no actual sklearn import at startup) ────
try:
    from sklearn.feature_extraction.text import CountVectorizer as _CV
    if not hasattr(_CV, "get_feature_names"):
        _CV.get_feature_names = _CV.get_feature_names_out
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════════

DB_FILE    = "video_db.json"
MAX_FRAMES = 24

SBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CLIP_MODEL  = "openai/clip-vit-base-patch32"

# ── Transcription API endpoints ───────────────────────────────────────────────
GROQ_API_URL       = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL         = "whisper-large-v3-turbo"
GROQ_SILENCE_GAP   = 5.0
GROQ_MAX_BATCH_MB  = 20.0
GROQ_SPEECH_KBPS   = 32
OPENAI_API_URL     = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL       = "whisper-1"
DEEPGRAM_API_URL   = "https://api.deepgram.com/v1/listen"
ASSEMBLYAI_API_URL = "https://api.assemblyai.com/v2"
GOOGLE_STT_URL     = "https://speech.googleapis.com/v1/speech:recognize"

# ── Search scoring weights ────────────────────────────────────────────────────
W_TRANSCRIPT = 0.50   # SBERT cosine on full transcript vector
W_TITLE      = 0.30   # SBERT cosine on title vector

# ── Keyword boost tiers  (ratio of query words found in title/transcript) ────
# This is the "hybrid" layer: exact word matches boost the semantic score so
# specific names / terms always surface even in a crowded vector space.
KEYWORD_TITLE_TIERS = [
    (1.00, 2.50),   # all query words in title  → very strong boost
    (0.75, 1.50),
    (0.50, 0.70),
    (0.33, 0.30),
]
KEYWORD_BODY_TIERS = [
    (1.00, 0.40),   # all query words in transcript text
    (0.75, 0.25),
    (0.50, 0.12),
    (0.25, 0.05),
]

# ── Topic / visual bonus tiers ────────────────────────────────────────────────
TOPIC_TIERS  = [(0.80, 0.30), (0.70, 0.18), (0.60, 0.09), (0.50, 0.04)]
VISUAL_TIERS = [(0.80, 0.80), (0.65, 0.55), (0.50, 0.35), (0.35, 0.20), (0.20, 0.10)]

# ── Similarity threshold for quality gate ────────────────────────────────────
SIMILARITY_THRESHOLD = 0.10


# ══════════════════════════════════════════════════════════════════════════════
#  Unicode helpers
# ══════════════════════════════════════════════════════════════════════════════

def safe_text(text: str) -> str:
    return str(text).encode("utf-8", errors="replace").decode("utf-8")

def safe_filename(name: str) -> str:
    ascii_name = str(name).encode("ascii", errors="ignore").decode("ascii").strip()
    return ascii_name or "audio.mp3"

def safe_print(*args, **kwargs):
    print(*[safe_text(str(a)) for a in args], **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  Model loaders  (lazy — nothing loads until first use)
# ══════════════════════════════════════════════════════════════════════════════

def _get_sbert():
    global _sbert_cache
    if _sbert_cache is None:
        from sentence_transformers import SentenceTransformer
        safe_print(f"  Loading SBERT ({SBERT_MODEL})...")
        _sbert_cache = SentenceTransformer(SBERT_MODEL)
    return _sbert_cache

def _get_keybert():
    global _keybert_cache
    if _keybert_cache is None:
        from keybert import KeyBERT
        _keybert_cache = KeyBERT(model=_get_sbert())
    return _keybert_cache

def _get_clip():
    if "model" not in _clip_cache:
        from transformers import CLIPModel, CLIPProcessor
        safe_print(f"  Loading CLIP ({CLIP_MODEL})...")
        _clip_cache["model"]     = CLIPModel.from_pretrained(CLIP_MODEL)
        _clip_cache["processor"] = CLIPProcessor.from_pretrained(CLIP_MODEL)
        _clip_cache["model"].eval()
    return _clip_cache["model"], _clip_cache["processor"]


# ══════════════════════════════════════════════════════════════════════════════
#  DB helpers  (single file — video_db.json)
# ══════════════════════════════════════════════════════════════════════════════

def load_db(path: str, verbose: bool = False) -> list:
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        safe_print(
            f"\n  ⚠️  DB not found at: {abs_path}"
            f"\n  Current folder: {os.getcwd()}"
            f"\n  JSON files here: {[f for f in os.listdir('.') if f.endswith('.json')]}"
            f"\n  Use --db <path> to point to your database file."
        )
        return []
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if verbose:
            safe_print(f"  Loaded {len(data)} entries from {abs_path}")
        return data
    except json.JSONDecodeError as e:
        safe_print(f"  ❌ DB file has invalid JSON: {e}\n  Path: {abs_path}")
        return []

def save_db(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
#  Generic helpers
# ══════════════════════════════════════════════════════════════════════════════

def tokenize(text: str) -> list:
    """
    Lowercase tokens from Cyrillic/Latin words (≥3 chars) + standalone numbers.
    Works correctly for uk / en / de / crh mixed text.
    """
    words   = re.findall(r"[а-яА-ЯіІїЇєЄa-zA-ZäöüÄÖÜß]{3,}", text)
    numbers = re.findall(r"\b\d+\b", text)
    return [w.lower() for w in words] + numbers

def tiered(value: float, tiers: list) -> float:
    for threshold, bonus in tiers:
        if value >= threshold:
            return bonus
    return 0.0

def cosine(a, b) -> float:
    """Pure-numpy cosine similarity. No scipy."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

def extract_video_id(url: str):
    for pat in [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
    ]:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None

def _detect_query_lang(text: str) -> str:
    if not text:
        return "?"
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    if cyr < 3 and lat < 3:
        return "?"
    if lat > cyr:
        return "en"
    if any(c in "іїєґІЇЄҐ" for c in text):
        return "uk"
    return "ru"


# ══════════════════════════════════════════════════════════════════════════════
#  Transcript + title fetching
# ══════════════════════════════════════════════════════════════════════════════

def fetch_title(video_id: str) -> str:
    try:
        import urllib.request
        url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8")).get("title", "")
    except Exception:
        return ""

def _fetch_transcript_direct(video_id: str, proxy=None):
    from youtube_transcript_api import YouTubeTranscriptApi
    kwargs = {}
    if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}
    try:
        api = YouTubeTranscriptApi(**kwargs)
        lst = api.list(video_id)
        transcript = None
        for t in lst:
            if not getattr(t, "is_generated", True):
                transcript = t
                break
        if transcript is None:
            for t in lst:
                transcript = t
                break
        if transcript is None:
            return None, None
        segs  = transcript.fetch()
        parts = [s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "") for s in segs]
        text  = " ".join(parts).strip()
        lang  = getattr(transcript, "language_code", "uk") or "uk"
        return (text, lang) if text else (None, None)
    except AttributeError:
        pass
    data = YouTubeTranscriptApi.get_transcript(video_id, **kwargs)
    text = " ".join(
        s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "") for s in data
    ).strip()
    return (text, "uk") if text else (None, None)

def _fetch_transcript_ytdlp(video_id: str, proxy=None):
    import yt_dlp, tempfile, json as _json, re as _re
    cookies_file = Path(__file__).parent / "cookies.txt"
    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
        "subtitleslangs": ["uk", "ru", "en", "all"], "subtitlesformat": "json3",
        "quiet": True, "no_warnings": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "referer": "https://www.youtube.com/",
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
    }
    if cookies_file.exists():
        opts["cookiefile"] = str(cookies_file)
    if proxy:
        opts["proxy"] = proxy
    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = str(Path(tmpdir) / "sub.%(ext)s")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception as e:
            safe_print(f"  [yt-dlp subs] Failed: {safe_text(str(e)[:120])}")
            return None, None
        for sf in sorted(Path(tmpdir).glob("sub.*")):
            if sf.suffix not in (".json3", ".vtt", ".srv3"):
                continue
            lang = sf.stem.split(".")[-1] if "." in sf.stem else "uk"
            try:
                raw = sf.read_text(encoding="utf-8", errors="replace")
                if sf.suffix == ".json3":
                    data  = _json.loads(raw)
                    words = [seg.get("utf8", "") for ev in data.get("events", []) for seg in ev.get("segs", [])]
                    text  = " ".join(words).replace("\n", " ").strip()
                else:
                    text = _re.sub(r"<[^>]+>", "", raw)
                    text = _re.sub(r"^\d{2}:\d{2}.*$", "", text, flags=_re.MULTILINE)
                    text = " ".join(text.split())
                if len(text.split()) >= 20:
                    return text, lang
            except Exception:
                continue
    return None, None

def fetch_transcript(video_id: str):
    _IP_ERRORS = ("IpBlocked", "TooManyRequests")
    _NO_SUBS   = ("NoTranscriptFound", "TranscriptsDisabled", "VideoUnavailable", "VideoUnplayable")
    try:
        result = _fetch_transcript_direct(video_id)
        if result[0]:
            safe_print(f"  Captions OK ({result[1]}, {len(result[0].split())} words)")
            return result
    except Exception as e:
        err = type(e).__name__
        if err in _IP_ERRORS:
            safe_print(f"  Captions IP-blocked. Trying yt-dlp...")
            result = _fetch_transcript_ytdlp(video_id)
            if result[0]:
                return result
        elif err not in _NO_SUBS:
            safe_print(f"  Captions error ({err}). Trying Groq...")
        else:
            safe_print(f"  Captions unavailable ({err}). Trying Groq...")
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
#  Transcription helpers
# ══════════════════════════════════════════════════════════════════════════════

def _log_ok(provider, lang, text):   safe_print(f"  {provider} OK ({lang}, {len(text.split())} words)")
def _log_fail(provider, e):         safe_print(f"  {provider} error: {safe_text(str(e))}")
def _log_http(provider, e):         safe_print(f"  {provider} HTTP {e.response.status_code}: {safe_text(e.response.text[:200])}")
def _ru_guard(text, lang):          return text, ("uk" if lang == "ru" else lang)

def _groq_keys() -> list:
    keys = []
    k = os.environ.get("GROQ_API_KEY", "").strip()
    if k: keys.append(k)
    i = 2
    while True:
        k = os.environ.get(f"GROQ_API_KEY_{i}", "").strip()
        if not k: break
        keys.append(k)
        i += 1
    seen, result = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result

def _groq_post(audio_bytes: bytes, language=None):
    keys = _groq_keys()
    if not keys:
        raise EnvironmentError("No GROQ_API_KEY found in .env")
    fields = {
        "model": (None, GROQ_MODEL),
        "response_format": (None, "verbose_json"),
        "temperature": (None, "0"),
    }
    if language:
        fields["language"] = (None, language)
    fields["file"] = ("audio.mp3", audio_bytes, "audio/mpeg")
    last_err = None
    for idx, api_key in enumerate(keys, 1):
        label = f"key #{idx} (...{api_key[-6:]})"
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files=dict(fields),
                timeout=180,
            )
            if resp.status_code in (401, 429):
                safe_print(f"  [groq] {label} {'rate-limited' if resp.status_code==429 else 'invalid'} — trying next...")
                last_err = requests.HTTPError(response=resp)
                continue
            resp.raise_for_status()
            data = resp.json()
            return safe_text(data.get("text", "").strip()), data.get("language", language or "uk") or "uk"
        except requests.HTTPError as e:
            last_err = e
        except requests.RequestException as e:
            last_err = e
    raise RuntimeError(f"All {len(keys)} Groq key(s) exhausted. Last: {last_err}")

def _groq_post_full(audio_bytes: bytes, language=None):
    keys = _groq_keys()
    if not keys:
        raise EnvironmentError("No GROQ_API_KEY found in .env")
    fields = {
        "model": (None, GROQ_MODEL), "response_format": (None, "verbose_json"), "temperature": (None, "0"),
    }
    if language:
        fields["language"] = (None, language)
    fields["file"] = ("audio.mp3", audio_bytes, "audio/mpeg")
    last_err = None
    for idx, api_key in enumerate(keys, 1):
        label = f"key #{idx} (...{api_key[-6:]})"
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files=dict(fields),
                timeout=300,
            )
            if resp.status_code in (401, 429):
                last_err = requests.HTTPError(response=resp)
                continue
            resp.raise_for_status()
            data     = resp.json()
            text     = safe_text(data.get("text", "").strip())
            lang_out = data.get("language", language or "uk") or "uk"
            return text, lang_out, data.get("segments", [])
        except (requests.HTTPError, requests.RequestException) as e:
            last_err = e
    raise RuntimeError(f"All Groq keys exhausted. Last: {last_err}")

def _transcribe_groq(audio_bytes: bytes):
    safe_print("  Sending to Groq...")
    try:
        text, lang = _groq_post(audio_bytes)
        if lang == "ru":
            safe_print("  Groq detected 'ru' -> re-sending as 'uk'")
            text, lang = _groq_post(audio_bytes, language="uk")
        text, lang = _ru_guard(text, lang)
        if not text: return None, None
        _log_ok("Groq", lang, text)
        return text, lang
    except requests.HTTPError as e:  _log_http("Groq", e)
    except Exception as e:           _log_fail("Groq", e)
    return None, None

def _transcribe_openai_whisper(audio_bytes: bytes):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        safe_print("  OpenAI skipped: OPENAI_API_KEY not set."); return None, None
    safe_print("  Sending to OpenAI Whisper...")
    try:
        resp = requests.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "file": ("audio.mp3", audio_bytes, "audio/mpeg"),
                "model": (None, OPENAI_MODEL),
                "response_format": (None, "verbose_json"),
                "temperature": (None, "0"),
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        text, lang = _ru_guard(safe_text(data.get("text", "").strip()), data.get("language", "uk") or "uk")
        if not text: return None, None
        _log_ok("OpenAI Whisper", lang, text); return text, lang
    except requests.HTTPError as e:  _log_http("OpenAI Whisper", e)
    except Exception as e:           _log_fail("OpenAI Whisper", e)
    return None, None

def _transcribe_deepgram(audio_bytes: bytes):
    api_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        safe_print("  Deepgram skipped: DEEPGRAM_API_KEY not set."); return None, None
    safe_print("  Sending to Deepgram Nova-2...")
    try:
        resp = requests.post(
            DEEPGRAM_API_URL,
            params={"model": "nova-2", "language": "uk", "smart_format": "true"},
            headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/mp3"},
            data=audio_bytes, timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        channels = data.get("results", {}).get("channels", [])
        text = safe_text(channels[0]["alternatives"][0]["transcript"].strip()) if channels else ""
        if not text: return None, None
        lang = data.get("metadata", {}).get("detected_language", "uk") or "uk"
        text, lang = _ru_guard(text, lang)
        _log_ok("Deepgram", lang, text); return text, lang
    except requests.HTTPError as e:  _log_http("Deepgram", e)
    except Exception as e:           _log_fail("Deepgram", e)
    return None, None

def _transcribe_assemblyai(audio_bytes: bytes):
    api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if not api_key:
        safe_print("  AssemblyAI skipped: ASSEMBLYAI_API_KEY not set."); return None, None
    safe_print("  Uploading to AssemblyAI...")
    try:
        up = requests.post(
            f"{ASSEMBLYAI_API_URL}/upload",
            headers={"authorization": api_key, "content-type": "application/octet-stream"},
            data=audio_bytes, timeout=120,
        )
        up.raise_for_status()
        upload_url = up.json().get("upload_url", "")
        if not upload_url: return None, None
        job = requests.post(
            f"{ASSEMBLYAI_API_URL}/transcript",
            headers={"authorization": api_key, "content-type": "application/json"},
            json={"audio_url": upload_url, "language_code": "uk", "punctuate": True},
            timeout=30,
        )
        job.raise_for_status()
        job_id = job.json().get("id", "")
        if not job_id: return None, None
        safe_print(f"  AssemblyAI polling {job_id}...")
        for _ in range(120):
            time.sleep(5)
            poll = requests.get(f"{ASSEMBLYAI_API_URL}/transcript/{job_id}",
                                headers={"authorization": api_key}, timeout=30)
            poll.raise_for_status()
            res = poll.json()
            status = res.get("status", "")
            if status == "completed":
                text, lang = _ru_guard(safe_text((res.get("text") or "").strip()), res.get("language_code", "uk") or "uk")
                if not text: return None, None
                _log_ok("AssemblyAI", lang, text); return text, lang
            if status == "error":
                safe_print(f"  AssemblyAI job error: {res.get('error','')}")
                return None, None
        safe_print("  AssemblyAI timed out.")
        return None, None
    except requests.HTTPError as e:  _log_http("AssemblyAI", e)
    except Exception as e:           _log_fail("AssemblyAI", e)
    return None, None

def _transcribe_google_stt(audio_bytes: bytes):
    import base64
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        safe_print("  Google STT skipped: GOOGLE_API_KEY not set."); return None, None
    safe_print("  Sending to Google Speech-to-Text...")
    try:
        payload = {
            "config": {"encoding": "MP3", "sampleRateHertz": 16000, "languageCode": "uk-UA",
                       "alternativeLanguageCodes": ["en-US", "pl-PL"], "enableAutomaticPunctuation": True, "model": "latest_long"},
            "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")},
        }
        resp = requests.post(
            GOOGLE_STT_URL, params={"key": api_key},
            headers={"Content-Type": "application/json; charset=utf-8"},
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"), timeout=180,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results: return None, None
        text = safe_text(" ".join(r.get("alternatives", [{}])[0].get("transcript", "") for r in results).strip())
        if not text: return None, None
        _log_ok("Google STT", "uk", text); return text, "uk"
    except requests.HTTPError as e:  _log_http("Google STT", e)
    except Exception as e:           _log_fail("Google STT", e)
    return None, None

def _transcribe_azure(audio_bytes: bytes):
    api_key = os.environ.get("AZURE_SPEECH_KEY", "")
    if not api_key:
        safe_print("  Azure Speech skipped: AZURE_SPEECH_KEY not set."); return None, None
    region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
    url    = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    safe_print("  Sending to Azure Speech Services...")
    try:
        resp = requests.post(
            url, params={"language": "uk-UA", "format": "detailed"},
            headers={"Ocp-Apim-Subscription-Key": api_key, "Content-Type": "audio/mpeg"},
            data=audio_bytes, timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        text = safe_text((data.get("DisplayText") or "").strip())
        if not text: return None, None
        text, lang = _ru_guard(text, "uk")
        _log_ok("Azure Speech", lang, text); return text, lang
    except requests.HTTPError as e:  _log_http("Azure Speech", e)
    except Exception as e:           _log_fail("Azure Speech", e)
    return None, None

def _transcribe_aws(audio_bytes: bytes):
    aws_key    = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    bucket     = os.environ.get("AWS_S3_BUCKET", "")
    if not all([aws_key, aws_secret, bucket]):
        safe_print("  AWS skipped: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_S3_BUCKET not set.")
        return None, None
    safe_print("  Sending to AWS Transcribe...")
    try:
        import boto3
        s3          = boto3.client("s3", aws_access_key_id=aws_key, aws_secret_access_key=aws_secret)
        transcribe  = boto3.client("transcribe", aws_access_key_id=aws_key, aws_secret_access_key=aws_secret)
        s3_key      = f"groq_audio/{uuid.uuid4().hex}.mp3"
        s3.put_object(Bucket=bucket, Key=s3_key, Body=audio_bytes)
        job_name    = f"job-{uuid.uuid4().hex}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name, Media={"MediaFileUri": f"s3://{bucket}/{s3_key}"},
            MediaFormat="mp3", LanguageCode="uk-UA",
        )
        for _ in range(120):
            time.sleep(5)
            res    = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = res["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                result_uri = res["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                tr_data    = requests.get(result_uri, timeout=60).json()
                text       = safe_text(" ".join(t["transcript"] for t in tr_data.get("results", {}).get("transcripts", [])).strip())
                try: s3.delete_object(Bucket=bucket, Key=s3_key)
                except Exception: pass
                if not text: return None, None
                _log_ok("AWS Transcribe", "uk", text); return text, "uk"
            if status == "FAILED":
                safe_print("  AWS Transcribe job failed."); return None, None
        safe_print("  AWS Transcribe timed out.")
    except Exception as e:
        _log_fail("AWS Transcribe", e)
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
#  Audio download (shared by all transcription tiers)
# ══════════════════════════════════════════════════════════════════════════════

def _download_audio(video_url: str, out_path: Path) -> bool:
    import yt_dlp
    _BROWSER_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_path.with_suffix(".%(ext)s")),
        "quiet": True, "no_warnings": True,
        "user_agent": _BROWSER_UA, "referer": "https://www.youtube.com/",
        "http_headers": {"Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7"},
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "96"}],
    }
    cookies_file = Path(__file__).parent / "cookies.txt"
    attempts = [(1, {})]
    if cookies_file.exists():
        attempts.append((2, {"cookiefile": str(cookies_file), "format": "bestaudio/bestvideo+bestaudio/best"}))
        safe_print("  [cookies] Found cookies.txt — will retry with it if needed.")
    else:
        safe_print("  [cookies] No cookies.txt found — trying without cookies.")
    for attempt, extra in attempts:
        try:
            with yt_dlp.YoutubeDL({**ydl_opts, **extra}) as ydl:
                ydl.download([video_url])
            mp3_file = out_path.parent / (out_path.stem + ".mp3")
            if not mp3_file.exists():
                candidates = sorted(f for f in out_path.parent.iterdir()
                                    if f.suffix in {".mp3", ".m4a", ".ogg", ".webm", ".opus"})
                if not candidates:
                    raise FileNotFoundError("No audio file after download")
                candidates[-1].rename(mp3_file)
            if mp3_file.stat().st_size == 0:
                raise ValueError("Downloaded file is empty")
            if mp3_file != out_path:
                mp3_file.rename(out_path)
            return True
        except Exception as e:
            safe_print(f"  Download attempt {attempt} failed: {safe_text(str(e)[:120])}")
    return False


def transcribe_audio(video_url: str):
    """8-tier cloud transcription pipeline. Returns (text, lang) or (None, None)."""
    tmpdir    = Path("C:/groq_tmp") / uuid.uuid4().hex
    audio_out = tmpdir / "audio.mp3"
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        safe_print("  Downloading audio...")
        if not _download_audio(video_url, audio_out):
            return None, None
        audio_bytes = audio_out.read_bytes()
        for tier_name, fn in [
            ("Groq",            _transcribe_groq),
            ("OpenAI Whisper",  _transcribe_openai_whisper),
            ("Deepgram",        _transcribe_deepgram),
            ("AssemblyAI",      _transcribe_assemblyai),
            ("Google STT",      _transcribe_google_stt),
            ("Azure Speech",    _transcribe_azure),
            ("AWS Transcribe",  _transcribe_aws),
        ]:
            text, lang = fn(audio_bytes)
            if text:
                return text, lang
            safe_print(f"  {tier_name} failed → next tier...")
        safe_print("  [FAIL] All transcription tiers failed.")
        return None, None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Batch Groq (for cmd_add with multiple URLs)
# ══════════════════════════════════════════════════════════════════════════════

def _build_batches(audio_items: list) -> list:
    """Split audio_items into sub-batches that fit within GROQ_MAX_BATCH_MB."""
    import subprocess, tempfile
    MAX_BYTES = GROQ_MAX_BATCH_MB * 1_048_576
    batches, current, current_size = [], [], 0
    for label, ab in audio_items:
        # Re-encode to speech quality to estimate final size
        est = len(ab) * (GROQ_SPEECH_KBPS * 1000 / 8) / max(len(ab), 1)
        if current and current_size + len(ab) > MAX_BYTES:
            batches.append(current)
            current, current_size = [], 0
        current.append((label, ab))
        current_size += len(ab)
    if current:
        batches.append(current)
    return batches

def _concat_with_silence(audio_list: list, gap: float = GROQ_SILENCE_GAP):
    """Concatenate MP3 bytes with silence gaps. Returns (combined_bytes, offsets, durations)."""
    import subprocess, tempfile, struct
    _tmpdir = Path(tempfile.mkdtemp())
    try:
        paths, durations = [], []
        for i, ab in enumerate(audio_list):
            p = _tmpdir / f"part_{i:04d}.mp3"
            p.write_bytes(ab)
            # Get duration via ffprobe
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                    capture_output=True, text=True, timeout=30,
                )
                dur = float(r.stdout.strip())
            except Exception:
                dur = len(ab) / (128 * 1000 / 8)  # fallback: assume 128kbps
            # Re-encode to speech quality
            out_p = _tmpdir / f"reenc_{i:04d}.mp3"
            subprocess.run(
                ["ffmpeg", "-i", str(p), "-ar", "16000", "-ac", "1",
                 "-b:a", f"{GROQ_SPEECH_KBPS}k", str(out_p), "-y"],
                capture_output=True, check=True, timeout=120,
            )
            paths.append(out_p)
            durations.append(dur)
        # Silence file
        silence = _tmpdir / "silence.mp3"
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono",
             "-t", str(gap), "-b:a", f"{GROQ_SPEECH_KBPS}k", str(silence), "-y"],
            capture_output=True, check=True, timeout=30,
        )
        # Concat list
        clist = _tmpdir / "concat.txt"
        lines = []
        for i, p in enumerate(paths):
            lines.append(f"file '{p}'\n")
            if i < len(paths) - 1:
                lines.append(f"file '{silence}'\n")
        clist.write_text("".join(lines), encoding="utf-8")
        out = _tmpdir / "combined.mp3"
        subprocess.run(
            ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(clist), "-c", "copy", str(out), "-y"],
            capture_output=True, check=True, timeout=120,
        )
        combined = out.read_bytes()
        offsets, t = [], 0.0
        for dur in durations:
            offsets.append(t)
            t += dur + gap
        return combined, offsets, durations
    finally:
        shutil.rmtree(_tmpdir, ignore_errors=True)

def _batch_groq_transcribe(audio_items: list) -> list:
    if not audio_items:
        return []
    if len(audio_items) == 1:
        return [_transcribe_groq(audio_items[0][1])]
    sub_batches = _build_batches(audio_items)
    result_map  = {}
    for bi, sub in enumerate(sub_batches, 1):
        safe_print(f"  [batch-groq] Sub-batch {bi}/{len(sub_batches)}: {len(sub)} video(s)")
        try:
            combined, offsets, durations = _concat_with_silence([ab for _, ab in sub])
        except Exception as e:
            safe_print(f"  [batch-groq] Concat failed ({e}). Falling back individually.")
            for lbl, ab in sub:
                result_map[lbl] = _transcribe_groq(ab)
            continue
        try:
            _, lang, segments = _groq_post_full(combined)
        except Exception as e:
            safe_print(f"  [batch-groq] Groq failed ({e}). Falling back.")
            for lbl, ab in sub:
                result_map[lbl] = _transcribe_groq(ab)
            continue
        for i, (lbl, ab) in enumerate(sub):
            start_off = offsets[i]
            end_off   = start_off + durations[i] + 0.5
            parts     = [seg.get("text", "") for seg in segments
                         if start_off - 0.3 <= seg.get("start", 0.0) < end_off]
            video_text = " ".join(parts).strip()
            if video_text:
                video_text, lang_i = _ru_guard(video_text, lang)
                result_map[lbl] = (video_text or None, lang_i)
            else:
                result_map[lbl] = _transcribe_groq(ab)
    return [result_map.get(lbl, (None, None)) for lbl, _ in audio_items]


# ══════════════════════════════════════════════════════════════════════════════
#  KeyBERT topic extraction
# ══════════════════════════════════════════════════════════════════════════════

_STOPWORDS = {
    "але","або","бо","від","все","для","до","є","за","із","коли","між",
    "на","не","по","при","про","так","там","тут","що","це","чи","через",
    "the","and","for","that","this","with","from","you","danger",
}

def extract_topics(text: str, n: int = 12):
    sbert   = _get_sbert()
    keybert = _get_keybert()
    if not text or not text.strip():
        return [], sbert.encode("").tolist()
    try:
        raw = keybert.extract_keywords(
            text, keyphrase_ngram_range=(1, 3),
            stop_words=list(_STOPWORDS), top_n=n,
            use_mmr=True, diversity=0.55,
        )
        keywords = [kw for kw, sc in raw if sc >= 0.20]
    except Exception as e:
        safe_print(f"  KeyBERT error: {safe_text(str(e))}")
        keywords = []
    if len(keywords) < 3:
        toks   = [w for w in tokenize(text) if w not in _STOPWORDS]
        extras = [w for w, _ in Counter(toks).most_common(20) if w not in keywords]
        keywords += extras[:n - len(keywords)]
    if not keywords:
        return [], sbert.encode(text[:512]).tolist()
    w    = np.array([1.0 / (i + 1) for i in range(len(keywords))], dtype=np.float32)
    w   /= w.sum()
    embs = sbert.encode(keywords, show_progress_bar=False)
    emb  = (w[:, None] * embs).sum(axis=0)
    preview = safe_text(", ".join(keywords[:8])) + ("..." if len(keywords) > 8 else "")
    safe_print(f"  -> topics: {preview}")
    return keywords, emb.tolist()


# ══════════════════════════════════════════════════════════════════════════════
#  CLIP visual analysis
# ══════════════════════════════════════════════════════════════════════════════

def extract_visual_embedding(video_url: str, max_frames: int = MAX_FRAMES):
    import cv2, torch, yt_dlp, tempfile, gc
    from PIL import Image
    gc.collect()
    with tempfile.TemporaryDirectory() as tmpdir:
        cookies_file = Path(__file__).parent / "cookies.txt"
        ydl_opts = {
            "format": "worstvideo[ext=mp4]/worstvideo/worst",
            "outtmpl": os.path.join(tmpdir, "video.%(ext)s"),
            "quiet": True, "no_warnings": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "referer": "https://www.youtube.com/",
            "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
        }
        if cookies_file.exists():
            ydl_opts["cookiefile"] = str(cookies_file)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            safe_print(f"  Video download failed: {safe_text(str(e))}")
            return None
        files = list(Path(tmpdir).iterdir())
        if not files: return None
        cap     = cv2.VideoCapture(str(sorted(files)[-1]))
        n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n_total < 1: cap.release(); return None
        frames = []
        for idx in np.linspace(0, n_total - 1, min(max_frames, n_total), dtype=int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, fr = cap.read()
            if ok: frames.append(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
        cap.release()
        if not frames: return None
        safe_print(f"  Encoding {len(frames)} frame(s) with CLIP...")
        try:
            clip_model, clip_proc = _get_clip()
        except RuntimeError as oom:
            if "memory" in str(oom).lower():
                safe_print("  [CLIP] Not enough RAM — skipping visual."); return None
            raise
        feats = []
        for i in range(0, len(frames), 8):
            inp = clip_proc(images=frames[i:i+8], return_tensors="pt", padding=True)
            with torch.no_grad():
                feats.append(clip_model.get_image_features(**inp).cpu().numpy())
        emb  = np.concatenate(feats).mean(axis=0)
        norm = np.linalg.norm(emb)
        return (emb / norm).tolist() if norm > 0 else emb.tolist()

def clip_encode_text(query: str) -> list:
    import torch
    clip_model, clip_proc = _get_clip()
    inp = clip_proc(text=[query], return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        emb = clip_model.get_text_features(**inp).cpu().numpy()[0]
    norm = np.linalg.norm(emb)
    return (emb / norm).tolist() if norm > 0 else emb.tolist()


# ══════════════════════════════════════════════════════════════════════════════
#  Index one video  →  save into video_db.json
# ══════════════════════════════════════════════════════════════════════════════

def index_video(url: str, no_visual: bool, frames: int, db_path: str,
                prefetched_transcript=None, prefetched_lang=None) -> bool:
    """
    Index one video and append it to db_path (video_db.json).
    Returns True=added, False=failed, None=skipped.
    """
    video_id = extract_video_id(url)
    if not video_id:
        safe_print(f"  [SKIP] Cannot extract video ID from: {url}")
        return False

    db = load_db(db_path)
    if any(e.get("video_id") == video_id for e in db):
        safe_print(f"  [SKIP] Already indexed: {url}")
        return None

    safe_print(f"\n{'='*60}")
    safe_print(f"  Indexing: {url}")
    safe_print(f"{'='*60}")

    # ── Title ─────────────────────────────────────────────────────────
    safe_print("[1/4] Fetching title...")
    title = fetch_title(video_id)
    safe_print(f"  title: {safe_text(title)!r}" if title else "  title: (not available)")

    # ── Transcript ────────────────────────────────────────────────────
    safe_print("[2/4] Fetching transcript...")
    if prefetched_transcript:
        transcript, lang = prefetched_transcript, prefetched_lang or "uk"
        safe_print("  transcript: pre-fetched via batch Groq")
    else:
        transcript, lang = fetch_transcript(video_id)
        if not transcript:
            transcript, lang = transcribe_audio(url)
    if not transcript:
        safe_print("  [FAIL] No transcript available.")
        return False
    safe_print(f"  lang={lang}  words={len(transcript.split())}")

    # ── SBERT embeddings + KeyBERT ────────────────────────────────────
    safe_print("[3/4] Encoding with SBERT + KeyBERT topics...")
    sbert               = _get_sbert()
    transcript_emb      = sbert.encode(transcript).tolist()
    title_emb           = sbert.encode(title).tolist() if title else transcript_emb
    tokens              = tokenize(transcript + " " + title)
    keywords, topic_emb = extract_topics(transcript, n=12)

    # ── CLIP visual ───────────────────────────────────────────────────
    visual_emb = None
    if not no_visual:
        safe_print("[4/4] CLIP visual analysis...")
        visual_emb = extract_visual_embedding(url, max_frames=frames)
        safe_print(f"  visual: {'dim=' + str(len(visual_emb)) if visual_emb else 'skipped'}")
    else:
        safe_print("[4/4] Visual analysis skipped (--no-visual).")

    # ── Save to video_db.json ─────────────────────────────────────────
    db = load_db(db_path)
    db.append({
        "video_url":      url,
        "video_id":       video_id,
        "lang":           lang,
        "title":          title,
        "transcript":     transcript,
        "tokens":         tokens,
        "transcript_emb": transcript_emb,
        "title_emb":      title_emb,
        "topic_emb":      topic_emb,
        "visual_emb":     visual_emb,
        "topics":         keywords,
    })
    save_db(db_path, db)
    safe_print(f"\n  [OK] Saved ({len(db)} total entries in {db_path})")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  Scoring  (query → vector similarity + keyword boost — no extra models)
# ══════════════════════════════════════════════════════════════════════════════

def _keyword_ratio(query_tokens: set, text: str) -> float:
    """
    Fraction of query tokens that appear as a substring in `text`.
    Works for partial matches: query "Олена" matches "Оленою" in transcript.
    """
    if not query_tokens or not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for qt in query_tokens if qt in text_lower)
    return hits / len(query_tokens)

def score_entry(entry: dict, q_vec: np.ndarray, q_tokens: set,
                q_clip=None, query_lang: str = "?") -> dict:
    """
    Hybrid score = vector similarity + keyword-match boost.

    Signals (all computed with numpy — no scipy/sklearn):
      1. transcript_sim  — cosine(query, transcript_emb)  × W_TRANSCRIPT
      2. title_sim       — cosine(query, title_emb)        × W_TITLE
      3. keyword_title   — fraction of query words in title text   (tiered bonus)
      4. keyword_body    — fraction of query words in transcript   (tiered bonus)
      5. topic_bonus     — cosine(query, topic_emb)                (tiered bonus)
      6. visual_bonus    — cosine(query_clip, visual_emb)          (opt-in)
      7. lang_bonus      — ±0.15 same/mismatch, -0.35 CrTat penalty

    Signals 3+4 are the "hybrid keyword layer": they guarantee that videos
    containing the exact queried name/term always rank higher than videos that
    are only semantically similar.
    """
    t_vec  = np.array(entry.get("transcript_emb", []), dtype=np.float32)
    ti_vec = np.array(entry.get("title_emb",      []), dtype=np.float32)
    tp_vec = np.array(entry.get("topic_emb",       []), dtype=np.float32)

    t_sim  = cosine(q_vec, t_vec)
    ti_sim = cosine(q_vec, ti_vec)
    tp_sim = cosine(q_vec, tp_vec) if tp_vec.size else 0.0

    tp_bonus = tiered(tp_sim, TOPIC_TIERS)

    # ── Keyword boost (hybrid layer — the key fix for exact names) ─────────
    title_text = entry.get("title", "")
    body_text  = entry.get("transcript", "")
    kw_title   = _keyword_ratio(q_tokens, title_text)
    kw_body    = _keyword_ratio(q_tokens, body_text)
    kw_title_bonus = tiered(kw_title, KEYWORD_TITLE_TIERS)
    kw_body_bonus  = tiered(kw_body,  KEYWORD_BODY_TIERS)

    # ── Visual ─────────────────────────────────────────────────────────────
    v_sim, v_bonus = 0.0, 0.0
    if q_clip is not None and entry.get("visual_emb"):
        v_sim   = cosine(np.array(q_clip, dtype=np.float32),
                         np.array(entry["visual_emb"], dtype=np.float32))
        v_bonus = tiered(v_sim, VISUAL_TIERS)

    # ── Language bonus / penalty ───────────────────────────────────────────
    lang_bonus  = 0.0
    title_lower = title_text.lower()
    if query_lang != "?":
        entry_lang = entry.get("lang", "?")
        e2 = (entry_lang or "")[:2].lower()
        q2 = query_lang[:2].lower()
        if entry_lang not in ("?", ""):
            lang_bonus += 0.15 if e2 == q2 else -0.15
        # Crimean Tatar mislabeled as 'uk' — detect from title
        _CT = ("кримськотатарська", "qırımtatar", "крымскотатарск")
        if any(m in title_lower for m in _CT) and q2 == "uk":
            lang_bonus -= 0.35

    total = (
        W_TRANSCRIPT   * t_sim
        + W_TITLE      * ti_sim
        + kw_title_bonus
        + kw_body_bonus
        + tp_bonus
        + v_bonus
        + lang_bonus
    )

    return {
        "url":              entry.get("video_url", ""),
        "title":            title_text,
        "lang":             entry.get("lang", "?"),
        "total":            total,
        "t_sim":            t_sim,
        "ti_sim":           ti_sim,
        "kw_title":         kw_title,
        "kw_title_bonus":   kw_title_bonus,
        "kw_body":          kw_body,
        "kw_body_bonus":    kw_body_bonus,
        "tp_sim":           tp_sim,
        "tp_bonus":         tp_bonus,
        "v_sim":            v_sim,
        "v_bonus":          v_bonus,
        "lang_bonus":       lang_bonus,
        "has_visual":       bool(entry.get("visual_emb")),
        "topics":           entry.get("topics", []),
        "has_emb":          bool(entry.get("transcript_emb")),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Commands
# ══════════════════════════════════════════════════════════════════════════════

def cmd_list(args):
    """Print every video in the database — no models loaded."""
    safe_print(f"\n  DB path: {os.path.abspath(args.db)}")
    db = load_db(args.db, verbose=True)
    if not db:
        safe_print(
            "  Database is empty or file not found.\n"
            "  Index a video with:\n"
            "    python Finder.py add https://youtu.be/VIDEO_ID --no-visual\n"
            "  Or point to your DB:\n"
            f"    python Finder.py --db video_db.json list"
        )
        return

    safe_print(f"\n{'-'*90}")
    safe_print(f"  {'#':<5} {'Lang':<5} {'Emb':>4} {'Visual':>6} {'Words':>6}  Title")
    safe_print(f"{'-'*90}")

    no_emb = 0
    for i, e in enumerate(db, 1):
        has_v   = "yes" if e.get("visual_emb") else " no"
        has_e   = " ✓" if e.get("transcript_emb") else " ✗"
        words   = len(e.get("transcript", "").split())
        title   = safe_text((e.get("title") or e.get("video_url", ""))[:60])
        if not e.get("transcript_emb"):
            no_emb += 1
        safe_print(f"  {i:<5} {e.get('lang','?'):<5} {has_e:>4} {has_v:>6} {words:>6}  {title}")

    safe_print(f"{'-'*90}")
    safe_print(f"  Total: {len(db)} video(s)")
    if no_emb:
        safe_print(
            f"\n  ⚠️  {no_emb} entries have no embedding (✗)."
            f"\n  Run  python Finder.py reindex  to generate missing embeddings."
        )
    else:
        safe_print("  ✅ All entries have embeddings and are ready to search.")
    safe_print("")


def cmd_search(args):
    safe_print(f"\n  DB path: {os.path.abspath(args.db)}")
    db = load_db(args.db, verbose=True)
    if not db:
        return

    # Count how many entries actually have embeddings
    has_emb = [e for e in db if e.get("transcript_emb")]
    no_emb  = len(db) - len(has_emb)
    if no_emb:
        safe_print(
            f"  ⚠️  {no_emb}/{len(db)} entries have no embedding — they will be skipped.\n"
            f"  Run  python Finder.py reindex  to fix this."
        )
    if not has_emb:
        safe_print("  No entries with embeddings found. Run 'reindex' first.")
        return

    # ── Encode query ─────────────────────────────────────────────────────────
    query    = args.query
    q_lang   = _detect_query_lang(query)
    q_tokens = set(tokenize(query))
    safe_print(f"  Query: \"{safe_text(query)}\"  lang={q_lang}  tokens={sorted(q_tokens)}")

    sbert = _get_sbert()
    q_vec = sbert.encode(query)

    q_clip = None
    if args.with_visual:
        safe_print("  Loading CLIP for visual similarity...")
        q_clip = clip_encode_text(query)

    # ── Score all entries with embeddings ────────────────────────────────────
    results = [
        score_entry(e, q_vec, q_tokens, q_clip, query_lang=q_lang)
        for e in has_emb
    ]
    results.sort(key=lambda x: x["total"], reverse=True)

    n       = min(args.top, len(results))
    best    = results[0]["total"] if results else 0.0

    if best < SIMILARITY_THRESHOLD:
        safe_print(
            f"\n  ⚠️  Best score ({best:.4f}) is below the quality threshold "
            f"({SIMILARITY_THRESHOLD}). The query may be too specific or "
            f"the relevant video may not be indexed yet.\n"
        )

    safe_print(f"\n  Top {n} results (out of {len(results)} searchable entries):\n")
    safe_print(
        f"  {'#':<4} {'Score':>7}  {'VecSim':>7}  {'KwTitle':>8}  "
        f"{'KwBody':>8}  {'Lang':>6}  Title"
    )
    safe_print("  " + "-" * 80)

    for i, r in enumerate(results[:n], 1):
        below  = " ⚠" if r["total"] < SIMILARITY_THRESHOLD else ""
        vis    = " [V]" if r["has_visual"] else ""
        vec_s  = r["t_sim"] * W_TRANSCRIPT + r["ti_sim"] * W_TITLE
        url_s  = r["url"][:55] + ("..." if len(r["url"]) > 55 else "")
        title_s = safe_text((r["title"] or url_s)[:65])

        safe_print(
            f"  {i:<4} {r['total']:>7.4f}  {vec_s:>7.4f}  "
            f"{r['kw_title']:>7.0%}  "
            f"{r['kw_body']:>7.0%}  "
            f"{r['lang_bonus']:>+6.2f}  "
            f"{title_s}{vis}{below}"
        )

        # Show keyword match details when they contributed
        hints = []
        if r["kw_title_bonus"] > 0:
            hits = [qt for qt in q_tokens if qt in r["title"].lower()]
            hints.append(f"title words matched: {', '.join(hits)}")
        if r["kw_body_bonus"] > 0 and r["kw_title_bonus"] == 0:
            hints.append(f"found in transcript ({r['kw_body']:.0%} of query words)")
        if hints:
            safe_print(f"        ↳ {' | '.join(hints)}")

        kws = safe_text(", ".join(r["topics"][:6]))
        if kws:
            safe_print(f"        topics: {kws}")
        safe_print("")


def cmd_reindex(args):
    """
    Generate (or regenerate) SBERT embeddings for entries that are missing them.
    Safe to re-run — entries that already have embeddings are skipped unless
    --force is passed.
    """
    db = load_db(args.db, verbose=True)
    if not db:
        return

    force    = getattr(args, "force", False)
    to_index = [e for e in db if force or not e.get("transcript_emb")]

    safe_print(
        f"\n  {len(to_index)}/{len(db)} entries need indexing"
        f"{' (forced)' if force else ''}."
    )
    if not to_index:
        safe_print("  ✅ All entries already have embeddings. Nothing to do.")
        safe_print("     Use --force to regenerate all embeddings.")
        return

    sbert   = _get_sbert()
    updated = 0

    for i, entry in enumerate(db):
        if not force and entry.get("transcript_emb"):
            continue

        transcript = entry.get("transcript", "")
        title      = entry.get("title", "")
        label      = safe_text((title or entry.get("video_url", "?"))[:60])
        safe_print(f"  [{updated+1}/{len(to_index)}] {label}")

        if not transcript:
            safe_print("    -> no transcript, skipping.")
            continue

        entry["transcript_emb"] = sbert.encode(transcript).tolist()
        entry["title_emb"]      = sbert.encode(title).tolist() if title else entry["transcript_emb"]
        entry["tokens"]         = tokenize(transcript + " " + title)

        if not entry.get("topic_emb") or force:
            keywords, topic_emb  = extract_topics(transcript, n=12)
            entry["topic_emb"]   = topic_emb
            entry["topics"]      = keywords

        updated += 1
        # Checkpoint every 20 entries so progress isn't lost on interruption
        if updated % 20 == 0:
            save_db(args.db, db)
            safe_print(f"    [checkpoint] Saved after {updated} updates.")

    save_db(args.db, db)
    safe_print(f"\n  ✅ Done. {updated} entrie(s) updated. Saved to {args.db}.")


def cmd_topics(args):
    db = load_db(args.db)
    if not db:
        safe_print("Database is empty."); return
    for entry in db:
        safe_print(f"\n{'-'*64}")
        safe_print(f"  [{entry.get('lang','?')}] {safe_text(entry.get('title','') or '(no title)')}")
        safe_print(f"  {entry.get('video_url','')}")
        topics = entry.get("topics", [])
        if not topics:
            safe_print("  (no topics)")
        else:
            for i, kw in enumerate(topics, 1):
                safe_print(f"    {i:>2}. {safe_text(kw)}")


def _cmd_add_pass(urls, args) -> tuple:
    ok = fail = skip = 0
    db_cache    = load_db(args.db)
    indexed_ids = {e.get("video_id") for e in db_cache}
    PROGRESS_CHUNK = 20
    chunks = [urls[i:i+PROGRESS_CHUNK] for i in range(0, len(urls), PROGRESS_CHUNK)]
    url_counter = 0
    for chunk in chunks:
        pending = []
        for url in chunk:
            url_counter += 1
            safe_print(f"\n[{url_counter}/{len(urls)}] {url}")
            vid = extract_video_id(url)
            if not vid:
                safe_print("  [SKIP] Cannot extract video ID."); skip += 1; continue
            if vid in indexed_ids:
                safe_print("  [SKIP] Already indexed."); skip += 1; continue
            pending.append((url, vid))
        if not pending:
            continue
        need_audio, transcripts = [], {}
        for url, vid in pending:
            t, l = fetch_transcript(vid)
            if t: transcripts[vid] = (t, l)
            else: need_audio.append((url, vid))
        if need_audio:
            safe_print(f"\n  [batch] {len(need_audio)} video(s) need Groq. Downloading audio...")
            audio_items = []
            for url, vid in need_audio:
                safe_print(f"  Downloading: {url}")
                tmpdir    = Path("C:/groq_tmp") / uuid.uuid4().hex
                audio_out = tmpdir / "audio.mp3"
                tmpdir.mkdir(parents=True, exist_ok=True)
                try:
                    if _download_audio(url, audio_out):
                        audio_items.append((url, audio_out.read_bytes()))
                    else:
                        safe_print(f"  [FAIL] Audio download failed: {url}")
                        audio_items.append((url, None))
                except Exception as e:
                    safe_print(f"  [FAIL] {safe_text(str(e))}"); audio_items.append((url, None))
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)
            valid_items = [(url, ab) for url, ab in audio_items if ab is not None]
            failed_urls = {url for url, ab in audio_items if ab is None}
            if valid_items:
                batch_results = _batch_groq_transcribe(valid_items)
                for (url, _), (t, l) in zip(valid_items, batch_results):
                    vid = extract_video_id(url)
                    if t: transcripts[vid] = (t, l)
                    else: failed_urls.add(url)
                import gc; gc.collect()
            for url in failed_urls:
                vid = extract_video_id(url)
                if vid: transcripts[vid] = (None, None)
        for url, vid in pending:
            t, l   = transcripts.get(vid, (None, None))
            result = index_video(
                url=url, no_visual=args.no_visual, frames=args.frames,
                db_path=args.db, prefetched_transcript=t, prefetched_lang=l,
            )
            if result is True:   ok += 1; indexed_ids.add(vid)
            elif result is None: skip += 1
            else:                fail += 1
    return ok, fail, skip


def cmd_add(args):
    urls = args.urls
    if len(urls) == 1:
        index_video(url=urls[0], no_visual=args.no_visual, frames=args.frames, db_path=args.db)
        return
    safe_print(f"\n  Batch mode: {len(urls)} URL(s). Press Ctrl+C to stop.")
    pass_num = total_added = 0
    try:
        while True:
            pass_num += 1
            t0 = time.time()
            safe_print(f"\n{'='*60}\n  Pass #{pass_num} — {len(urls)} URL(s)\n{'='*60}")
            ok, fail, skip = _cmd_add_pass(urls, args)
            elapsed = time.time() - t0
            total_added += ok
            safe_print(
                f"\n  Pass #{pass_num} done in {elapsed:.0f}s  "
                f"OK={ok}  SKIP={skip}  FAIL={fail}  Total added={total_added}"
            )
            if fail == 0 and ok == 0:
                safe_print("  All videos indexed. Stopping."); break
            safe_print("  Starting next pass... (Ctrl+C to stop)")
    except KeyboardInterrupt:
        safe_print(f"\n  Stopped. Total added: {total_added}.")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        prog="finder",
        description=(
            "YouTube semantic search\n"
            "Single DB: video_db.json\n"
            "Search = SBERT vector similarity + keyword boost (hybrid, no extra models)\n"
            "Transcription: 8-tier cloud fallback (Groq → OpenAI → Deepgram → ...)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--db", default=DB_FILE, help=f"Database file (default: {DB_FILE})")
    sub = p.add_subparsers(dest="command", required=True)

    # add
    ap = sub.add_parser("add", help="Index one or more YouTube videos.")
    ap.add_argument("urls", nargs="+", metavar="URL")
    ap.add_argument("--no-visual", action="store_true", help="Skip CLIP visual analysis.")
    ap.add_argument("--frames", type=int, default=MAX_FRAMES)
    ap.set_defaults(func=cmd_add)

    # search
    sp = sub.add_parser("search", help="Search indexed videos.")
    sp.add_argument("query")
    sp.add_argument("--top", type=int, default=10, help="Results to show (default 10).")
    sp.add_argument("--with-visual", action="store_true", dest="with_visual",
                    help="Include CLIP visual signal (loads CLIP model).")
    sp.set_defaults(func=cmd_search)

    # list
    ls = sub.add_parser("list", help="List all indexed videos.")
    ls.set_defaults(func=cmd_list)

    # reindex
    ri = sub.add_parser("reindex", help="Generate missing SBERT embeddings for existing entries.")
    ri.add_argument("--force", action="store_true",
                    help="Regenerate embeddings even for entries that already have them.")
    ri.set_defaults(func=cmd_reindex)

    # topics
    tp = sub.add_parser("topics", help="Print stored keywords for each video.")
    tp.set_defaults(func=cmd_topics)

    # ── Optional: read command from finder_command.txt ────────────────────────
    if len(sys.argv) == 1:
        cmd_file = Path(__file__).parent / "finder_command.txt"
        if not cmd_file.exists():
            p.print_help()
            return
        raw = cmd_file.read_text(encoding="utf-8").strip()
        if not raw:
            safe_print(f"[cmd] {cmd_file.name} is empty — nothing to do.")
            return
        raw = re.sub(r"^python\S*\s+\S*[Ff]inder\S*\s*", "", raw).strip()
        safe_print(f"[cmd] Running: {raw[:120]}")
        import shlex
        sys.argv.extend(shlex.split(raw))

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()