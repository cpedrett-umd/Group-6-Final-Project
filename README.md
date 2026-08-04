# AdInsight — Persuasion-Aware Ad Explainer

*Helping users understand the persuasion behind every advertisement.*

An NLP system for detecting emotionally manipulative advertising tactics.

[Report](#) | [Demo](app/README.md) |

**Group 6 — Final Project**
[Shashank Ashoka](https://github.com/shashk09-coder), [Christopher Pedretti](https://github.com/cpedrett-umd), [Ciara Cameron](https://github.com/Ciaracam), [
Jonathan Kim](https://github.com/Jonathan5108) .

---

## Abstract

Online advertisements routinely employ emotionally persuasive language to influence consumer behavior — particularly targeting older adults with health, financial, and wellness products. We present a multi-modal NLP pipeline that ingests ad content from text or images, detects persuasion tactics at the phrase level, and returns plain-language explanations alongside real-world review evidence. The system is designed for users aged 60 and older who encounter such ads on Facebook, Instagram, YouTube, and news websites, and who may lack a reliable method for evaluating ad credibility before engaging. Unlike approaches that classify ads as fraudulent or legally misleading, our system focuses on **awareness and transparency**: explaining *why* a piece of language is persuasive and *what tactic it employs*, without making legal judgments.

---

## System Overview

![System Architecture](docs/workflow_ad_explainer.png)

The pipeline operates in four stages. A confused user who encounters an emotionally loaded ad submits it through one of two interfaces. The input processing layer normalizes the submission into raw text regardless of modality. The main analysis model produces two parallel outputs: a claim and persuasion analysis, and a review insight layer that grounds the analysis in external evidence. These are merged into a single friendly explanation returned to the user.

---

## Method

### Input Interfaces

The system accepts ad content through two surfaces:

**App** — Users upload ad text or a screenshot directly.

**Browser Extension** — Users drag, highlight, or drop an ad region, text block, or image from any webpage.

### Input Processing Layer

Raw submissions are routed through two parallel processors depending on modality:

| Input Type | Processor |
|---|---|
| Image or screenshot | OCR (optical character recognition) |
| Raw ad text | Text processor (direct tokenization) |

Both paths emit a unified extracted-text representation passed downstream.

### Main Analysis Model

The extracted ad content is analyzed by a central NLP model that generates two types of insight simultaneously:

**Claim and Persuasion Analysis**
- Explains scientific or technical terms used in the ad
- Checks whether stated claims are supported by evidence
- Detects and classifies emotionally manipulative tactics
- Issues a scam / not-scam signal (informational, not legal)

**Review Insight Layer**
- Searches Reddit threads and consumer review websites
- Retrieves real user reviews for the advertised product or service
- Identifies recurring complaints and negative patterns
- Surfaces real-world evidence alongside the model's internal analysis

### Persuasion Tactics Detected

| Tactic | Description | Example Trigger Language |
|---|---|---|
| Urgency | Creates artificial time pressure | "Act now", "Offer ends tonight" |
| FOMO | Exploits fear of missing out | "Everyone is switching to...", "Don't miss out" |
| Fear Appeals | Induces anxiety about health or safety | "Without this, you risk...", "Doctors are alarmed" |
| Scarcity | Implies limited availability | "Only 3 left", "Limited supply" |
| Exaggerated Claims | Makes unsubstantiated or inflated promises | "Cures in 24 hours", "Guaranteed results" |
| Authority Manipulation | Invokes false or unverifiable authority | "As seen on TV", "Doctor-approved" |
| Social Proof | Uses crowd behavior to validate the product | "Over 1 million satisfied customers" |

### Output

The two analysis branches are merged into a **friendly user explanation**: a clear, concise, plain-language summary that helps the user decide whether to trust the ad, without requiring them to interpret model outputs directly.

---

## Target Population

The primary user group is adults aged 60 and older. This group is disproportionately exposed to ads for health products, supplements, insurance, and financial services, and may encounter persuasion techniques — personal relevance framing, pseudo-scientific language, and artificial scarcity — that are difficult to identify without prior media literacy exposure. The system is designed to require no technical knowledge to use.

The tool generalizes to any consumer affected by emotionally persuasive advertising, including younger users encountering influencer marketing, FOMO-driven promotions, or misleading wellness claims.

---

## Project Status (Midsemester)

**Decision: persevere.** The problem — and users' appetite for third-party
evidence — is validated by published consumer research (FTC Consumer Sentinel,
AARP fraud surveys, BrightLocal, YouGov). The data engine works. The main open
question is usability, which drives the second half of the semester.

**Built so far — the data engine.** A multi-modal collection pipeline funnels
two input types into one labeled dataset:

- **7,768** ad texts in the unified dataset
- **2** input modalities piloted — text (regex-based ad-copy scraping) and
  image (OCR over ad screenshots)
- **8** annotation labels — the 7 persuasion tactics above plus *neutral* —
  with written [labeling guidelines](docs/labeling_guidelines.md)
- A HuggingFace subword tokenizer ([modeling/](modeling/)) that prepares the
  text for the classifier

**Scope change — audio dropped.** Voice/video (ASR) collection proved
inconsistent and hard to standardize, so the audio modality was removed and
effort was redirected to text and image. (Prior ASR work is retained under
`datasets/audio_processing (deprecated)/`.)

**North-star metric:** macro F1 across the 7 persuasion-tactic classes.

### The tactic classifier

DistilBERT fine-tuned on the 3,230 labeled ads, with the training configuration
chosen by a Hyperopt TPE search (`modeling/train_hyperopt.py`). The winning
configuration — lr 5e-5, batch 16, 3 epochs, weight decay 0.0 — scores on the
held-out test split (15%, stratified):

| Metric | Score |
|---|---|
| **Macro F1** (north star) | **0.896** |
| Accuracy | 0.909 |
| Weighted F1 | 0.911 |

Per-class F1 ranges from 0.77 (Social Proof, the smallest class at 198 examples)
to 0.98 (Fear Appeals). Class weighting in the loss compensates for the ~4.6x
imbalance.

The weights are committed via Git LFS as **float16** (134 MB rather than 268 MB).
float16 changes none of the 485 held-out test predictions and leaves macro F1 at
0.8956, so the extra precision would be pure clone cost; `app/predict.py` casts
back to float32 at load. After retraining, run `python compress_model.py` before
committing, or the repo gains a 268 MB file.

### Road to demo day

1. ~~Merge & annotate the multi-modal dataset~~ — done
2. ~~Train & evaluate the tactic classifier~~ — done, macro F1 0.896
3. Build the explanation & review-insight layers — explanation layer done
   (`app/tactics.py`); review-insight layer still stubbed
4. ~~Ship the app & browser-extension MVP~~ — both surfaces working
   (`app/`, `extension/`)
5. Usability tests with adults 60+ → demo day

---

## Repository Structure

```
Group-6-Final-Project/
├── datasets/
│   ├── text_processing/                    # Ad-text dataset + tokenizer artifacts
│   │   ├── ads_dataset_labeled.csv         # Labeled dataset (3,230 ads, 7 tactic classes)
│   │   ├── ads_tokenizer/                  # Saved HF tokenizer (vocab + config)
│   │   ├── tokenized_ads.pt                # Pre-tokenized dataset, ready to load
│   │   ├── label_ads.py                    # Labeling helper script
│   │   ├── main.py                         # Dataset cleaning / build script
│   │   ├── requirements.txt
│   │   └── ads_dataset_*(deprecated).csv   # Earlier dataset iterations, kept for reference
│   └── audio_processing (deprecated)/      # Prior ASR experiment (video ads)
├── modeling/                               # Tokenizer + tactic classifier
│   ├── hf_tokenizer.py                     # AdsTokenizer + dataset-tokenization script
│   ├── train_baseline.py                   # Baseline DistilBERT fine-tune
│   ├── train_hyperopt.py                   # Hyperopt (TPE) search over the training config
│   ├── train_best.py                       # Trains just the winning config → saved weights
│   ├── compress_model.py                   # Converts saved weights to fp16 before committing
│   ├── hyperopt_results/                   # Trial table, best parameters, best model (LFS)
│   ├── requirements.txt
│   └── README.md                           # Tokenizer usage + artifact details
├── app/                                    # App surface — the wireframe, working
│   ├── server.py                           # Flask API + static serving
│   ├── desktop.py                          # Same UI as a native desktop window
│   ├── predict.py                          # Tuned model → label + confidence
│   ├── ocr.py                              # Ad screenshot → text (RapidOCR)
│   ├── tactics.py                          # Trigger-phrase lexicon + plain-language copy
│   ├── reviews.py                          # Stub for the review-insight layer
│   ├── static/                             # index.html, styles.css, app.js, demo-page.html
│   ├── requirements.txt
│   └── README.md                           # Setup, the three inputs, API shape
├── extension/                              # Browser-extension surface (Chrome MV3)
│   ├── manifest.json
│   ├── background.js                       # Service worker — network + context menus
│   ├── content.js                          # Overlay: ad detection, pick mode, rendering
│   ├── panel.css                           # Overlay styles (shadow-root scoped)
│   ├── popup.html / popup.js               # Toolbar popup
│   ├── tests/                              # 57 tests (node:test + jsdom)
│   └── README.md
├── tests/                                  # 118 Python tests (pytest)
├── docs/                                   # Project docs and reference material
│   ├── project_overview.pdf
│   ├── labeling_guidelines.md
│   └── workflow_ad_explainer.png           # System architecture diagram
├── weekly_reports/                         # Per-week progress reports
├── .gitignore
└── README.md
```

The abstract above describes the full planned system (multimodal input, analysis
model, review layer, app, and extension). The repository now covers the data and
tokenization groundwork, the **tuned tactic classifier**, and a **working demo
front end** for both input modalities. The review-insight layer is the main piece
still outstanding — `app/reviews.py` holds its stub.

---

## Installation

```bash
git clone https://github.com/cpedrett-umd/Group-6-Final-Project.git
cd Group-6-Final-Project

# Tokenizer (modeling/) — subword tokenization for the base NLP model
pip install -r modeling/requirements.txt

# Dataset cleaning / labeling scripts (datasets/text_processing/)
pip install -r "datasets/text_processing/requirements.txt"
```

See [modeling/README.md](modeling/README.md) for how to load the pre-tokenized
dataset or regenerate the tokenizer artifacts.

## Running the demo

```bash
pip install -r modeling/requirements.txt -r app/requirements.txt
```

The tuned weights are committed through **Git LFS**, so a clone comes with a
working model — no training step. Make sure LFS is installed before cloning
(`git lfs install`); if you cloned without it, run `git lfs pull`.

**App** — a compact desktop window:

```bash
python app/desktop.py
```

**Browser extension** — start the backend, then load `extension/` unpacked via
`chrome://extensions` → Developer mode → Load unpacked, and open
<http://127.0.0.1:5000/demo-page>:

```bash
python app/server.py --warm
```

Both surfaces accept ad text or an ad screenshot; OCR reads the words off the
image and feeds them to the classifier. See [app/README.md](app/README.md) and
[extension/README.md](extension/README.md).

## Tests

```bash
python -m pytest tests/ -q
```

```bash
cd extension/tests && npm install && npm test
```

175 tests — 118 Python over the analysis pipeline and API, 57 JavaScript over
the extension overlay. Tests that need the weights or an OCR backend skip
rather than fail, so a fresh clone runs green.


## Team

| Name | Contribution |
|---|---|
| Chris Pedretti | Engineering, Data&Eval |
| Shashank Ashoka | Architecture, OCR, Agents |
| Ciara Cameron | Review insight layer, external evidence retrieval |
| Jonathan Kim | App interface and browser extension |

---

## Notes

This system is built for **educational awareness and media literacy**. It does not provide legal classification of advertisements as fraudulent or deceptive under any regulatory standard. Persuasion tactic labels are informational signals intended to help users think critically about ad language, not definitive judgments about a product or advertiser.
