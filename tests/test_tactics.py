"""Trigger-phrase lexicon and panel-row construction.

Pure logic -- no model, no network. These are the tests that should still pass
on a fresh clone before anyone downloads weights.
"""
from __future__ import annotations

import pytest

import tactics

# The dataset's seven classes, from ads_dataset_labeled.csv.
DATASET_LABELS = [
    "Authority Manipulation",
    "Exaggerated Claims",
    "FOMO",
    "Fear Appeals",
    "Scarcity",
    "Social Proof",
    "Urgency",
]


def distribution_for(top_label, top_confidence=0.9):
    """A plausible softmax distribution with `top_label` winning."""
    rest = (1.0 - top_confidence) / (len(DATASET_LABELS) - 1)

    entries = [
        {
            "label": label,
            "confidence": top_confidence if label == top_label else rest,
        }
        for label in DATASET_LABELS
    ]

    entries.sort(key=lambda entry: -entry["confidence"])
    return entries


def prediction_for(label, confidence=0.9):
    return {
        "label": label,
        "confidence": confidence,
        "distribution": distribution_for(label, confidence),
        "truncated": False,
    }


# ── Copy tables cover every class ───────────────────────────────


@pytest.mark.parametrize("label", DATASET_LABELS)
def test_every_dataset_label_has_copy(label):
    """A class with no copy would render as a blank row in the panel."""
    assert label in tactics.DISPLAY_NAMES
    assert label in tactics.PHRASE_TEMPLATES
    assert label in tactics.GENERIC_EXPLANATIONS
    assert label in tactics.TRIGGER_PATTERNS


def test_no_extra_labels_in_copy_tables():
    """Guards against a typo'd key that would silently never be used."""
    assert set(tactics.DISPLAY_NAMES) == set(DATASET_LABELS)
    assert set(tactics.PHRASE_TEMPLATES) == set(DATASET_LABELS)
    assert set(tactics.GENERIC_EXPLANATIONS) == set(DATASET_LABELS)
    assert set(tactics.TRIGGER_PATTERNS) == set(DATASET_LABELS)


def test_phrase_templates_interpolate_the_phrase():
    for label, template in tactics.PHRASE_TEMPLATES.items():
        assert "{phrase}" in template, f"{label} template drops the quoted phrase"


# ── find_phrases ────────────────────────────────────────────────


def test_wireframe_ad_finds_the_five_tactics(wireframe_ad):
    """The reference case: the wireframe shows exactly these five."""
    found = tactics.find_phrases(wireframe_ad)

    assert set(found) == {
        "Urgency",
        "Scarcity",
        "Authority Manipulation",
        "Fear Appeals",
        "Exaggerated Claims",
    }


def test_neutral_ad_finds_nothing(neutral_ad):
    assert tactics.find_phrases(neutral_ad) == {}


def test_empty_text_finds_nothing():
    assert tactics.find_phrases("") == {}


def test_match_preserves_original_casing(wireframe_ad):
    urgency = tactics.find_phrases(wireframe_ad)["Urgency"]
    assert any(span["text"] == "FINAL HOURS" for span in urgency)


def test_longest_overlapping_match_wins(wireframe_ad):
    """"Only 7 bottles left" must not be reported as the shorter "Only 7 bottles"."""
    scarcity = tactics.find_phrases(wireframe_ad)["Scarcity"]

    assert len(scarcity) == 1
    assert scarcity[0]["text"] == "Only 7 bottles left"


def test_spans_are_sorted_by_position():
    text = "Guaranteed results. Limited time only. Miracle cure overnight."
    for spans in tactics.find_phrases(text).values():
        starts = [span["start"] for span in spans]
        assert starts == sorted(starts)


def test_spans_index_into_the_original_text(wireframe_ad):
    for spans in tactics.find_phrases(wireframe_ad).values():
        for span in spans:
            assert wireframe_ad[span["start"] : span["end"]] == span["text"]


@pytest.mark.parametrize(
    "text",
    [
        "Our banner is blue.",            # "ban" inside "banner"
        "An uncertified product.",        # "certified" inside "uncertified"
        "The urgency of abandonment.",    # "ban" inside "abandonment"
    ],
)
def test_word_boundaries_prevent_substring_matches(text):
    """Without \\b guards these would each fire a false tactic."""
    found = tactics.find_phrases(text)
    assert found == {}, f"false positive on {text!r}: {found}"


def test_matching_is_case_insensitive():
    lower = tactics.find_phrases("act now, only 3 left!")
    upper = tactics.find_phrases("ACT NOW, ONLY 3 LEFT!")
    assert set(lower) == set(upper) == {"Urgency", "Scarcity"}


