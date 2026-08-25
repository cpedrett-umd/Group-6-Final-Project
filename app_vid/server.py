"""Flask app serving the AdInsight demo front end and its analyse endpoint.

Run from the repository root (or anywhere -- paths are resolved from __file__):

    python app/server.py

Then open http://127.0.0.1:5000

Requires the tuned weights. If they are missing the page still loads and says
what to run, rather than failing at import time.
"""
from __future__ import annotations

import argparse
import traceback

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
import media
from pathlib import Path
import ocr
import predict
import reviews
import tactics

# Guard against a browser tab uploading something enormous.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

# OCR that recovers less than this is noise, not an ad. Live ad thumbnails
# routinely yield a stray digit or logo fragment ("1", "TM"); classifying that
# produces a confident-looking verdict about nothing. Below this, the image
# path reports "no text" instead.
MIN_OCR_CHARS = 8

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def build_summary(rows):
    """The amber banner at the top of the panel.

    The wireframe's line is "This ad uses 5 pressure tactics. Nothing requires a
    decision today." -- reassurance first, count second. A clean ad needs the
    opposite message, so both cases are handled here.

    Rows flagged `uncertain` are not counted: they are a forced pick from a
    label set with no neutral option, not a finding. See tactics.LOW_CONFIDENCE.
    """
    count = sum(1 for row in rows if not row["uncertain"])

    if count == 0:
        return {
            "tone": "calm",
            "headline": "Nothing pushy found.",
            "message": "This ad reads as straightforward. You can still take your time.",
            "count": 0,
        }

    noun = "pressure tactic" if count == 1 else "pressure tactics"

    return {
        "tone": "caution",
        "headline": "Take your time.",
        "message": f"This ad uses {count} {noun}. Nothing requires a decision today.",
        "count": count,
    }
