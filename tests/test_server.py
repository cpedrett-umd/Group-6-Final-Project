"""The Flask API and the routes the two front ends depend on."""
from __future__ import annotations

import io
import json

import pytest

import server
import tactics


# ── Static routes ───────────────────────────────────────────────


def test_index_serves_the_app(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"AdInsight" in response.data


def test_demo_page_is_served_for_the_extension(client):
    """The extension's fixed demo target -- a broken route breaks the demo."""
    response = client.get("/demo-page")

    assert response.status_code == 200
    assert b"Sponsored" in response.data
    assert b"NeuroVital" in response.data


def test_static_assets_are_served(client):
    for path in ["/styles.css", "/app.js"]:
        assert client.get(path).status_code == 200


# ── Health ──────────────────────────────────────────────────────


def test_health_reports_both_dependencies(client):
    payload = client.get("/api/health").get_json()

    assert set(payload) == {"model_ready", "ocr_backend"}
    assert isinstance(payload["model_ready"], bool)


# ── CORS (the extension calls this API cross-origin) ────────────


def test_api_routes_allow_cross_origin(client):
    headers = client.get("/api/health").headers
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_non_api_routes_do_not_set_cors(client):
    """No reason to widen the page itself."""
    assert "Access-Control-Allow-Origin" not in client.get("/").headers


def test_preflight_is_answered(client):
    response = client.options("/api/analyze")

    assert response.status_code in (200, 204)
    assert response.headers.get("Access-Control-Allow-Origin") == "*"


# ── Text analysis ───────────────────────────────────────────────


@pytest.mark.model
@pytest.mark.slow
def test_analyze_text_returns_the_documented_shape(client, wireframe_ad):
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    assert set(payload) >= {
        "text",
        "source",
        "prediction",
        "tactics",
        "summary",
        "reviews",
    }
    assert payload["source"]["mode"] == "text"
    assert payload["text"] == wireframe_ad


@pytest.mark.model
@pytest.mark.slow
def test_wireframe_ad_reports_five_tactics(client, wireframe_ad):
    """The reference case from the deck, end to end through the API."""
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    displays = {row["display"] for row in payload["tactics"]}
    assert displays == {"Urgency", "Scarcity", "Authority", "Fear", "Big claim"}

    assert payload["summary"]["count"] == 5
    assert payload["summary"]["tone"] == "caution"
    assert "5 pressure tactics" in payload["summary"]["message"]


@pytest.mark.model
@pytest.mark.slow
def test_neutral_ad_gets_the_calm_summary(client, neutral_ad):
    """No neutral class exists, so the guard has to keep this from false-alarming."""
    payload = client.post("/api/analyze", json={"text": neutral_ad}).get_json()

    assert payload["summary"]["tone"] == "calm"
    assert payload["summary"]["count"] == 0

    # The model's forced pick is still returned, just flagged, so the UI can
    # show it under "read the full explanation" rather than as a finding.
    assert all(row["uncertain"] for row in payload["tactics"])
    assert payload["prediction"]["label"]


@pytest.mark.model
@pytest.mark.slow
def test_summary_count_ignores_uncertain_rows(client, monkeypatch):
    rows = [
        {"label": "Urgency", "uncertain": False},
        {"label": "FOMO", "uncertain": True},
    ]
    assert server.build_summary(rows)["count"] == 1


def test_summary_singular_and_plural():
    one = server.build_summary([{"label": "Urgency", "uncertain": False}])
    assert "1 pressure tactic." in one["message"]

    two = server.build_summary(
        [
            {"label": "Urgency", "uncertain": False},
            {"label": "FOMO", "uncertain": False},
        ]
    )
    assert "2 pressure tactics" in two["message"]


def test_summary_with_no_rows_is_calm():
    summary = server.build_summary([])
    assert summary["tone"] == "calm"
    assert summary["count"] == 0


# ── Text input validation ───────────────────────────────────────


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   "}, {}])
def test_empty_text_is_rejected(client, body):
    response = client.post("/api/analyze", json=body)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_missing_body_is_rejected(client):
    response = client.post("/api/analyze")
    assert response.status_code == 400


def test_malformed_json_is_rejected_not_crashed(client):
    response = client.post(
        "/api/analyze",
        data="{not json",
        content_type="application/json",
    )
    assert response.status_code == 400


# ── Image analysis ──────────────────────────────────────────────


@pytest.mark.model
@pytest.mark.ocr
@pytest.mark.slow
@pytest.mark.renders
def test_analyze_image_runs_ocr_then_the_model(client, ad_image_bytes):
    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(ad_image_bytes), "ad.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["source"]["mode"] == "image"
    assert payload["source"]["filename"] == "ad.png"

    ocr_block = payload["source"]["ocr"]
    assert ocr_block["confidence"] > 0.5
    assert ocr_block["line_count"] >= 1

    # The text the model saw is returned so the UI can show a bad scan.
    assert payload["text"]
    assert "only 5 kits" in payload["text"].lower()


@pytest.mark.ocr
def test_unreadable_image_is_a_400_with_a_plain_message(client, not_an_image_bytes):
    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(not_an_image_bytes), "notanimage.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "image" in response.get_json()["error"].lower()


@pytest.mark.ocr
@pytest.mark.slow
def test_image_with_no_text_is_a_422(client, blank_image_bytes):
    """Distinct from a broken file: the image is fine, it just has no words."""
    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(blank_image_bytes), "blank.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert "No readable text" in response.get_json()["error"]


def _fake_extraction(lines, confidence=0.9):
    text = " ".join(lines)
    return {
        "text": text,
        "raw_text": text,
        "lines": list(lines),
        "confidence": confidence,
        "line_count": len(lines),
        "backend": "fake",
        "repaired": False,
    }


@pytest.mark.model
@pytest.mark.slow
def test_multi_frame_upload_merges_unique_lines(client, monkeypatch):
    """Animated/video ads: the extension sends several frames of one slot.

    A rotating creative shows different text per frame; a static one repeats
    itself. Lines merge order-preserving and case-insensitively deduped, so
    both end up with each message exactly once.
    """
    frames = iter(
        [
            _fake_extraction(["FINAL HOURS: 70% OFF", "Act now!"]),
            _fake_extraction(["Act now!", "Only 7 bottles left"]),  # overlap
            _fake_extraction(["FINAL HOURS: 70% OFF"]),             # repeat
        ]
    )
    monkeypatch.setattr(server.ocr, "extract_text", lambda _b: next(frames))

    response = client.post(
        "/api/analyze",
        data={
            "image": [
                (io.BytesIO(b"f1"), "f1.png"),
                (io.BytesIO(b"f2"), "f2.png"),
                (io.BytesIO(b"f3"), "f3.png"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["text"] == "FINAL HOURS: 70% OFF Act now! Only 7 bottles left"

    ocr_block = payload["source"]["ocr"]
    assert ocr_block["frames"] == 3
    assert ocr_block["readable_frames"] == 3
    assert ocr_block["line_count"] == 3


@pytest.mark.model
@pytest.mark.slow
def test_blank_frames_do_not_sink_a_burst(client, monkeypatch):
    """A transition frame with no text must not break the whole capture."""
    frames = iter(
        [
            _fake_extraction([]),  # caught mid-transition
            _fake_extraction(["Guaranteed results, limited time only"]),
        ]
    )
    monkeypatch.setattr(server.ocr, "extract_text", lambda _b: next(frames))

    response = client.post(
        "/api/analyze",
        data={
            "image": [
                (io.BytesIO(b"f1"), "f1.png"),
                (io.BytesIO(b"f2"), "f2.png"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source"]["ocr"]["readable_frames"] == 1
    assert "Guaranteed results" in payload["text"]


def test_all_blank_frames_are_a_422(client, monkeypatch):
    monkeypatch.setattr(
        server.ocr, "extract_text", lambda _b: _fake_extraction([])
    )

    response = client.post(
        "/api/analyze",
        data={
            "image": [
                (io.BytesIO(b"f1"), "f1.png"),
                (io.BytesIO(b"f2"), "f2.png"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


def test_near_empty_ocr_is_a_422_not_a_verdict(client, monkeypatch):
    """A stray digit off an ad thumbnail must not become a confident verdict.

    Found on live Taboola creatives: OCR read a lone "1" and the model then
    classified one character. Anything under MIN_OCR_CHARS reports no text.
    """
    monkeypatch.setattr(
        server.ocr,
        "extract_text",
        lambda _bytes: _fake_extraction(["1"], confidence=0.51),
    )

    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(b"\x89PNG fake"), "thumb.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert "No readable text" in response.get_json()["error"]


def test_empty_upload_is_rejected(client):
    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(b""), "empty.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_oversized_upload_is_rejected(client):
    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * (server.MAX_UPLOAD_BYTES + 1024)

    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(too_big), "huge.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert "8 MB" in response.get_json()["error"]


# ── Review stub ─────────────────────────────────────────────────


@pytest.mark.model
@pytest.mark.slow
def test_reviews_are_always_flagged_as_mock(client, wireframe_ad):
    """The layer isn't built. If this ever returns mock=False silently, the UI
    drops its "sample data" badge and starts presenting invented quotes as real."""
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    assert payload["reviews"]["mock"] is True
    assert payload["reviews"]["notice"]
    assert len(payload["reviews"]["items"]) >= 1

    for item in payload["reviews"]["items"]:
        assert set(item) >= {"source", "quote"}


# ── Failure modes ───────────────────────────────────────────────


def test_missing_model_returns_503_with_instructions(client, monkeypatch):
    def boom(_text):
        raise server.predict.ModelNotTrainedError("No trained model at ...\ntrain_best.py")

    monkeypatch.setattr(server.predict, "predict", boom)

    response = client.post("/api/analyze", json={"text": "act now"})

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["needs_training"] is True
    assert "train_best.py" in payload["error"]


def test_missing_ocr_returns_503(client, monkeypatch, ad_image_bytes):
    def boom(_bytes):
        raise server.ocr.OCRUnavailableError("No OCR backend installed. pip install ...")

    monkeypatch.setattr(server.ocr, "extract_text", boom)

    response = client.post(
        "/api/analyze",
        data={"image": (io.BytesIO(ad_image_bytes), "ad.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503


def test_unexpected_error_is_a_generic_500(client, monkeypatch):
    """Internal tracebacks go to the console, never to the user's panel."""
    def boom(_text):
        raise RuntimeError("some internal detail")

    monkeypatch.setattr(server.predict, "predict", boom)

    response = client.post("/api/analyze", json={"text": "act now"})

    assert response.status_code == 500
    assert "some internal detail" not in json.dumps(response.get_json())


# ── Contract between the API and both front ends ────────────────


@pytest.mark.model
@pytest.mark.slow
def test_tactic_rows_carry_every_field_the_front_ends_render(client, wireframe_ad):
    """app/static/app.js and extension/content.js both read these keys."""
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    for row in payload["tactics"]:
        assert set(row) >= {
            "display",
            "confidence",
            "sources",
            "phrases",
            "explanation",
            "uncertain",
        }
        assert set(row["sources"]) <= {"model", "phrase"}


@pytest.mark.model
@pytest.mark.slow
def test_exactly_one_row_is_the_model_pick(client, wireframe_ad):
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    model_rows = [row for row in payload["tactics"] if "model" in row["sources"]]
    assert len(model_rows) == 1
    assert model_rows[0]["label"] == payload["prediction"]["label"]


@pytest.mark.model
@pytest.mark.slow
def test_display_names_match_the_lexicon_table(client, wireframe_ad):
    payload = client.post("/api/analyze", json={"text": wireframe_ad}).get_json()

    for row in payload["tactics"]:
        assert row["display"] == tactics.DISPLAY_NAMES[row["label"]]
