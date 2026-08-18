# app/ — AdInsight demo front end

A working demo of the end-product wireframe from the midsemester deck: paste an
ad or upload a screenshot of one, and the tuned classifier explains, in plain
language, how it is trying to persuade you.

Two gaps in the repo are closed here — there was no live OCR path (image ads
were collected offline into the CSV, so nothing turned a screenshot into model
input at request time), and there was no inference surface at all.

```
app/
├── server.py        Flask API + static serving
├── desktop.py       runs the same UI as a native desktop window
├── predict.py       loads the tuned DistilBERT, text -> label + confidence
├── ocr.py           image bytes -> text (VLM preferred, RapidOCR fallback), with space repair
├── vlm_ocr.py       VLM transcription backend (transcription-only prompt, needs OPENAI_API_KEY)
├── tactics.py       trigger-phrase lexicon + plain-language copy
├── reviews.py       review-insight layer: retrieval + summary, sample-data fallback
├── requirements.txt
└── static/          index.html, styles.css, app.js, demo-page.html
```

## Setup

The tuned weights are committed through Git LFS, so a clone already has a
working model. If you cloned before installing LFS, the checkpoint will be a
small text pointer instead of real weights — fix it with:

```bash
git lfs install && git lfs pull
```

Then install dependencies:

```bash
pip install -r app/requirements.txt
```

To rebuild the weights yourself instead (~20 min on CPU, no GPU needed):

```bash
cd modeling && python train_best.py && python compress_model.py
```

`train_best.py` reads the winning hyperopt configuration out of
`hyperopt_results/best_parameters.txt` (lr 5e-5, batch 16, 3 epochs, weight
decay 0.0) and writes `hyperopt_results/best_distilbert_model/`. It reuses
`train_hyperopt.py`'s own data loading, so the split and label encoding match
the tuning run exactly. `compress_model.py` then halves the checkpoint to
float16 — do that before committing, or the repo gains a 268 MB file.

## Two ways to run it

**As a desktop app** — a compact window, no browser chrome, nothing to explain
about localhost before a demo starts:

```bash
python app/desktop.py
```

**As a local web app** — same UI in a browser tab, and the backend the
[extension](../extension/README.md) talks to:

```bash
python app/server.py --warm
```

Then <http://127.0.0.1:5000>. Run it from the repository root. The server holds
the terminal; `Ctrl+C` stops it.

| Flag | Effect |
|---|---|
| `--warm` | Loads the model at startup (~10s) rather than on the first click |
| `--port 8000` | Serve on a different port |
| `--host 0.0.0.0` | Reachable from other machines on the network |

`Address already in use` means something already holds that port — use it, pass
`--port`, or stop it. On Windows: `netstat -ano | findstr :5000` then
`taskkill /PID <pid> /F`. On macOS or Linux: `lsof -ti:5000 | xargs kill`.

`desktop.py` never hits this — it binds to an OS-assigned free port.

If the model or OCR is missing, the page still loads and shows a banner saying
what to run — it won't fail silently mid-demo. `curl http://127.0.0.1:5000/api/health`
checks the same thing from a terminal.

### About the window size

`desktop.py` opens a 420×760 window, shaped like a browser-extension popup
rather than a full-page app: the tool is something you glance at beside an ad,
not something that should take over the screen. The layout collapses to one
column below 940px and tightens again below 520px, so the same UI reflows into
that width — padding and chrome shrink, but **type sizes do not**. The scale is
there for the 60+ audience, and shrinking the text to fit would defeat it.

## The three inputs

| Tab | What it does |
|---|---|
| **Demo ad** | The mock news page and NeuroVital ad from the wireframe, analyzed as-is |
| **Paste ad text** | Any ad copy, typed or pasted |
| **Upload ad image** | A screenshot — OCR reads the words off it, then the model runs |

For image input the panel shows **what OCR actually read** above the verdict.
That is deliberate: a bad scan should be visible to the user, not silently
driving a confident-looking result.

## How the panel's tactic list is built

The wireframe lists five tactics for one ad. The classifier is single-label over
eight classes (7 tactics + Neutral), so it cannot produce that list alone. Two
signals are combined, and each row is badged with its source:

- **`model pick`** — the tuned DistilBERT's predicted class, with its softmax
  confidence. Exactly one row carries this.
- **`phrase found`** — a trigger phrase from
  [`docs/labeling_guidelines.md`](../docs/labeling_guidelines.md) is literally
  present in the ad text. Deterministic, and traceable to the annotation spec
  the dataset was built from.

A row can carry both. The model's pick always leads the list. Full model output
— all eight classes with confidence bars — sits under *Read the full
explanation*, so nothing about the ranking is hidden.

This is the one place the demo deviates from the wireframe's implied behavior,
and the badges make the deviation visible rather than papering over it.

## The review-insight layer

**"What real customers say"** (`reviews.py`) runs live when API keys are set:
an OpenAI glossary of authority-lending terms, Tavily web search shaped as
complaint queries, source-independence ranking (advertiser-owned domains
excluded, affiliate content flagged), and a summary grounded only in retrieved
passages, with links. It needs `OPENAI_API_KEY` and `TAVILY_API_KEY`; without
them — or on any failure — it degrades to hard-coded sample quotes flagged
`mock: true`, and the UI renders a *sample data* badge over the section, so a
demo never breaks and mock data is never mistaken for real evidence.

## Notes on OCR

Image extraction tries the VLM first (`vlm_ocr.py`, transcription-only prompt —
it may not name tactics or judge the ad) when `OPENAI_API_KEY` is set, because
it recovers substantially more text from complex layouts (89% vs 64% of
required strings in our six-real-ad study). RapidOCR remains the fully local,
no-key fallback.

RapidOCR (ONNX) was chosen over Tesseract and EasyOCR because it is pip-only
with no system installer, ships ~15MB of models, and runs an ad in about a
second on CPU — the least that can break on a teammate's laptop before a demo.

Its English model sometimes returns a line with the spaces collapsed
(`70%offbeforethesupplementban`), which would wreck both wordpiece tokenization
and phrase matching. `ocr.py` splits those runs back apart, but only when a
token is clearly merged — the same splitter would otherwise turn brand names
like *MemoryMax* into *Memory Max*. When repair fires, the panel says
"spacing repaired".

`_BACKENDS` in `ocr.py` is an ordered list, so adding Tesseract or EasyOCR later
means adding a function there and nothing else.

## Tests

```bash
python -m pytest tests/ -q
```

130 tests over the lexicon, OCR repair, the classifier wrapper, and every API
route. Tests needing the weights or an OCR backend skip rather than fail, so a
fresh clone runs green. See [tests/README.md](../tests/README.md).

## API

`POST /api/analyze` — JSON `{"text": "..."}` or multipart with an `image` file.

```jsonc
{
  "text": "FINAL HOURS: Doctor-recommended ...",
  "source": { "mode": "image", "ocr": { "confidence": 0.98, "repaired": false } },
  "prediction": { "label": "Urgency", "confidence": 0.91, "distribution": [ ... ] },
  "tactics": [ { "display": "Urgency", "sources": ["model", "phrase"], "phrases": [ ... ] } ],
  "summary": { "headline": "Take your time.", "count": 5 },
  "reviews": { "mock": true, "items": [ ... ] }
}
```

`GET /api/health` — `{ "model_ready": bool, "ocr_backend": "vlm" | "rapidocr" | null }`
(`"vlm"` when `OPENAI_API_KEY` is set, `"rapidocr"` otherwise).

## Scope

This explains persuasion. It does not judge whether a product or seller is
fraudulent, and the UI says so.
