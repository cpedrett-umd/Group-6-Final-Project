---
team: AdInsight
week: 11
date: 2026-08-15
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
  previous: 0.9191 (unchanged — no retrain this week)
---

## Shipped this week

 
- **First measurement of the system against real ads.** Six ad screenshots
  collected from X, Instagram and short-form video — hand-labelled for both the
  text they contain (53 required strings) and the persuasion tactic they use.
  This is the project's first held-out evaluation on genuine advertising rather
  than the synthetic corpus.
- **Text-extraction comparison: OCR vs vision-language model.** Three extractors
  scored on the same six ads. VLM recovery 89% against 64% for the project's
  current OCR path. Requested by the instructor before we committed to the
  approach; approved on condition the prompt stays transcription-only.
  → [`vlm_extraction.ipynb`](../vlm_extraction.ipynb)
- **Claim and query extraction for the review layer.** A second VLM call returns
  the brand, the promise the ad makes, and the search a cautious buyer would
  type. It returns NONE when no product is named rather than inventing a generic
  search — verified on all three income ads in the set.
- **Prompt scope kept narrow.** The VLM transcribes and reports what the ad
  claims. It never names a tactic, never judges the ad, and never decides whether
  a claim is true. Classification remains the fine-tuned DistilBERT.
## User / validation learning
 
Nothing user-facing shipped this week; usability testing with adults 60+ is still
outstanding and is now the largest gap against the course's definition of
"validated".
 
What the six-ad evaluation did surface is a design finding. On these ads the
system is protected by its uncertainty rather than its accuracy: the classifier's
top score fell below the 0.60 guard on four of six, so nothing was reported to
the user. Where it did cross the guard it was wrong — "I Made $500K in 2 Minutes"
was reported as Urgency at 98%, with no deadline anywhere in the ad. For a 60+
audience silence is the right failure mode, but the demo should present it as
such rather than implying accuracy.
 
## Metrics snapshot
 
### Text extraction across six real ad screenshots (53 required strings)
<img width="1860" height="743" alt="extraction_comparison" src="https://github.com/user-attachments/assets/deb65860-d133-4c23-a577-e242961f0e96" />

 
Three outcomes are distinguished. **Exact** — the string is present as written.
**Spacing-damaged** — present only once spaces are stripped (`TRYRYZE`,
`WINUP TO $900`), so the word-boundary regexes in `tactics.py` cannot match it and
it is unusable downstream. **Missing** — absent entirely.
 
| Extractor | Required | Exact | Spacing-damaged | Missing | Recovery | Mean s |
|---|---|---|---|---|---|---|
| RapidOCR (raw) | 53 | 29 | 19 | 5 | 55% | 2.0 |
| `app/ocr.py` | 53 | 34 | 13 | 6 | 64% | 0.8 |
| **VLM (gpt-4o)** | 53 | **47** | **2** | 4 | **89%** | 1.4 |
 
*PaddleOCR was included in the comparison but failed on all six images with an
API argument error and is omitted from the table.*
 
- **Spacing damage is the dominant OCR failure, not misreading.** Only 5–6 strings
  were lost outright by either OCR path; 19 and 13 respectively were recovered but
  run together. The existing space-repair step in [`app/ocr.py`](../app/ocr.py)
  converts 6 damaged strings into exact matches over raw RapidOCR — real work,
  but the VLM reduces the count to 2.
- **The gap widens as layout gets harder.** On the Chime creative — large type on
  a flat background — `app/ocr.py` scored 10/10 and beat the VLM, which omitted
  the card-face text. On a dense tweet screenshot both OCR paths scored **0/8**:
  every string was present but glued together
  (`youareCOOKEDifyoucan'tmake$20K+permonthonlinein2026`). The VLM scored 7/8.
- **The failure that motivated this is fixed.** On the RYZE ad both OCR paths lost
  `THIS WEEK ONLY` entirely — a profile avatar overlaps the "TH" and OCR returned
  `ISWEEKONLY` — so the Urgency trigger never matched and the ad was reported as
  clean. The VLM recovers it.
### Classification on the same six ads
 
| Input | Tactic correct | Trigger phrases fired |
|---|---|---|
| RapidOCR | 1 / 6 | 0 |
| `app/ocr.py` | 1 / 6 | 0 |
| VLM | 0 / 6 | 0 |
 
**Better extraction did not produce better classification.** Zero trigger phrases
fired across all 18 runs. Four of the six ads make income claims — a category
absent from both the training corpus and the trigger lexicon — so cleaner input
into a model that has never seen this ad type yields a different wrong answer
rather than a right one. On one ad the VLM's cleaner text pushed a wrong
prediction from 57% to 86%, crossing the guard and surfacing a confident error
where OCR had produced a suppressed one.
 
The bottleneck on real ads is the training distribution, not the input pipeline.
 
### Claim extraction for the review layer
 
| Ad | Brand | Query generated |
|---|---|---|
| RYZE mushroom coffee | RYZE | `RYZE mushroom coffee reviews potbelly results` |
| Chime | Chime | `Do Chime checking accounts really spot you $200?` |
| Kling 3.0 / MakeUGC | Kling 3.0 | `Kling 3.0 ad creation service reviews` |
| "$20K+ per month" tweet | NONE | NONE |
| "I Made $500K in 2 Minutes" | NONE | NONE |
| "WIN UP TO $900" | NONE | NONE |
 
Three of six ads promise income and name no product, company or service. There is
nothing to look up, and the extractor correctly says so rather than fabricating a
search. An earlier prompt returned `How to make $500K fast reviews` for one of
these — a query that would surface more of the same genre of content — which is
why the "no searchable entity" rule was added explicitly.
 
