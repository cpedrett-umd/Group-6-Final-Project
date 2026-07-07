---
team: <your-company-name>
week: 6
date: <YYYY-MM-DD>
members:
  - name: Ciara Cameron
    github: Ciaracam
    hat: Data&Eval
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: <name>
    github: <handle>
    hat: Product | Engineering | Data&Eval
north_star:
  metric: <e.g. task success rate>
  value: <this week>
  previous: <last week>
---

## Shipped this week
- <what is now merged or deployed>  (evidence: #12, PR #34; link the live product if it is deployed)

## User / validation learning
- Today, users usually deal with suspicious or persuasive ads in a manual and inconsistent way. Some users ignore the ad if it feels suspicious, while others click through and try to judge the product after seeing the landing page. They may Google the product or company, check Amazon reviews, search Reddit threads, read comments under the ad, ask friends or family members, or report the ad to the platform.

## Metrics snapshot
- No metrics to report yet.

## Challenges / blockers
- Our initial dataset did not accurately reflect all of our persuasion labels. The dataset was heavily skewed toward urgency and scarcity language, while categories such as FOMO, social proof, authority, and fear appeal were less represented. We also realized that cleaning and labeling the dataset required more manual review than expected due to noisy OCR text, near-duplicate ads, and inconsistent advertisement quality.
- Audio speech recognition for video ads proved to be too inconsistent for collecting data, therefore we narrowed scope.

## Next week's goal
- Refine model architecure
- Finalize preprocessing and labeling dataset

## Individual contributions
- Ciara (Data&Eval) : labeled an initial subset of ads, and developed a data-cleaning script to reduce noisy OCR text and near-duplicate entries.
- Chris (Engineering | Data&Eval): Explored ASR pipeline for audio to text transcription for increasing modalities, drafted initial nlp model architecture in PyTorch.
- <name> (<hat>): <what they did>  (evidence: ...)

## Lean canvas changes (if any)
- Shifted away from OCR and ASR and decided to focus on purely textual ad data.
