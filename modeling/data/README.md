# Evaluation inputs (not committed)

The three evaluation notebooks in `modeling/` resolve every path relative to the
repo root, so they run from a fresh clone — but two inputs are third-party ad
content we don't redistribute. Place them here to re-run:

| Path | Used by | What it is |
|---|---|---|
| `cheers_ad_transcript.txt` | `sentence_attribution.ipynb`, `occlusion_attribution.ipynb` | Plain-text transcript of the Cheers Protect video ad (~584 words) |
| `real_ads/` | `vlm_extraction.ipynb` | The six evaluation screenshots: `ad.png`, `ad_1.png`, `ad_12.png`, `RYZE_AD.jpeg`, and the two WhatsApp reel captures |

Without these files the notebooks stop with a clear message instead of a stack
trace; their committed outputs record the full executed run either way.

`vlm_extraction.ipynb` also needs `OPENAI_API_KEY` set in the environment for
the VLM calls, and imports its transcription prompt from `app/vlm_ocr.py` so the
study and the shipped extraction path can't drift apart.
