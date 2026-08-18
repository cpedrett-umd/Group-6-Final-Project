"""Vision-language model as a text extractor.

Measured against six real ad screenshots, this recovers 89% of required strings
against 64% for the RapidOCR path. The gap is almost entirely spacing damage:
OCR returns `TRYRYZE` and `ISWEEKONLY`, which survive as text but cannot match
the word-boundary regexes in tactics.py. On the RYZE ad an avatar overlaps the
"TH" in "THIS WEEK ONLY" and OCR loses the phrase outright, so the ad was
reported to the user as clean.

Scope: this transcribes. It does not classify, name tactics, or judge the ad --
that stays with the fine-tuned model. The prompt enforces it.

Needs OPENAI_API_KEY in the environment. Callers should fall back to the local
OCR backend when this raises, since it is a network call in the request path.
"""
from __future__ import annotations

import base64
import os

MODEL = os.environ.get("ADINSIGHT_VLM_MODEL", "gpt-4o-mini")
TIMEOUT_SECONDS = 20

TRANSCRIBE_PROMPT = """Transcribe every piece of text visible in this image, in reading order.

Rules:
- Output only the transcribed text. No commentary, no formatting, no labels.
- Preserve the original wording, capitalisation and punctuation.
- Include text that is partly covered or low contrast if you can read it.
- Separate distinct blocks of text with a newline.
- Do not describe images, do not summarise, do not interpret."""


class VLMUnavailableError(RuntimeError):
    """No API key, or the call failed."""


def is_available() -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def _media_type(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


def extract_text(image_bytes: bytes) -> dict:
    """Return the same shape as ocr.extract_text so callers are unchanged."""
    if not is_available():
        raise VLMUnavailableError("OPENAI_API_KEY not set, or openai not installed.")

    from openai import OpenAI

    encoded = base64.b64encode(image_bytes).decode()
    url = f"data:{_media_type(image_bytes)};base64,{encoded}"

    try:
        response = OpenAI(timeout=TIMEOUT_SECONDS).chat.completions.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                ],
            }],
        )
    except Exception as error:
        raise VLMUnavailableError(f"VLM call failed: {error}") from error

    raw = (response.choices[0].message.content or "").strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    return {
        "lines": lines,
        "raw_text": raw,
        "text": " ".join(lines),
        # The VLM reports no per-line confidence. 1.0 would overstate it; the
        # field exists so the response shape matches the OCR backend.
        "confidence": None,
        "backend": f"vlm:{MODEL}",
    }