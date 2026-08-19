# AdInsight — Final Project Submission (Group 6)

DATA/MSAI/MSML 641 · Natural Language Processing · August 19, 2026

AdInsight shows users **how** an online ad is trying to persuade them — naming the
persuasion tactic (urgency, scarcity, FOMO, fear appeals, authority, social proof,
exaggerated claims), explaining it in plain language with the ad's own words as
evidence. Built for adults 60+; no
"scam / not scam" verdicts, no legal claims.

**Team:** Chris Pedretti (Engineering · Classifier · App & Extension) ·
Shashank Ashoka (Architecture · ASR/VLM Studies · VLM Extraction) ·
Ciara Cameron (Data & Annotation · Hyperparameter Tuning) ·
Jonathan Kim (Data Pipeline · Preprocessing · Baseline Model)

## Contents

| File | What it is |
|---|---|
| `AdInsight_Final_Presentation.pdf` | Final presentation slides (11 slides, one per rubric area) |
| `AdInsight_Final_Presentation.pptx` | Same deck with speaker notes, for presenting |
| `AdInsight_Final_Report.pdf` | Final written report, sectioned by the five rubric areas |
| `AdInsight_Final_Report.docx` | Report source document |

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

**Optional API key** (the app runs fully local without it):
`OPENAI_API_KEY` enables VLM transcription of image ads. Without it, image ads
use the on-device RapidOCR path.

**Tests:** `python -m pytest tests/ -q` (130 Python) and
`cd extension/tests && npm install && npm test` (56 JavaScript).
