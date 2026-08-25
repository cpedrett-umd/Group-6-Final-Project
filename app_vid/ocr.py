"""Image ad -> text, so a screenshot can reach the classifier on the spot.

The repo had no live OCR path: the image modality was collected offline and
merged into the CSV, leaving nothing that turns an uploaded screenshot into
model input at request time. This module is that missing step.

`_BACKENDS` is an ordered list, tried in order, first usable one wins:

  * vlm       -- a vision-language model used purely as a transcriber. On a
                 six-ad evaluation set it recovered 89% of required strings
                 against 64% for RapidOCR. Needs OPENAI_API_KEY and a network
                 call, so it is not always available.
  * rapidocr  -- ONNX, pip-only with no system installer, ~15MB of models, about
                 a second per ad on CPU. Always available once installed, and
                 the fallback when the VLM call fails.

A note on space repair. The English recognition model sometimes returns a line
with its spaces collapsed -- "FINALHOURS:", "70%offbeforethesupplementban".
That wrecks both wordpiece tokenization and trigger-phrase matching, so merged
runs are split back apart with `wordninja`. The repair is deliberately timid:
splitting is only safe when a token is obviously merged, because the same
splitter would otherwise turn brand names like "MemoryMax" into "Memory Max".

Space repair is why the VLM helps as much as it does. Measured on real ad
screenshots, only 5-6 required strings were lost outright by OCR; 13-19 were
recovered but run together, which survives as text but cannot match the
word-boundary regexes in tactics.py. On the RYZE ad a profile avatar overlaps
the "TH" in "THIS WEEK ONLY" and OCR returns "ISWEEKONLY", so the urgency
trigger never fired and the ad was reported to the user as clean.
"""
from __future__ import annotations

import io
import re

# Runs shorter than this are never split -- too likely to be an ordinary word
# or a brand name.
_MIN_REPAIR_LENGTH = 8

# All-caps runs get a lower bar: tight letter-spacing in headline text is the
# usual cause of a merge, and short ad imperatives ("ACTNOW", "BUYNOW") are
# common enough to be worth recovering.
_MIN_CAPS_LENGTH = 6

# Any fragment shorter than this means the splitter guessed badly.
_MIN_PART_LENGTH = 2

# A 2-way split is the risky shape -- it is what a compound brand name looks
# like. Case is the usable signal: brand compounds carry an internal capital
# ("MemoryMax", "PayPal", "YouTube") or are capitalised ("Trustpilot"), whereas
# a run that OCR merged out of ordinary body text keeps that text's uniform
# case ("nowbefore", "thisseason", "ACTNOW").
#
# So 2-way splits are accepted only for runs that are entirely upper or
# entirely lower case, and rejected for mixed case. Both halves must also be
# substantial, which keeps "ACT NOW" while leaving "COSTCO" (-> COST/CO) alone.
#
# The cost is real but one-directional: "Yourhome" is structurally identical to
# "Trustpilot", so merges of a capitalised word stay merged. Preserving a brand
# the panel quotes back to the user matters more than recovering one space.
_MIN_WORD_PART_LENGTH = 3

# Splitting is applied per run of letters/digits so that punctuation survives:
# wordninja discards anything non-alphanumeric, which would silently turn
# "70%offbeforethesupplementban" into "70 off before the supplement ban" and
# drop the percent sign from text the panel quotes back to the user.
_RUN = re.compile(r"[A-Za-z0-9]+")

# Symbols that normally close a token, so a word butting straight up against
# one is evidence the space was lost rather than never present.
_TRAILING_SYMBOLS = "%)]}>.,:;!?\"'"


class OCRUnavailableError(RuntimeError):
    """Raised when no OCR backend is installed."""


class UnreadableImageError(ValueError):
    """Raised when the upload isn't a decodable image."""


def _rapidocr(image_bytes: bytes):
    """RapidOCR ONNX backend. Returns (lines, confidences)."""
    from rapidocr_onnxruntime import RapidOCR

    global _engine

    if _engine is None:
        _engine = RapidOCR()

    import numpy as np
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise UnreadableImageError(
            "That file isn't an image we can read. Try a PNG or JPG screenshot."
        ) from error

    result, _elapsed = _engine(np.array(image))

    if not result:
        return [], []

    # RapidOCR returns [box, text, score] top-to-bottom already.
    lines = [entry[1] for entry in result]
    scores = [float(entry[2]) for entry in result]

    return lines, scores


def _vlm(image_bytes: bytes):
    """Vision-language model backend. Returns (lines, confidences).

    The model transcribes only -- it does not classify, name tactics, or judge
    the ad. That stays with the tuned classifier; the prompt in vlm_ocr enforces
    the boundary.

    Raises VLMUnavailableError on a missing key, timeout, or network failure.
    `extract_text` catches that and falls through to RapidOCR, because this is a
    network call sitting in the request path and a demo must not depend on it.
    """
    import vlm_ocr

    result = vlm_ocr.extract_text(image_bytes)

    # The API returns no per-line score. An empty list makes extract_text report
    # `confidence: None` rather than inventing a number the model never gave.
    return result["lines"], []


