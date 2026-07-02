# Persuasion-Aware Ad Explainer: An NLP System for Detecting Emotionally Manipulative Advertising Tactics

[Report](#) | [Demo](#) |

**Group 6 — Final Project**
[Shashank Ashoka](https://github.com/shashk09-coder), [Christopher Pedretti](https://github.com/cpedrett-umd), [Ciara Cameron](https://github.com/Ciaracam), [
Jonathan Kim](https://github.com/Jonathan5108) .

---

## Abstract

Online advertisements routinely employ emotionally persuasive language to influence consumer behavior — particularly targeting older adults with health, financial, and wellness products. We present a multi-modal NLP pipeline that ingests ad content from text, images, or video, detects persuasion tactics at the phrase level, and returns plain-language explanations alongside real-world review evidence. The system is designed for users aged 60 and older who encounter such ads on Facebook, Instagram, YouTube, and news websites, and who may lack a reliable method for evaluating ad credibility before engaging. Unlike approaches that classify ads as fraudulent or legally misleading, our system focuses on **awareness and transparency**: explaining *why* a piece of language is persuasive and *what tactic it employs*, without making legal judgments.

---

## System Overview

![System Architecture](Workflow_Ad_explainer.png)

The pipeline operates in four stages. A confused user who encounters an emotionally loaded ad submits it through one of two interfaces. The input processing layer normalizes the submission into raw text regardless of modality. The main analysis model produces two parallel outputs: a claim and persuasion analysis, and a review insight layer that grounds the analysis in external evidence. These are merged into a single friendly explanation returned to the user.

---

## Method

### Input Interfaces

The system accepts ad content through two surfaces:

**App** — Users upload ad text, a screenshot, or a video recording directly.

**Browser Extension** — Users drag, highlight, or drop an ad region, text block, image, or video from any webpage.

### Input Processing Layer

Raw submissions are routed through three parallel processors depending on modality:

| Input Type | Processor |
|---|---|
| Video or voice recording | Voice agent (ASR transcription) |
| Image or screenshot | OCR (optical character recognition) |
| Raw ad text | Text processor (direct tokenization) |

All three paths emit a unified extracted-text representation passed downstream.

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

## Repository Structure

```
Group-6-Final-Project/
├── data/
│   ├── raw/                    # Collected ad samples
│   └── labeled/                # Annotated persuasion tactic dataset
├── src/
│   ├── input_processing/       # OCR, ASR, and text normalization modules
│   ├── analysis/               # Persuasion classifier and claim checker
│   ├── review_layer/           # Reddit and review scraping + retrieval
│   └── explanation/            # Plain-language output generation
├── extension/                  # Browser extension source
├── app/                        # Mobile/web app interface
├── notebooks/                  # Experiments and evaluation
├── tests/
└── README.md
```

---

## Installation

```bash
git clone https://github.com/your-org/Group-6-Final-Project.git
cd Group-6-Final-Project
pip install -r requirements.txt
```


## Team

| Name | Contribution |
|---|---|
| Chris Pedretti | Engineering, Data&Eval |
| Shashank Ashoka | Architecture, OCR, Agents |
| [Name] | Review insight layer, external evidence retrieval |
| [Name] | App interface and browser extension |
| [Name] | Evaluation, annotation, and documentation |

---

## Notes

This system is built for **educational awareness and media literacy**. It does not provide legal classification of advertisements as fraudulent or deceptive under any regulatory standard. Persuasion tactic labels are informational signals intended to help users think critically about ad language, not definitive judgments about a product or advertiser.
