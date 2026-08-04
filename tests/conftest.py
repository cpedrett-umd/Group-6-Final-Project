"""Shared fixtures.

`app/` is put on sys.path because the app's modules import each other as
top-level names (`import ocr`), which is what running `python app/server.py`
gives them. Tests have to reproduce that or every import fails.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIRECTORY = REPO_ROOT / "app"
SAMPLES_DIRECTORY = REPO_ROOT / "samples"

for directory in (APP_DIRECTORY, SAMPLES_DIRECTORY):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


# ── Sample ad text ──────────────────────────────────────────────

# The ad from the wireframe. Its five tactics are the reference case for the
# whole explanation layer, so it is reused across suites.
WIREFRAME_AD = (
    "FINAL HOURS: Doctor-recommended MemoryMax Pro reverses memory loss in "
    "14 days. Only 7 bottles left - 70% off before the supplement ban."
)

NEUTRAL_AD = (
    "Our new bakery is now open on Main Street. "
    "Visit our website for hours and directions."
)

FEAR_AD = (
    "Protect your family from harmful bacteria. Clinically proven to "
    "eliminate 99.9% of germs in your home."
)


@pytest.fixture
def wireframe_ad():
    return WIREFRAME_AD


@pytest.fixture
def neutral_ad():
    return NEUTRAL_AD


@pytest.fixture
def fear_ad():
    return FEAR_AD


# ── Images ──────────────────────────────────────────────────────


def has_scalable_font():
    """Whether this machine has a font we can render legible text with.

    Pillow's bitmap default renders at a fixed tiny size that OCR cannot read,
    so tests depending on rendered text skip rather than fail confusingly.
    """
    from make_images import find_font

    return find_font(24) is not None


def render_ad_image(lines, width=1000, height=None, font_size=32):
    """Render text as a PNG, standing in for an ad screenshot."""
    from PIL import Image, ImageDraw

    from make_images import find_font

    height = height or (60 + len(lines) * (font_size + 18))

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    font = find_font(font_size)

    y = 30
    for line in lines:
        draw.text((40, y), line, font=font, fill=(17, 17, 17))
        y += font_size + 18

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def ad_image_bytes():
    return render_ad_image(
        [
            "LIMITED TIME OFFER",
            "Clinically proven formula. Only 5 kits left.",
            "Act now before stock runs out.",
        ]
    )


@pytest.fixture
def blank_image_bytes():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def not_an_image_bytes():
    return b"this is definitely not a PNG file"


# ── App / server ────────────────────────────────────────────────


@pytest.fixture(scope="session")
def model_available():
    import predict

    return predict.is_ready()


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)

    with server.app.test_client() as test_client:
        yield test_client


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "model: needs the trained weights (run modeling/train_best.py)"
    )
    config.addinivalue_line("markers", "ocr: needs an OCR backend installed")
    config.addinivalue_line("markers", "slow: takes more than a second")
    config.addinivalue_line(
        "markers", "renders: needs a scalable system font to draw a test image"
    )


def pytest_collection_modifyitems(config, items):
    """Skip model/OCR tests instead of failing when the artifact isn't there.

    A teammate who has only cloned the repo should be able to run the suite and
    see the pure-logic tests pass, rather than a wall of errors about weights
    they haven't downloaded yet.
    """
    import predict

    try:
        import ocr

        has_ocr = ocr.available_backend() is not None
    except ImportError:  # pragma: no cover
        has_ocr = False

    has_model = predict.is_ready()

    skip_model = pytest.mark.skip(
        reason="no trained weights - they are committed via Git LFS, so try "
        "`git lfs install && git lfs pull`, or rebuild with "
        "`cd modeling && python train_best.py`"
    )
    skip_ocr = pytest.mark.skip(
        reason="no OCR backend - run `pip install rapidocr-onnxruntime`"
    )
    skip_renders = pytest.mark.skip(
        reason="no scalable system font - install DejaVu or Liberation fonts"
    )

    can_render = has_scalable_font()

    for item in items:
        if "model" in item.keywords and not has_model:
            item.add_marker(skip_model)
        if "ocr" in item.keywords and not has_ocr:
            item.add_marker(skip_ocr)
        if "renders" in item.keywords and not can_render:
            item.add_marker(skip_renders)
