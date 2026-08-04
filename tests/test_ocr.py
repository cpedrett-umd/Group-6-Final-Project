"""OCR: the space-repair heuristic, and reading text off real images.

The repair tests matter more than they look. RapidOCR's English model sometimes
returns a line with its spaces collapsed, and the fix has to split those without
also splitting legitimate compound words -- the failure mode is a panel that
quotes "Memory Max Pro" back at a user looking at "MemoryMax Pro".
"""
from __future__ import annotations

import pytest

import ocr

pytestmark = pytest.mark.filterwarnings("ignore")


# ── Space repair: things that must be split ─────────────────────


@pytest.mark.parametrize(
    "merged,expected",
    [
        ("70%offbeforethesupplementban", "70% off before the supplement ban"),
        ("Doctor-recommendedMemoryMaxProreverses", "Doctor-recommended Memory Max Pro reverses"),
        ("FINALHOURS", "FINAL HOURS"),
        ("LIMITEDTIMEOFFER", "LIMITED TIME OFFER"),
    ],
)
def test_obvious_merges_are_split(merged, expected):
    assert ocr.repair_spacing(merged) == expected


def test_all_caps_two_word_merge_is_split():
    """Tight letter-spacing in all-caps headlines is the common OCR failure."""
    assert ocr.repair_spacing("ACTNOW") == "ACT NOW"


# ── Space repair: things that must NOT be split ─────────────────


@pytest.mark.parametrize(
    "token",
    [
        "MemoryMax",     # brand name, 2-way split -> must survive
        "NeuroVital",
        "Trustpilot",
        "PayPal",
        "YouTube",
    ],
)
def test_brand_names_survive(token):
    """A 2-way split on a mixed-case token is far more likely a brand."""
    assert ocr.repair_spacing(token) == token


@pytest.mark.parametrize(
    "word",
    [
        "recommended",
        "supplement",
        "guaranteed",
        "subscription",
        "advertisement",
        "clinically",
        "immediately",
    ],
)
def test_ordinary_long_words_survive(word):
    assert ocr.repair_spacing(word) == word


@pytest.mark.parametrize("token", ["Act", "now", "7", "70%", "$19.99", "a", ""])
def test_short_and_numeric_tokens_are_untouched(token):
    assert ocr.repair_spacing(token) == token


def test_already_spaced_text_is_unchanged():
    text = "Only 7 bottles left before the supplement ban"
    assert ocr.repair_spacing(text) == text


def test_punctuation_is_preserved_around_a_split():
    assert ocr.repair_spacing("(FINALHOURS)") == "(FINAL HOURS)"
    assert ocr.repair_spacing("FINALHOURS:") == "FINAL HOURS:"


def test_repair_is_idempotent():
    once = ocr.repair_spacing("70%offbeforethesupplementban")
    assert ocr.repair_spacing(once) == once


def test_mixed_line_repairs_only_the_broken_token():
    line = "Doctor-recommended MemoryMax Pro FINALHOURS today"
    result = ocr.repair_spacing(line)

    assert "MemoryMax" in result          # untouched
    assert "FINAL HOURS" in result        # repaired


# ── Backend discovery ───────────────────────────────────────────


@pytest.mark.ocr
def test_backend_is_discovered():
    assert ocr.available_backend() == "rapidocr"


def test_missing_backend_raises_a_useful_error(monkeypatch):
    """With no backend the demo must say what to install, not crash."""
    monkeypatch.setattr(ocr, "available_backend", lambda: None)

    with pytest.raises(ocr.OCRUnavailableError) as error:
        ocr.extract_text(b"whatever")

    assert "pip install" in str(error.value)


# ── extract_text ────────────────────────────────────────────────


@pytest.mark.ocr
@pytest.mark.slow
def test_reads_text_off_an_ad_image(ad_image_bytes):
    result = ocr.extract_text(ad_image_bytes)

    lowered = result["text"].lower()
    assert "limited" in lowered
    assert "only 5 kits" in lowered

    assert result["line_count"] >= 3
    assert result["confidence"] > 0.5
    assert result["backend"] == "rapidocr"


@pytest.mark.ocr
@pytest.mark.slow
def test_result_has_the_keys_the_front_end_reads(ad_image_bytes):
    result = ocr.extract_text(ad_image_bytes)

    assert set(result) >= {
        "text",
        "raw_text",
        "confidence",
        "line_count",
        "backend",
        "repaired",
    }
    assert isinstance(result["repaired"], bool)


@pytest.mark.ocr
@pytest.mark.slow
def test_repaired_flag_reflects_whether_text_changed(ad_image_bytes):
    result = ocr.extract_text(ad_image_bytes)
    assert result["repaired"] == (result["text"] != result["raw_text"])


@pytest.mark.ocr
@pytest.mark.slow
def test_blank_image_yields_no_text(blank_image_bytes):
    """Must return empty rather than raise -- the route turns this into a 422."""
    result = ocr.extract_text(blank_image_bytes)

    assert result["text"] == ""
    assert result["line_count"] == 0


@pytest.mark.ocr
def test_non_image_bytes_raise_unreadable(not_an_image_bytes):
    with pytest.raises(ocr.UnreadableImageError):
        ocr.extract_text(not_an_image_bytes)


@pytest.mark.ocr
def test_truncated_image_raises_unreadable(ad_image_bytes):
    with pytest.raises(ocr.UnreadableImageError):
        ocr.extract_text(ad_image_bytes[:80])
