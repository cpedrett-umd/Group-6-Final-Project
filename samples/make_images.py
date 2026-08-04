"""Render the sample ad screenshots in `images/`.

The PNGs are committed, so this only needs running if you want to change them
or add cases. Each one is styled differently on purpose — OCR accuracy varies a
lot with contrast, weight, and letter-spacing, and a demo that only ever sees
one clean render is not being tested.

    python samples/make_images.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).resolve().parent / "images"


# Candidates in preference order, per platform. Pillow resolves bare names
# through the system font path on Windows, but macOS and Linux need the full
# path. Falling through to Pillow's bitmap default would be worse than failing:
# it renders at a fixed tiny size that OCR cannot read, which shows up as a
# confusing test failure rather than a missing-font error.
_REGULAR_FONTS = [
    "arial.ttf",                                          # Windows
    "calibri.ttf",                                        # Windows
    "/System/Library/Fonts/Supplemental/Arial.ttf",       # macOS
    "/Library/Fonts/Arial.ttf",                           # macOS
    "/System/Library/Fonts/Helvetica.ttc",                # macOS
    "DejaVuSans.ttf",                                     # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_BOLD_FONTS = [
    "arialbd.ttf",
    "calibrib.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def find_font(size, bold=False):
    """A scalable system font, or None if the platform has none we know."""
    for name in _BOLD_FONTS if bold else _REGULAR_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def font(size, bold=False):
    resolved = find_font(size, bold)

    if resolved is None:
        raise SystemExit(
            "No scalable system font found (looked for Arial, Calibri, "
            "Helvetica, DejaVu, Liberation).\n"
            "On Linux: apt-get install fonts-dejavu-core"
        )

    return resolved


def render(filename, lines, width=900, background="white", padding=44):
    """lines: list of (text, size, bold, colour)."""
    height = padding * 2 + sum(size + 16 for _text, size, _bold, _colour in lines)

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    y = padding
    for text, size, bold, colour in lines:
        draw.text((padding, y), text, font=font(size, bold), fill=colour)
        y += size + 16

    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / filename)
    print(f"  {filename}  ({width}x{height})")


def main():
    print("Writing sample ad images:")

    # 1. The wireframe's ad — five tactics at once.
    render(
        "supplement_ad.png",
        [
            ("FINAL HOURS", 46, True, (20, 20, 20)),
            ("Doctor-recommended MemoryMax Pro reverses", 30, False, (30, 30, 30)),
            ("memory loss in 14 days. Only 7 bottles left", 30, False, (30, 30, 30)),
            ("— 70% off before the supplement ban.", 30, False, (30, 30, 30)),
            ("Trusted by millions of satisfied customers.", 30, False, (30, 30, 30)),
        ],
    )

    # 2. Light text on a dark background — a harder OCR case.
    render(
        "flash_sale_ad.png",
        [
            ("48 HOURS ONLY", 42, True, (255, 255, 255)),
            ("Limited stock — only 5 kits remaining.", 30, False, (238, 238, 238)),
            ("Act now before this exclusive offer", 30, False, (238, 238, 238)),
            ("disappears forever. Don't miss out!", 30, False, (238, 238, 238)),
        ],
        background=(24, 32, 44),
    )

    # 3. Fear appeal, with tighter type.
    render(
        "home_security_ad.png",
        [
            ("Protect your family tonight", 38, True, (140, 20, 20)),
            ("Break-ins rise 300% this season. Your home", 26, False, (40, 40, 40)),
            ("may be at risk right now. Clinically proven", 26, False, (40, 40, 40)),
            ("sensors stop intruders before they enter.", 26, False, (40, 40, 40)),
        ],
        width=820,
    )

    # 4. A straightforward ad — should come back "nothing pushy found".
    render(
        "bakery_ad.png",
        [
            ("Corner Street Bakery", 38, True, (35, 45, 40)),
            ("Now open on Main Street, 7am to 3pm.", 28, False, (55, 55, 55)),
            ("Fresh sourdough daily. Visit our website", 28, False, (55, 55, 55)),
            ("for hours, directions, and our full menu.", 28, False, (55, 55, 55)),
        ],
        background=(250, 248, 243),
        width=820,
    )


if __name__ == "__main__":
    main()
