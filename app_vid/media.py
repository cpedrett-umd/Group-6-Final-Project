"""Video and audio ads -> text, and text -> a map of where each tactic sits.

Three ways in: a link to a post, an uploaded recording, or audio captured in
the browser. All three end up as the same thing -- a transcript, plus whatever
text is burned into the frames -- and both go to the same classifier the text
and image paths use.

Why this needs its own module rather than reusing the image path.

A video ad is not one ad. A 60-second clip carries several tactics in sequence:
one measured clip spent 57 seconds dismissing every alternative approach and
3 seconds naming the product. Classifying the whole transcript at once returns
a single label, which is both wrong and less useful than saying where each
tactic sits.

So the transcript is split into windows and each is classified separately. Two
constraints shape the windowing:

  * The classifier's window is 128 subwords, and it was fine-tuned on ads
    averaging 22 words. A 600-word transcript is far outside that, so the
    windows are sized to land inside it.
  * Splitting at a fixed word count cuts mid-sentence, and fragments produce
    confident nonsense -- measured: a dosage instruction came back as Fear
    Appeals at 99% when classified alone. Windows are therefore built from
    whole sentences.

Needs yt-dlp for links, faster-whisper for audio, opencv for frames. Each is
imported lazily so the app still starts without them.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

# Words per window. Roughly 130 subwords once tokenized, so a window lands just
# around the model's limit while still holding a complete thought.
WINDOW_WORDS = 100

# Transcripts longer than this are truncated. A two-minute ad is already well
# past the point where more text adds signal, and every window costs a forward
# pass.
MAX_WORDS = 600

# Frames sampled from a video, spread across its whole duration.
MAX_FRAMES = 6

# Difference-hash distance below which two frames count as the same shot.
# An average hash was tried first and judged three visibly different title
# cards identical (7-11 bits of 256) -- it tracks brightness layout, and text
# on a flat background barely moves it. dHash tracks edges instead.
DISTINCT_BITS = 20

FETCH_TIMEOUT = 120

PLATFORMS = [
    ("instagram", re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", re.I)),
    ("youtube",   re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})", re.I)),
    ("tiktok",    re.compile(r"tiktok\.com/@[\w.]+/video/(\d+)", re.I)),
    ("facebook",  re.compile(r"(?:facebook\.com|fb\.watch)/", re.I)),
    ("x",         re.compile(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", re.I)),
]

# Cache downloads: a demo that re-fetches on every click depends on the
# platform cooperating, and Instagram frequently does not.
CACHE = Path(tempfile.gettempdir()) / "adinsight_media"
CACHE.mkdir(exist_ok=True)


class MediaError(RuntimeError):
    """Anything that stops a clip becoming text, with a message for the user."""


# ── Fetching ──────────────────────────────────────────────────────────

def identify(url: str):
    for name, pattern in PLATFORMS:
        match = pattern.search(url or "")
        if match:
            return name, (match.group(1) if match.groups() else None)
    return "unknown", None


def tools_available() -> dict:
    available = {"yt_dlp": shutil.which("yt-dlp") is not None}

    for name, module in [("whisper", "faster_whisper"), ("frames", "cv2")]:
        try:
            __import__(module)
            available[name] = True
        except ImportError:
            available[name] = False

    return available


def fetch_url(url: str) -> Path:
    """Download a post's media. Raises MediaError with a usable message."""
    if not shutil.which("yt-dlp"):
        raise MediaError(
            "Link support needs yt-dlp. Install it with: pip install yt-dlp"
        )

    platform, ident = identify(url)
    stem = f"{platform}_{ident or int(time.time())}"

    cached = [p for p in CACHE.iterdir() if p.stem == stem]
    if cached:
        return cached[0]

    command = [
        "yt-dlp", url,
        "-f", "best[ext=mp4]/best",
        "-o", str(CACHE / f"{stem}.%(ext)s"),
        "--no-playlist", "--no-warnings", "--socket-timeout", "20",
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=FETCH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise MediaError(
            f"That {platform} link took too long to load. Try again, or upload "
            "a screen recording of the ad instead."
        )

    if result.returncode != 0:
        # The platform's own reason is what the user needs. "Couldn't fetch
        # that" leaves them with nothing to do about it.
        stderr = (result.stderr or "").lower()

        if "429" in stderr or "rate" in stderr:
            raise MediaError(
                f"{platform.title()} is limiting requests right now. Wait a "
                "minute and try again, or upload a screen recording instead."
            )
        if any(word in stderr for word in ("private", "login", "sign in")):
            raise MediaError(
                "That post is private or needs a sign-in, so it can't be read "
                "from the link. A screen recording of it will work."
            )
        if any(word in stderr for word in ("unavailable", "removed", "deleted")):
            raise MediaError("That post is no longer available.")

        raise MediaError(
            f"Couldn't read that {platform} link. Uploading a screen recording "
            "of the ad usually works when a link doesn't."
        )

    found = [p for p in CACHE.iterdir() if p.stem == stem]

    if not found:
        raise MediaError("The download finished but produced no file.")

    return found[0]


def save_upload(file_storage) -> Path:
    """Write an uploaded recording to a temp file for the decoders to open."""
    suffix = Path(file_storage.filename or "clip.mp4").suffix or ".mp4"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                         dir=str(CACHE))
    file_storage.save(handle.name)
    handle.close()
    return Path(handle.name)


