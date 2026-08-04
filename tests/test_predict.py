"""The tuned classifier's inference wrapper.

Every test here is marked `model` and skips without the weights, so a fresh
clone still runs green on the logic suites.
"""
from __future__ import annotations

import pytest

import predict

pytestmark = [pytest.mark.model, pytest.mark.slow]

EXPECTED_LABELS = {
    "Authority Manipulation",
    "Exaggerated Claims",
    "FOMO",
    "Fear Appeals",
    "Scarcity",
    "Social Proof",
    "Urgency",
}


def test_is_ready_when_weights_exist():
    assert predict.is_ready() is True


def test_returns_the_documented_shape(wireframe_ad):
    result = predict.predict(wireframe_ad)

    assert set(result) == {"label", "confidence", "distribution", "truncated"}
    assert isinstance(result["label"], str)
    assert isinstance(result["truncated"], bool)


def test_distribution_covers_all_seven_classes(wireframe_ad):
    result = predict.predict(wireframe_ad)

    labels = {entry["label"] for entry in result["distribution"]}
    assert labels == EXPECTED_LABELS


def test_labels_come_from_the_checkpoint_not_a_hardcoded_list():
    """Guards against the UI drifting from a re-trained model's class order."""
    state = predict._load()
    assert set(state["id_to_label"].values()) == EXPECTED_LABELS


def test_distribution_is_a_probability_distribution(wireframe_ad):
    result = predict.predict(wireframe_ad)

    total = sum(entry["confidence"] for entry in result["distribution"])
    assert total == pytest.approx(1.0, abs=1e-3)

    for entry in result["distribution"]:
        assert 0.0 <= entry["confidence"] <= 1.0


def test_distribution_is_sorted_high_to_low(wireframe_ad):
    confidences = [
        entry["confidence"] for entry in predict.predict(wireframe_ad)["distribution"]
    ]
    assert confidences == sorted(confidences, reverse=True)


def test_top_label_matches_the_distribution_head(wireframe_ad):
    result = predict.predict(wireframe_ad)

    assert result["label"] == result["distribution"][0]["label"]
    assert result["confidence"] == result["distribution"][0]["confidence"]


def test_prediction_is_deterministic(wireframe_ad):
    """Two identical demos on stage must not disagree."""
    first = predict.predict(wireframe_ad)
    second = predict.predict(wireframe_ad)
    assert first == second


def test_a_clear_fear_ad_is_classified_as_fear(fear_ad):
    """Sanity check that the loaded weights are the trained ones.

    Held-out F1 for Fear Appeals is 0.98, so this is a stable assertion -- if it
    fails, the checkpoint is wrong, not the model merely uncertain.
    """
    assert predict.predict(fear_ad)["label"] == "Fear Appeals"


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_text_is_rejected(text):
    with pytest.raises(ValueError):
        predict.predict(text)


def test_long_text_sets_the_truncated_flag():
    """Anything past 128 subwords is invisible to the model; the UI can say so."""
    long_ad = "act now before this limited time offer expires tonight " * 40
    assert predict.predict(long_ad)["truncated"] is True


def test_short_text_is_not_flagged_truncated(wireframe_ad):
    assert predict.predict(wireframe_ad)["truncated"] is False


def test_model_runs_in_float32_even_if_weights_are_float16():
    """The released weights are float16; CPU inference needs float32."""
    import torch

    state = predict._load()
    dtype = next(state["model"].parameters()).dtype
    assert dtype == torch.float32


def test_unicode_and_punctuation_do_not_crash():
    for text in [
        "Act now — only 7 left! 70% off 😱",
        "¡Compre ahora! Limited time.",
        "<script>alert(1)</script> Guaranteed results",
    ]:
        result = predict.predict(text)
        assert result["label"] in EXPECTED_LABELS
