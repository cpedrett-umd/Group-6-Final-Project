"""Stub for the review-insight layer ("What real customers say").

That layer -- searching Reddit and consumer review sites for the advertised
product -- is a separate workstream and is not built yet. The wireframe gives it
a panel, so the demo renders the panel and fills it from here.

Everything returned carries ``"mock": True`` and the UI shows a visible badge
over the section. That is deliberate: canned quotes styled to look live would
misrepresent what the system can currently do, which matters more in a demo than
a complete-looking screen.

To make this real, replace `fetch()` with the retrieval call. The response shape
is what the front end already renders.
"""
from __future__ import annotations

NOT_BUILT_NOTICE = (
    "Sample data — the review-insight layer is not built yet."
)

# Illustrative only: these are written to demonstrate the panel's layout and the
# kind of evidence it will carry, not scraped from any real listing.
SAMPLE_REVIEWS = [
    {
        "source": "Trustpilot",
        "rating": "2.1★",
        "quote": "Auto-billed monthly. Six calls to cancel.",
    },
    {
        "source": "Reddit · r/scams",
        "rating": None,
        "quote": "14 threads report this seller since March.",
    },
]


def fetch(text: str) -> dict:
    """Return placeholder review evidence for an ad.

    `text` is accepted so the signature already matches what a real
    implementation needs; it is unused while this is a stub.
    """
    return {
        "mock": True,
        "notice": NOT_BUILT_NOTICE,
        "items": SAMPLE_REVIEWS,
    }
