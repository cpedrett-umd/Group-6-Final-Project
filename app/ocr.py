"""Image ad -> text, so a screenshot can reach the classifier on the spot.

The repo had no live OCR path: the image modality was collected offline and
merged into the CSV, leaving nothing that turns an uploaded screenshot into
model input at request time. This module is that missing step.

Backend is RapidOCR (ONNX): pip-only with no system installer, ~15MB of models,
and about a second per ad on CPU. `_BACKENDS` is an ordered list, so a teammate
can add Tesseract or EasyOCR later without touching the Flask route.

A note on space repair. The English recognition model sometimes returns a line
with its spaces collapsed -- "FINALHOURS:", "70%offbeforethesupplementban".
That wrecks both wordpiece tokenization and trigger-phrase matching, so merged
runs are split back apart with `wordninja`. The repair is deliberately timid:
splitting is only safe when a token is obviously merged, because the same
splitter would otherwise turn brand names like "MemoryMax" into "Memory Max".
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


_engine = None

_BACKENDS = [("rapidocr", _rapidocr)]


def available_backend() -> str | None:
    """Name of the first importable backend, or None if OCR can't run."""
    for name, _function in _BACKENDS:
        try:
            if name == "rapidocr":
                import rapidocr_onnxruntime  # noqa: F401
            return name
        except ImportError:
            continue

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
    show what OCR literally saw), a mean `confidence`, and the `line_count`.
    Callers should display `text` for confirmation before trusting the verdict --
    a bad scan should be visible, not silently classified.
    """
    backend = available_backend()

    if backend is None:
        raise OCRUnavailableError(
            "No OCR backend installed. Install one with:\n"
            "    pip install rapidocr-onnxruntime\n"
            "Or paste the ad's text instead."
        )

    function = dict(_BACKENDS)[backend]

    lines, scores = function(image_bytes)

    if not lines:
        return {
            "text": "",
            "raw_text": "",
            "lines": [],
            "confidence": 0.0,
            "line_count": 0,
            "backend": backend,
            "repaired": False,
        }

    raw_lines = [line.strip() for line in lines if line.strip()]
    repaired_lines = [repair_spacing(line) for line in raw_lines]

    raw_text = " ".join(raw_lines)
    text = " ".join(repaired_lines)

    confidence = sum(scores) / len(scores) if scores else 0.0

    return {
        "text": text,
        "raw_text": raw_text,
        # Per-line output so multi-frame captures (animated/video ads) can be
        # merged with line-level dedup instead of concatenating whole frames.
        "lines": repaired_lines,
        "confidence": round(confidence, 4),
        "line_count": len(lines),
        "backend": backend,
        "repaired": text != raw_text,
    }