_engine = None

# Ordered by preference. The VLM is more accurate but needs a key and a network
# round trip; RapidOCR always works offline and is the fallback.
_BACKENDS = [("vlm", _vlm), ("rapidocr", _rapidocr)]

_FALLBACK_BACKEND = "rapidocr"


def _backend_usable(name: str) -> bool:
    """Whether one backend can actually run right now."""
    if name == "vlm":
        try:
            import vlm_ocr
        except ImportError:
            return False
        return vlm_ocr.is_available()

    if name == "rapidocr":
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except ImportError:
            return False
        return True

    return False


def available_backend() -> str | None:
    """Name of the first usable backend, or None if OCR can't run at all."""
    for name, _function in _BACKENDS:
        if _backend_usable(name):
            return name

    return None


def _split_run(run: str) -> str:
    """Re-space one run of letters/digits, only when it is clearly merged."""
    try:
        import wordninja
    except ImportError:
        return run

    if not any(character.isalpha() for character in run):
        return run

    is_upper = run.isupper()
    minimum = _MIN_CAPS_LENGTH if is_upper else _MIN_REPAIR_LENGTH

    if len(run) < minimum:
        return run

    parts = wordninja.split(run)

    if len(parts) < 2:
        return run

    if any(len(part) < _MIN_PART_LENGTH for part in parts):
        return run

    if len(parts) == 2:
        # Mixed case is the brand-compound signature -- leave it alone.
        if not (is_upper or run.islower()):
            return run

        # Numbers carry their own boundary ("48HOURS"), so only word parts
        # need to be substantial.
        if any(
            len(part) < _MIN_WORD_PART_LENGTH
            for part in parts
            if not part.isdigit()
        ):
            return run

    return " ".join(parts)


def repair_spacing(text: str) -> str:
    """Split collapsed word runs in OCR output, leaving everything else intact.

    Operates on each run of letters/digits independently and rebuilds the string
    around them, so punctuation, symbols, and spacing are preserved exactly.
    """
    pieces = []
    cursor = 0

    for match in _RUN.finditer(text):
        separator = text[cursor : match.start()]
        run = match.group(0)
        split = _split_run(run)

        # If this run lost its spaces, the space after an adjacent trailing
        # symbol was probably lost with them: "70%offbefore..." should come back
        # as "70% off before...", not "70%off before...". Only symbols that
        # normally end a token qualify, so "(FINALHOURS)" stays "(FINAL HOURS)".
        if split != run and separator and separator[-1] in _TRAILING_SYMBOLS:
            separator += " "

        pieces.append(separator)
        pieces.append(split)
        cursor = match.end()

    pieces.append(text[cursor:])

    return "".join(pieces)


def extract_text(image_bytes: bytes) -> dict:
    """Run OCR over an image and return text ready for the classifier.

    Returns the joined `text`, the `raw_text` before space repair (so the UI can
    show what the backend literally saw), a mean `confidence`, and the
    `line_count`. Callers should display `text` for confirmation before trusting
    the verdict -- a bad scan should be visible, not silently classified.

    `confidence` is None when the backend reports no per-line score, which is
    the case for the VLM. The UI must treat that as "not reported" rather than
    printing 0%.
    """
    backend = available_backend()

    if backend is None:
        raise OCRUnavailableError(
            "No OCR backend installed. Install one with:\n"
            "    pip install rapidocr-onnxruntime\n"
            "Or paste the ad's text instead."
        )

    function = dict(_BACKENDS)[backend]

    try:
        lines, scores = function(image_bytes)
    except UnreadableImageError:
        # A corrupt upload will fail on every backend -- retrying wastes a
        # round trip and hides the real cause from the user.
        raise
    except Exception:
        # The VLM is a network call: a missing key, a timeout, or a rate limit
        # must degrade to the local backend rather than break the request.
        if backend == _FALLBACK_BACKEND or not _backend_usable(_FALLBACK_BACKEND):
            raise

        backend = _FALLBACK_BACKEND
        lines, scores = dict(_BACKENDS)[_FALLBACK_BACKEND](image_bytes)

    if not lines:
        return {
            "text": "",
            "raw_text": "",
            "lines": [],
            "confidence": None if not scores else 0.0,
            "line_count": 0,
            "backend": backend,
            "repaired": False,
        }

    raw_lines = [line.strip() for line in lines if line.strip()]
    repaired_lines = [repair_spacing(line) for line in raw_lines]

    raw_text = " ".join(raw_lines)
    text = " ".join(repaired_lines)

    # No scores means the backend does not report confidence, which is not the
    # same as reporting zero.
    confidence = round(sum(scores) / len(scores), 4) if scores else None

    return {
        "text": text,
        "raw_text": raw_text,
        # Per-line output so multi-frame captures (animated/video ads) can be
        # merged with line-level dedup instead of concatenating whole frames.
        "lines": repaired_lines,
        "confidence": confidence,
        "line_count": len(lines),
        "backend": backend,
        "repaired": text != raw_text,
    }