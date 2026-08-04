---
team: AdInsight
week: 10
date: 2026-08-05
members:
  - name: Ciara Cameron
    github: Ciaracam
    hat: Data&Eval
  - name: Chris Pedretti
    github: cpedrett-umd
    hat: Engineering | Data&Eval
  - name: Jonathan Kim
    github: jonathanjkim5108
    hat: Product | Engineering | Data&Eval
north_star:
  metric: F1 Macro score across class labels
  value: 89.6% (held-out test)
  previous: 86%
---

## Shipped this week

- **Tuned classifier, trained and committed.** Hyperopt TPE search picked the
  training configuration (lr 5e-5, batch 16, 3 epochs, weight decay 0.0);
  retraining just that configuration scores **macro F1 0.896 / accuracy 0.909**
  on the held-out test split. The weights are now in the repo via Git LFS, so a
  clone runs the model with no training step. (evidence: commits c18116b, dba8527)
- **The system runs end to end.** An ad goes in as text or as a screenshot and a
  plain-language explanation comes out. Both interfaces from the wireframe are
  working: a desktop app and a Chrome extension that overlays any page.
  (evidence: commits 0bd0e20, 1240f29)
- **Live OCR, which the pipeline never had.** Image ads were previously collected
  offline into the CSV; nothing turned a screenshot into model input at request
  time. `app/ocr.py` closes that with RapidOCR — pip-only, ~1s per ad on CPU.
- **Explanation layer.** `app/tactics.py` quotes the specific words that make an
  ad pushy, matched against the trigger phrases in our own
  [labeling guidelines](../docs/labeling_guidelines.md).
- **183 tests** — 126 Python (pytest) over the pipeline and API, 57 JavaScript
  (node:test + jsdom) over the extension overlay.
- **Sample test material** in [`samples/`](../samples/README.md) — nine ad texts
  and four ad screenshots, each with the result it actually produces recorded.

## User / validation learning

- Not user-facing yet — the MVP still has not been in front of a real user, and
  that remains the gap. What changed this week is that there is finally
  something testable: both surfaces run on a laptop with no setup beyond
  `pip install`, so moderated sessions with adults 60+ are now schedulable
  rather than blocked.
- Building the panel forced a design finding: the wireframe lists five tactics
  for one ad, but the classifier is single-label. Rather than fake multi-label
  output, the panel merges two signals and badges which is which — "model pick"
  for the prediction, "phrase found" for a guideline trigger phrase literally
  present in the ad. Worth testing whether users read that distinction or ignore it.

## Metrics snapshot

- Macro F1 (north star): **89.6%** on held-out test (was 86%)
- Accuracy: 90.9% · Weighted F1: 91.1%
- Per-class F1: 0.98 Fear Appeals … 0.77 Social Proof (smallest class, 198 examples)
- Model size shipped: 134 MB float16 (was 268 MB float32; zero predictions change)
- Automated tests: 183 (was 0)
- OCR accuracy on sample ad screenshots: 97–98% confidence, 4/4 read correctly

## Challenges / blockers

- **The dataset has no `Neutral` class, and it shows.** Softmax must name one of
  the seven tactics for every input, so the model cannot report "this ad is
  fine". On a genuinely clean ad it is confidently wrong — a bakery's
  opening-hours ad scores 75.8% Social Proof. A low-confidence guard suppresses
  the weakest cases, but not these. Raising the threshold is not the fix; it
  would also suppress correct single-tactic detections in the 70s. **The fix is
  dataset-side: label and add Neutral examples, then retrain.** This is the
  highest-value data task left, and it directly affects how the demo lands.
- The review-insight layer is still a stub. It renders behind a visible "sample
  data" badge so nothing invented is presented as real.
- Ads inside cross-origin iframes cannot be read by the extension at all — that
  covers most programmatic ad slots. Those fall back to right-clicking the image.

## Next week's goal

- Add `Neutral` examples to the dataset and retrain, to stop the false alarms on
  clean ads before anyone demos it.

## Individual contributions

- Chris (Engineering | Data&Eval): Trained and committed the tuned classifier
  (`train_best.py`, reusing `train_hyperopt.py`'s data loading so the split and
  label encoding cannot drift from the tuning run); set up Git LFS and float16
  storage for the weights; built the demo app (`app/`) including the live OCR
  path, the explanation layer, and the desktop window; built the Chrome
  extension (`extension/`); wrote the 183-test suite and the sample ad material.
  (evidence: commits dba8527, 0bd0e20, 1240f29)
- Ciara (Data&Eval): Ran the Hyperopt TPE search over the DistilBERT training
  configuration, producing the trial table and the winning parameters that
  `train_best.py` now trains from. (evidence: commit c18116b)
- Jonathan (Product | Engineering | Data&Eval): Finalized training of the
  baseline model that the hyperparameter search then tuned

## Lean canvas changes (if any)

- No change to user, problem, or value proposition. One risk moved: "can we
  build it" is now answered — both surfaces work end to end. The open risks are
  narrower and more concrete: the missing Neutral class producing false alarms,
  and the fact that no real user has touched it yet.
