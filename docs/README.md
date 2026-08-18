# AdInsight — Final Project Submission (Group 6)

DATA/MSAI/MSML 641 · Natural Language Processing · August 19, 2026

AdInsight shows users **how** an online ad is trying to persuade them — naming the
persuasion tactic (urgency, scarcity, FOMO, fear appeals, authority, social proof,
exaggerated claims), explaining it in plain language with the ad's own words as
evidence, and pulling independent review context. Built for adults 60+; no
"scam / not scam" verdicts, no legal claims.

**Team:** Chris Pedretti (Engineering · Data & Eval) · Shashank Ashoka
(Architecture · OCR/VLM · Agents) · Ciara Cameron (Review Insights · Evidence) ·
Jonathan Kim (App · Browser Extension)

## Contents

| File | What it is |
|---|---|
| `slides.pdf` | Final presentation slides (11 slides, one per rubric area) |
| `report.md` | Final written report, sectioned by the five rubric areas |

## Run it locally

There is no hosted URL — the app runs entirely on your machine.

```bash
git lfs install
git clone https://github.com/cpedrett-umd/Group-6-Final-Project.git
cd Group-6-Final-Project
pip install -r requirements.txt
python app/desktop.py            # native desktop window (model loads in ~10s)
```

Or the web UI / extension path:

```bash
python app/server.py --warm      # then open http://127.0.0.1:5000
```

**Chrome extension:** with the server running, open `chrome://extensions`, enable
Developer mode, *Load unpacked*, select the `extension/` folder, then visit the
demo article at `http://127.0.0.1:5000/demo-page`.

**Smoke test:**

```bash
curl -X POST http://127.0.0.1:5000/api/analyze -F "image=@samples/images/supplement_ad.png"
```

**Optional API keys** (the app runs fully local without them):
`OPENAI_API_KEY` enables VLM transcription of image ads and the review-layer
glossary/summary; `TAVILY_API_KEY` enables live review retrieval. Without keys,
image ads use the on-device RapidOCR path and the review panel shows
clearly-badged sample data.

**Tests:** `python -m pytest tests/ -q` (126 Python) and
`cd extension/tests && npm install && npm test` (57 JavaScript).