## Challenges / blockers
 
- **Usability testing with adults 60+ has not started.** It is the outstanding
  milestone from week 8 and needs no ML work. It is now the primary risk to the
  final criteria.
- **The review-insight layer is still a stub.** Query generation now works; the
  retrieval and scoring half is not built.
  → [`app/reviews.py`](../app/reviews.py)
- **Reddit API access was never granted** despite applying early in the term.
  Meta Ad Library API access is blocked pending identity confirmation. The
  instructor has approved a general web search API instead, noting that a single
  source is difficult to score for independence while several give something real
  to work with.
- **The VLM is a network dependency in the request path.** RapidOCR must stay as
  fallback so a failed call degrades rather than breaks the demo.
- **Six ads is a small evaluation set.** The extraction figures are measured, but
  the classification figures (1/6, 0/6) are indicative rather than statistically
  meaningful.
## Review-insight layer — build plan
 
The layer is specified by the interface the front end already renders:
`reviews.fetch()` returns `{"mock", "notice", "items": [{"source", "quote"}]}`.
Replacing the stub's internals requires no change to `app.js` or `content.js`.
 
**1. Claim extraction — built.** The VLM returns brand, promise, and the search
query a cautious buyer would type, or NONE where no product is named.
 
**2. Query strategy driven by the classifier.** The tactic label selects what kind
of scrutiny the ad receives: Exaggerated Claims routes to evidence queries ("does
X work"), Scarcity and Urgency to conduct queries ("X complaint", "X cancel
subscription"), Authority Manipulation to credential checks. This is what keeps
the fine-tuned model steering retrieval rather than sitting beside it.
 
**3. Retrieval via a general web search API.** Complaint-shaped queries
outperformed review-shaped ones in testing — a review query returned SEO
listicles and affiliate content, while a complaint query returned Better Business
Bureau records and genuine cancellation problems. This mirrors the FTC's own
advice to search a seller's name alongside "complaint", which the mid-semester
deck cited as the behaviour this layer automates.
 
**4. Source-independence scoring.** Testing surfaced two contaminants a naive
pipeline would present as evidence: a page hosted on the advertiser's own
subdomain, and a blog carrying an affiliate discount code. The scorer excludes
domains derived from the extracted brand, flags affiliate markers, and ranks
remaining sources by tier — regulators and consumer-protection bodies first, then
verified-purchase retail, then forums.
 
**5. The no-entity branch.** Where no product is named, the panel reports that
plainly and hands the user a method rather than a verdict: for an ad promising
money with no company named, that absence is itself the finding.
 
**Fallback.** If retrieval returns nothing above the relevance floor, the layer
returns the existing placeholder set with `mock: true` intact, so the "sample
data" badge behaves exactly as it does today and the change cannot regress the
current behaviour.
 
## Next week's goal
 
- Wire retrieval and source scoring into [`app/reviews.py`](../app/reviews.py)
  behind the existing interface, with the mock fallback preserved.
- Usability testing with 5–8 adults 60+ — think-aloud protocol, 4–6 tasks.
- Update the stale copy in [`app/static/app.js`](../app/static/app.js) and
  [`extension/content.js`](../extension/content.js), which still states the model
  was trained on 3,230 ads with no neutral label while the panel displays a
  Neutral score.
- Deliverable: a review panel showing real retrieved quotes with source
  attribution, and a written usability findings summary.

## Individual contributions

- **Chris (Engineering | Data&Eval):** Trained and committed the tuned classifier
  ([`train_best.py`](../modeling/train_best.py), reusing
  [`train_hyperopt.py`](../modeling/train_hyperopt.py)'s data loading so the split
  and label encoding cannot drift from the tuning run); set up Git LFS and float16
  storage for the weights; built the demo app ([`app/`](../app/)) including the
  live OCR path, the explanation layer, and the desktop window; built the Chrome
  extension ([`extension/`](../extension/)); wrote the 183-test suite and the
  sample ad material.
  (evidence: commits
  [dba8527](https://github.com/cpedrett-umd/Group-6-Final-Project/commit/dba8527),
  [0bd0e20](https://github.com/cpedrett-umd/Group-6-Final-Project/commit/0bd0e20),
  [1240f29](https://github.com/cpedrett-umd/Group-6-Final-Project/commit/1240f29))
- **Ciara (Data&Eval):** Ran the Hyperopt TPE search over the DistilBERT training
  configuration, producing the
  [trial table](../modeling/hyperopt_results/hyperopt_trials.csv) and the
  [winning parameters](../modeling/hyperopt_results/best_parameters.txt) that
  [`train_best.py`](../modeling/train_best.py) now trains from.
  (evidence: commit
  [c18116b](https://github.com/cpedrett-umd/Group-6-Final-Project/commit/c18116b))
- **Jonathan (Product | Engineering | Data&Eval):** Finalized training of the
  baseline model that the hyperparameter search then tuned
  → [`train_baseline.py`](../modeling/train_baseline.py)
- **Shashank (Architecture | OCR | Agents):** - **Shashank (Architecture | OCR | Agents):** Assembled and hand-labelled the
  six-ad evaluation set; built the extraction comparison across RapidOCR,
  `app/ocr.py` and a vision-language model; built claim and query extraction for
  the review layer including the no-searchable-entity branch; specified the
  retrieval and source-independence design.

## Lean canvas changes (if any)

- No change to user, problem, or value proposition. One risk sharpened: the gap
between the synthetic training corpus and real advertising is now measured rather
than suspected. Extraction quality is no longer the limiting factor on the image
path; the training distribution is.
