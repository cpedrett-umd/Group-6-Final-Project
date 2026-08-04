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

import ocr
import predict
import reviews
import tactics

# Guard against a browser tab uploading something enormous.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

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
    """A stand-in news article carrying a sponsored ad.

    The extension needs a real page to overlay. This gives the demo a fixed,
    offline target instead of hunting for a live ad mid-presentation.
    """
    return send_from_directory(app.static_folder, "demo-page.html")


@app.get("/api/health")
def health():
    """Lets the page report missing pieces up front instead of on first click."""
    return jsonify(
        {
            "model_ready": predict.is_ready(),
            "ocr_backend": ocr.available_backend(),
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
            upload = request.files["image"]
            image_bytes = upload.read()

            if not image_bytes:
                return jsonify({"error": "The uploaded image was empty."}), 400

            extraction = ocr.extract_text(image_bytes)
            text = extraction["text"]

            source = {
                "mode": "image",
                "filename": upload.filename,
                "ocr": extraction,
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

        return jsonify(
            {
                "text": text,
                "source": source,
                "prediction": prediction,
                "tactics": rows,
                "summary": build_summary(rows),
                "reviews": reviews.fetch(text),
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