# ── Audio ─────────────────────────────────────────────────────────────

_whisper = None


def transcribe(path: Path, model_size: str = "base") -> dict:
    global _whisper

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise MediaError(
            "Audio needs faster-whisper. Install it with: pip install faster-whisper"
        )

    if _whisper is None:
        _whisper = WhisperModel(model_size, device="cpu", compute_type="int8")

    try:
        segments, info = _whisper.transcribe(str(path))
        parts = [(round(s.start, 1), s.text.strip()) for s in segments]
    except Exception as error:
        raise MediaError(f"Couldn't read the audio from that file. ({error})")

    return {
        "text": " ".join(t for _, t in parts).strip(),
        "segments": parts,
        "language": getattr(info, "language", None),
    }


# ── Frames ────────────────────────────────────────────────────────────

def sample_frames(path: Path, max_frames: int = MAX_FRAMES):
    """Stills spread across the clip, near-duplicates dropped.

    Spread rather than a fixed interval: an interval plus a frame cap only ever
    sees the opening seconds, which on a two-minute clip misses the pitch
    entirely.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return [], 0.0

    def dhash(bgr, size=32):
        grey = cv2.cvtColor(cv2.resize(bgr, (size + 1, size)), cv2.COLOR_BGR2GRAY)
        return (grey[:, 1:] > grey[:, :-1]).flatten()

    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 24
    duration = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) / fps if fps else 0

    if duration <= 0:
        capture.release()
        return [], 0.0

    step = max(0.5, duration / max_frames)
    kept, hashes, seconds = [], [], 0.0

    while seconds < duration and len(kept) < max_frames:
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = capture.read()

        if not ok:
            break

        h = dhash(frame)

        if all(int(np.count_nonzero(h != prev)) >= DISTINCT_BITS for prev in hashes):
            hashes.append(h)
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                kept.append((round(seconds, 1), buffer.tobytes()))

        seconds += step

    capture.release()
    return kept, duration


def read_frames(frames, extract_text):
    """Text burned into the frames, merged with order-preserving dedup.

    `extract_text` is ocr.extract_text, so this path uses whichever backend the
    image path is using. Dedup matches server.py's multi-frame merge, so a
    caption held across several frames contributes once.
    """
    merged, seen, per_frame = [], set(), []

    for timestamp, image_bytes in frames:
        try:
            lines = extract_text(image_bytes)["lines"]
        except Exception:
            continue

        per_frame.append({"at": timestamp, "text": " ".join(lines)})

        for line in lines:
            key = " ".join(line.lower().split())
            if key and key not in seen:
                seen.add(key)
                merged.append(line)

    return " ".join(merged), per_frame


# ── Windowing ─────────────────────────────────────────────────────────

_SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'(])')


def split_windows(text: str, window_words: int = WINDOW_WORDS,
                  max_words: int = MAX_WORDS):
    """Group whole sentences into windows of roughly `window_words`.

    Sentence boundaries rather than a word count, because a window that starts
    mid-clause is out of distribution for a model fine-tuned on complete ads --
    fragments produce confident wrong answers rather than uncertain ones.
    """
    words = text.split()

    if len(words) > max_words:
        text = " ".join(words[:max_words])
        truncated = True
    else:
        truncated = False

    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]

    if not sentences:
        return ([text] if text.strip() else []), truncated

    windows, current, count = [], [], 0

    for sentence in sentences:
        length = len(sentence.split())

        # A single sentence longer than the window still gets its own window
        # rather than being cut -- better one oversized pass than a fragment.
        if current and count + length > window_words:
            windows.append(" ".join(current))
            current, count = [], 0

        current.append(sentence)
        count += length

    if current:
        windows.append(" ".join(current))

    return windows, truncated


def analyse_windows(text, predict_fn, build_tactics_fn, low_confidence):
    """Classify each window and report where each tactic sits.

    Returns per-window results plus an aggregate. The aggregate is a union, not
    an average: a tactic used once in the closing seconds is present in the ad,
    and averaging would dilute it away.
    """
    windows, truncated = split_windows(text)

    if not windows:
        return {"windows": [], "tactics": [], "truncated": False,
                "window_count": 0}

    results, found = [], {}

    for index, window in enumerate(windows):
        try:
            prediction = predict_fn(window)
        except Exception:
            continue

        rows = build_tactics_fn(prediction, window)
        reported = [r for r in rows if not r["uncertain"]]

        results.append({
            "index": index,
            "text": window,
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "findings": [
                {
                    "display": r["display"],
                    "label": r["label"],
                    "confidence": r["confidence"],
                    "sources": r["sources"],
                    "explanation": r["explanation"],
                    "phrases": r["phrases"],
                }
                for r in reported
            ],
        })

        for row in reported:
            existing = found.get(row["label"])

            if existing is None or row["confidence"] > existing["confidence"]:
                found[row["label"]] = {
                    "label": row["label"],
                    "display": row["display"],
                    "confidence": row["confidence"],
                    "sources": row["sources"],
                    "explanation": row["explanation"],
                    "phrases": row["phrases"],
                    "windows": [index],
                    "uncertain": False,
                }
            else:
                existing["windows"].append(index)

    tactics_found = sorted(found.values(), key=lambda t: -t["confidence"])

    return {
        "windows": results,
        "tactics": tactics_found,
        "truncated": truncated,
        "window_count": len(windows),
    }
