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
  - name: Shashank Ashoka
    github: shashk09-coder
    hat: Architecture | OCR | Agents
north_star:
  metric: F1 Macro score across class labels
  value: 0.9191 (8 classes, incl. Neutral)
  previous: 0.8960 (7 classes)
---

## Shipped this week
- **Tuned classifier, trained and committed.** Hyperopt TPE search picked the
  training configuration (lr 5e-5, batch 16, 3 epochs, weight decay 0.0);
  retraining just that configuration scores **macro F1 0.9191/ accuracy 0.9285**
  on the held-out test split. The weights are now in the repo via Git LFS, so a
- **Diagnosed shortcut learning.** in the labeled corpus. Statistical n-gram mining (log-odds against document frequency) over ads_dataset_labeled.csv showed four of seven classes are effectively defined by a single token. limited stock appears in 435 of 449 Scarcity rows — 96.9%.
- **Merged the Mathur et al.** dark-patterns corpus into the dataset, mapping their Scarcity, Urgency and Social Proof onto ours and dropping the four categories with no counterpart in our taxonomy. Adds ~940 rows of real scraped e-commerce phrasing.
- **Added a Neutral class**. (~250 generated benign ad texts at matched length), which the corpus previously lacked entirely.
- Added sliding-window inference to app/predict.py. Text over 126 subwords is scored in overlapping windows and max-pooled per class rather than truncated.
- Retrained the classifier on the merged corpus: 4,374 rows, 8 classes.
- Fixed a Neutral-handling bug the retrain exposed in app/tactics.py — the panel rendered a Neutral verdict as a finding and told the user a clean ad "is a pressure tactic". Neutral now returns no tactic rows; trigger-phrase hits still surface.
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

**Model, held-out test split**

| | Before | After |
|---|---|---|
| Rows | 3,230 | 4,374 |
| Classes | 7 | 8 |
| Test accuracy | 0.9090 | 0.9285 |
| Test macro F1 | 0.8960 | 0.9191 |
| Macro F1, original 7 classes only | 0.8960 | 0.9070 |
| Social Proof F1 | 0.77 | 0.88 |
| Class imbalance ratio | 4.6× | 4.3× |

**Shortcut coverage** — share of a class covered by its single most frequent n-gram:

| Class | Before | After |
|---|---|---|
| Scarcity | 97.3% | 73.4% |
| Urgency | 91.6% | 74.0% |
| Social Proof | 36.4% | 19.2% |

- Model size shipped: 134 MB float16 (was 268 MB float32; zero predictions change)
- Automated tests: 183 (was 0)
- OCR accuracy on sample ad screenshots: 97–98% confidence, 4/4 read correctly
-**Documented failure, now fixed.** The bakery counter-example in
`samples/README.md` — *"Fresh bread daily. Open 7am to 5pm, Tuesday to Sunday."*
— scored **75.8% Social Proof** under the previous model and was reported to the
user as a pressure tactic. It now classifies as **Neutral at 100%**, and the
panel correctly reports nothing pushy.

<img width="1356" alt="Bakery ad analysed by the retrained model — classified Neutral, no tactics reported" src="https://github.com/user-attachments/assets/f0813efa-3d24-4b77-851a-b8c23996c2a6" />

*Figure 1 — the retrained model on the bakery ad: Neutral, and the panel reports no pressure tactics.*

<img width="653" alt="Full distribution for the bakery ad — Neutral at 100%, all seven tactic classes at 0%" src="https://github.com/user-attachments/assets/3770cde2-09eb-4400-9dbe-59d8aef2cdc6" />

*Figure 2 — full class distribution: Neutral at 100%, every tactic class at 0%.*



## Challenges / blockers

- **The Neutral class does not generalise**. It scores 1.00 precision and recall on the test split, which is a warning rather than a result — the generated templates are trivially separable. Tested against a real benign ad (a Chime checking-account promotion), Neutral ranked sixth of eight at 5%. The class learned "opening hours, parking, local business", not "absence of pressure". Replacing it with real benign ads is the honest fix.
- **Sentence-level attribution failed.** Classifying individual sentences of a long ad returned a dosage instruction ("You should take two capsules daily") as Fear Appeals at 99%, and a phrase containing "bottleneck" as Scarcity at 97%. Every sentence is far outside the retail ad copy the model was fine-tuned on, so it pattern-matches individual words with high confidence.
- **Occlusion attribution could not localise the prediction either.** Leave-one-out over 33 sentences produced a maximum confidence drop of 7.3% against a 42.5% baseline, with everything else in a 2–6% band. At a 20%-of-baseline threshold, zero driver sentences. The signal is diffuse, not localised.
- The review-insight layer is still a stub. It renders behind a visible "sample
  data" badge so nothing invented is presented as real.
- **API access was never granted.** Applied for early in the term; still no response. Meta Ad Library API access is also blocked pending identity confirmation. Retrieval for the review layer will need a general web search API instead.
- Ads inside cross-origin iframes cannot be read by the extension at all — that
  covers most programmatic ad slots. Those fall back to right-clicking the image.

## Next week's goal

- Usability testing with 5–8 adults 60+ — think-aloud protocol, 4–6 tasks, recorded success/failure. This is the outstanding milestone and it needs no ML work.
- Build the review-insight layer against a web search API, with claim extraction driving the query and source-independence scoring (advertiser's own domain and affiliate content excluded).
- Deliverable: a working review panel with real retrieved quotes, and a written usability findings summary.

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
- Shashank (Architecture | OCR | Agents): Mined the labeled corpus statistically and identified shortcut learning across four classes; merged the Mathur et al. dark-patterns corpus and added a Neutral class; retrained and evaluated the classifier; fixed the Neutral-handling bug in tactics.py; added sliding-window inference to predict.py; built the ASR input-compatibility study on 41 collected video ads.

## Lean canvas changes (if any)

- No change to user, problem, or value proposition. One risk moved: "can we
  build it" is now answered — both surfaces work end to end. The open risks are
  narrower and more concrete: the missing Neutral class producing false alarms,
  and the fact that no real user has touched it yet.