def extract_claim(text, image_bytes=None):
    """Brand, promise, and the search a cautious buyer would type.

    Returns (brand, promise, query), any of which may be None. Never raises:
    the review layer degrades to its no-entity branch without this, and a
    failure here must not cost the user their tactic analysis.
    """
    import os

    if not os.environ.get("OPENAI_API_KEY") or not text.strip():
        return None, None, None
    prompt = (
        "You are looking at an advertisement someone has just seen. They want "
        "to find out what other people's real experience with this product has "
        "been.\n\nOutput exactly three lines:\n\n"
        "BRAND: the brand or product name as written in the ad, or NONE\n"
        "PROMISE: the outcome the ad says the product will deliver, or NONE\n"
        "QUERY: the search a cautious buyer would type to find out whether "
        "other people actually got that outcome\n\n"
        "Rules for QUERY:\n"
         "The PROMISE is the outcome the reader is being offered, not a "
        "description of the product. It may be stated in words, implied by an "
        "image, or carried by a number. Ingredients, materials, brand story, "
        "flavour, styling and technical specifications are never the promise "
        "-- they are how the ad supports it.\n\n"
        "Ask yourself what would change for the reader if this worked. That is "
        "the promise.\n\n"
        "QUERY must ask whether real people got that outcome. It should read "
        "like what someone would type after seeing the ad and wondering "
        "whether to believe it -- the brand, the outcome, and a word that "
        "leads to other people's experience. Never build the query from the "
        "product's ingredients or description.\n\n"
        "Report only what the ad states. Do not evaluate it, do not say "
        "whether the promise is true, and do not name any persuasion tactic.\n\n"
        "Advertisement text:\n" + text[:2000]
    )



    try:
        from openai import OpenAI

        response = OpenAI(timeout=15).chat.completions.create(
            model=os.environ.get("ADINSIGHT_VLM_MODEL", "gpt-4o-mini"),
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (response.choices[0].message.content or "")
    except Exception:
        return None, None, None

    found = {}
    for line in raw.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().upper(), value.strip()
        if key in {"BRAND", "PROMISE", "QUERY"} and value:
            found[key] = None if value.upper() == "NONE" else value

    return found.get("BRAND"), found.get("PROMISE"), found.get("QUERY")


@app.after_request
def allow_extension_origin(response):
    """Let the browser extension call this API.

    The extension's service worker already bypasses CORS through its
    host_permissions, so this is belt-and-braces: it keeps the API reachable
    from a page served on another port, from a file:// test harness, or from
    Firefox, where content-script CORS behaves differently. This binds to
    localhost for a demo, so a wildcard origin is not exposing anything.
    """
    if request.path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

    return response


@app.route("/api/analyze", methods=["OPTIONS"])
def analyze_preflight():
    return ("", 204)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/demo-page")
def demo_page():
    """A stand-in news article carrying every kind of ad the extension handles.

    The extension needs a real page to overlay. This gives the demo a fixed,
    offline target instead of hunting for a live ad mid-presentation — and a
    safe one: testing hover/capture on third-party sites means injecting into
    a signed-in browser profile, which this page exists to avoid.

    Fixtures: a marked-up text ad, an iframe ad slot (exercises the hover
    sensor + screenshot capture), and a "Sponsored"-labeled card with no
    ad-ish markup (exercises label detection).
    """
    return send_from_directory(app.static_folder, "demo-page.html")


@app.get("/fake-ad")
def fake_ad():
    """The creative inside the demo page's iframe ad slot."""
    return send_from_directory(app.static_folder, "fake-ad.html")


@app.get("/api/health")
def health():
    """Lets the page report missing pieces up front instead of on first click."""
    tools = media.tools_available()

    return jsonify(
        {
            "model_ready": predict.is_ready(),
            "ocr_backend": ocr.available_backend(),
            "media": tools,
            "media_ready": bool(tools.get("whisper")),
        }
    )


@app.post("/api/analyze")
def analyze():
    """Analyse an ad supplied either as text or as an uploaded image.

    Accepts JSON ``{"text": ...}`` or a multipart form with an ``image`` file.
    The image path runs OCR first and returns the extracted text alongside the
    verdict, so a bad scan is visible to the user rather than silently driving
    the prediction.
    """
    source = {"mode": "text"}
    text = ""

    try:
        if "image" in request.files:
            # One file for a still ad; several for an animated or video ad,
            # where the extension photographs the same slot a few times and
            # each frame may carry different text. Lines are merged with
            # order-preserving dedup, so a rotating creative contributes each
            # message once and a static one is unchanged by extra frames.
            uploads = request.files.getlist("image")

            merged_lines = []
            seen = set()
            raw_parts = []
            confidences = []
            readable_frames = 0

            for upload in uploads:
                image_bytes = upload.read()

                if not image_bytes:
                    return jsonify({"error": "The uploaded image was empty."}), 400

                extraction = ocr.extract_text(image_bytes)

                if extraction["lines"]:
                    readable_frames += 1
                    if extraction["confidence"] is not None:
                        confidences.append(extraction["confidence"])
                    raw_parts.append(extraction["raw_text"])

                for line in extraction["lines"]:
                    key = " ".join(line.lower().split())
                    if key and key not in seen:
                        seen.add(key)
                        merged_lines.append(line)

            text = " ".join(merged_lines)

            source = {
                "mode": "image",
                "filename": uploads[0].filename,
                "ocr": {
                    "text": text,
                    "raw_text": " ".join(raw_parts),
                    "confidence": round(
                        sum(confidences) / len(confidences), 4
                    ) if confidences else None,
                    "line_count": len(merged_lines),
                    "backend": ocr.available_backend(),
                    "repaired": text != " ".join(raw_parts),
                    "frames": len(uploads),
                    "readable_frames": readable_frames,
                },
            }

            if len(text.strip()) < MIN_OCR_CHARS:
                return (
                    jsonify(
                        {
                            "error": "No readable text could be found in that image. "
                            "Try a sharper screenshot, or paste the ad's text instead.",
                            "source": source,
                        }
                    ),
                    422,
                )
        else:
            payload = request.get_json(silent=True) or {}
            text = (payload.get("text") or "").strip()

            if not text:
                return jsonify({"error": "Paste some ad text first."}), 400

        prediction = predict.predict(text)
        rows = tactics.build_tactics(prediction, text)
        brand, promise, claim_query = extract_claim(text)

        return jsonify(
            {
                "text": text,
                "source": source,
                "prediction": prediction,
                "tactics": rows,
                "summary": build_summary(rows),
                "claim": {"brand": brand, "promise": promise},
                "reviews": reviews.fetch(
                    text,
                    brand=brand,
                    tactic=prediction["label"],
                    claim_query=claim_query,
                ),
            }
        )

    except predict.ModelNotTrainedError as error:
        return jsonify({"error": str(error), "needs_training": True}), 503

    except ocr.OCRUnavailableError as error:
        return jsonify({"error": str(error)}), 503

    except ocr.UnreadableImageError as error:
        return jsonify({"error": str(error)}), 400

    except HTTPException:
        # Werkzeug raises these while parsing the request -- an over-limit
        # upload trips RequestEntityTooLarge on the first `request.files`
        # access, inside this try. Re-raise so Flask's own handlers (the 413
        # below) produce the response instead of the generic 500 catch-all.
        raise

    except Exception:  # noqa: BLE001 - surface the traceback in a demo tool
        traceback.print_exc()
        return jsonify({"error": "Something went wrong analysing that ad."}), 500

@app.route("/api/analyze-media", methods=["OPTIONS"])
def analyze_media_preflight():
    return ("", 204)


@app.post("/api/analyze-media")
def analyze_media():
    """Analyse a video or audio ad, from a link or an uploaded recording.

    Accepts multipart with a `media` file, or JSON {"url": ...}.

    Two channels are read and both are kept. Speech carries the argument; text
    burned into the frames carries the assertions -- headline copy, prices,
    deadlines. Measured on a supplement ad the frames returned 71 words against
    593 spoken, but every frame word was deliberate ad copy. Reading one channel
    misses half the ad.

    The result is windowed rather than reduced to a single label. A 60-second ad
    commonly spends most of its length building credibility and pitches in the
    last few seconds, so one verdict over the whole transcript reports the
    credibility-building and never sees the pitch.
    """
    temporary_path = None

    try:
        upload = request.files.get("media")

        if upload is not None:
            if not upload.filename:
                return jsonify({"error": "No file was chosen."}), 400
            temporary_path = media.save_upload(upload)
            path, platform = temporary_path, None
            origin = {"kind": "upload", "filename": upload.filename}
        else:
            payload = request.get_json(silent=True) or {}
            url = (payload.get("url") or "").strip()

            if not url:
                return jsonify({"error": "Paste a link, or upload a recording."}), 400

            if not url.lower().startswith(("http://", "https://")):
                return jsonify({"error": "That doesn't look like a link."}), 400

            path = media.fetch_url(url)
            temporary_path = path
            platform, _ = media.identify(url)
            origin = {"kind": "url", "url": url, "platform": platform}

        # ── read both channels ─────────────────────────────────────────
        frame_text, per_frame, duration = "", [], 0.0

        if path.suffix.lower() not in {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".aac"}:
            frames, duration = media.sample_frames(path)
            if frames:
                frame_text, per_frame = media.read_frames(frames, ocr.extract_text)

        spoken_text, segments, speech_error = "", [], None

        try:
            result = media.transcribe(path)
            spoken_text = result["text"]
            segments = result["segments"]
        except media.MediaError as error:
            # A silent ad is still analysable from its overlays, so this is only
            # fatal when the frames gave nothing either.
            speech_error = str(error)

        text = " ".join(part for part in (frame_text, spoken_text) if part).strip()

        if len(text) < MIN_OCR_CHARS:
            return (
                jsonify(
                    {
                        "error": "No words could be read from that recording. "
                        + (speech_error or "It may have no speech and no on-screen text."),
                    }
                ),
                422,
            )

        # ── windowed analysis ──────────────────────────────────────────
        analysis = media.analyse_windows(
            text, predict.predict, tactics.build_tactics, tactics.LOW_CONFIDENCE
        )

        # The whole-ad verdict still drives the review layer's query strategy,
        # so it is computed alongside the per-window map rather than instead.
        prediction = predict.predict(text)
        rows = tactics.build_tactics(prediction, text)

        brand, promise, claim_query = extract_claim(text)

        source = {
            "mode": "media",
            **origin,
            "duration": round(duration, 1),
            "spoken_words": len(spoken_text.split()),
            "frame_words": len(frame_text.split()),
            "frames_read": len(per_frame),
            "segments": segments[:40],
            "per_frame": per_frame,
            "speech_error": speech_error,
            "ocr": {
                "text": text,
                "raw_text": text,
                "confidence": None,
                "line_count": len(per_frame),
                "backend": ocr.available_backend(),
                "repaired": False,
                "frames": len(per_frame),
                "readable_frames": len(per_frame),
            },
        }

        return jsonify(
            {
                "text": text,
                "source": source,
                "prediction": prediction,
                "tactics": rows,
                "summary": build_summary(rows),
                "timeline": analysis,
                "claim": {"brand": brand, "promise": promise},
                "reviews": reviews.fetch(
                    text,
                    brand=brand,
                    tactic=prediction["label"],
                    claim_query=claim_query,
                ),
            }
        )

    except media.MediaError as error:
        # Already worded for the user -- rate limits, private posts and missing
        # tools each need a different response from them.
        return jsonify({"error": str(error)}), 422

    except predict.ModelNotTrainedError as error:
        return jsonify({"error": str(error), "needs_training": True}), 503

    except HTTPException:
        raise

    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": "Something went wrong reading that ad."}), 500

    finally:
        if temporary_path is not None:
            try:
                Path(temporary_path).unlink(missing_ok=True)
            except Exception:
                pass
@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That image is larger than 8 MB."}), 413


def main():
    parser = argparse.ArgumentParser(description="Run the AdInsight demo server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--warm",
        action="store_true",
        help="load the model at startup instead of on the first request",
    )
    arguments = parser.parse_args()

    if not predict.is_ready():
        print(
            "\n  Warning: no trained model found.\n"
            "  Build it first:  cd modeling && python train_best.py\n"
            "  The page will load but analysis will return an error.\n"
        )
    elif arguments.warm:
        print("Loading model...")
        predict.warm_up()
        print("Model ready.")

    if ocr.available_backend() is None:
        print("  Warning: no OCR backend — image uploads will be rejected.\n")

    app.run(host=arguments.host, port=arguments.port, debug=False)


if __name__ == "__main__":
    main()