# ── explain ─────────────────────────────────────────────────────


def test_explain_quotes_the_matched_phrase():
    spans = [{"text": "Act now", "start": 0, "end": 7}]
    assert '"Act now"' in tactics.explain("Urgency", spans)


def test_explain_falls_back_when_no_phrase_matched():
    result = tactics.explain("Urgency", [])
    assert result == tactics.GENERIC_EXPLANATIONS["Urgency"]
    assert '"' not in result


def test_explain_uses_the_first_phrase():
    spans = [
        {"text": "Act now", "start": 0, "end": 7},
        {"text": "Hurry", "start": 20, "end": 25},
    ]
    assert "Act now" in tactics.explain("Urgency", spans)


# ── build_tactics ───────────────────────────────────────────────


def test_model_prediction_always_gets_a_row(neutral_ad):
    rows = tactics.build_tactics(prediction_for("Urgency"), neutral_ad)
    assert [row["label"] for row in rows] == ["Urgency"]
    assert rows[0]["sources"] == ["model"]


def test_model_row_leads_the_list(wireframe_ad):
    rows = tactics.build_tactics(prediction_for("Authority Manipulation"), wireframe_ad)
    assert "model" in rows[0]["sources"]


def test_label_appears_once_when_both_signals_agree(wireframe_ad):
    rows = tactics.build_tactics(prediction_for("Urgency"), wireframe_ad)

    labels = [row["label"] for row in rows]
    assert len(labels) == len(set(labels))

    urgency = next(row for row in rows if row["label"] == "Urgency")
    assert urgency["sources"] == ["model", "phrase"]


def test_wireframe_ad_produces_five_rows(wireframe_ad):
    """Model pick is one of the five phrase hits, so the panel shows five."""
    rows = tactics.build_tactics(prediction_for("Authority Manipulation"), wireframe_ad)
    assert len(rows) == 5
    assert not any(row["uncertain"] for row in rows)


def test_row_carries_confidence_from_the_distribution(wireframe_ad):
    rows = tactics.build_tactics(prediction_for("Urgency", 0.77), wireframe_ad)
    urgency = next(row for row in rows if row["label"] == "Urgency")
    assert urgency["confidence"] == pytest.approx(0.77)


# ── The "no neutral class" guard ────────────────────────────────


def test_weak_model_only_row_is_flagged_uncertain(neutral_ad):
    """The dataset has no Neutral class, so a clean ad still gets a label.

    Reporting that as a finding is a false alarm; it must be flagged instead.
    """
    rows = tactics.build_tactics(prediction_for("Urgency", 0.45), neutral_ad)
    assert rows[0]["uncertain"] is True


def test_confident_model_only_row_is_not_uncertain(neutral_ad):
    rows = tactics.build_tactics(prediction_for("Urgency", 0.95), neutral_ad)
    assert rows[0]["uncertain"] is False


def test_phrase_evidence_defeats_low_confidence():
    """A literal trigger phrase is evidence regardless of the model's score."""
    text = "Act now, this offer ends tonight."
    rows = tactics.build_tactics(prediction_for("Urgency", 0.20), text)

    urgency = next(row for row in rows if row["label"] == "Urgency")
    assert urgency["uncertain"] is False


def test_phrase_only_rows_are_never_uncertain(wireframe_ad):
    rows = tactics.build_tactics(prediction_for("Authority Manipulation"), wireframe_ad)

    for row in rows:
        if row["sources"] == ["phrase"]:
            assert row["uncertain"] is False


@pytest.mark.parametrize(
    "confidence,expected",
    [
        (tactics.LOW_CONFIDENCE - 0.01, True),
        (tactics.LOW_CONFIDENCE, False),
        (tactics.LOW_CONFIDENCE + 0.01, False),
    ],
)
def test_uncertain_boundary_is_inclusive_at_the_threshold(
    neutral_ad, confidence, expected
):
    rows = tactics.build_tactics(prediction_for("Urgency", confidence), neutral_ad)
    assert rows[0]["uncertain"] is expected


# ── Row shape ───────────────────────────────────────────────────


def test_rows_have_the_keys_the_front_end_reads(wireframe_ad):
    rows = tactics.build_tactics(prediction_for("Urgency"), wireframe_ad)

    for row in rows:
        assert set(row) >= {
            "label",
            "display",
            "confidence",
            "sources",
            "phrases",
            "explanation",
            "uncertain",
        }
        assert row["display"] == tactics.display_name(row["label"])
        assert row["sources"], "every row needs at least one source"
        assert isinstance(row["explanation"], str) and row["explanation"]
