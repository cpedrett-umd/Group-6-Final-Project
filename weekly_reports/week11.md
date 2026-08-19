---
team: AdInsight
week: 11
date: 2026-08-19
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

- **Final written report.** Assembled and edited to the five rubric areas.
  → [`AdInsight_Final_Report.pdf`](../docs/AdInsight_Final_Report.pdf) /
  [`.docx`](../docs/AdInsight_Final_Report.docx)
- **Final presentation deck.** Eleven slides, one per rubric area, with speaker
  notes and per-slide timings for the live demo.
  → [`AdInsight_Final_Presentation.pptx`](../docs/AdInsight_Final_Presentation.pptx) /
  [`.pdf`](../docs/AdInsight_Final_Presentation.pdf)
- **Removed the review-insight layer.** Its retrieval was not returning reliable
  results and there was no time to fix it before the final demo, so it was cut
  from the app and the extension rather than shipped broken. The report, deck
  and READMEs were updated to say it was prototyped but not shipped.
  (evidence: commit
  [684caa9](https://github.com/cpedrett-umd/Group-6-Final-Project/commit/684caa9))

No model or data work this week — the build was frozen after week 10, and apart
from the removal above the whole week went to the deliverables.

## User / validation learning

- Nothing new this week. The report and deck write up the six-user study from
  week 10; no additional sessions were run.

## Metrics snapshot

- F1 Macro (8 classes): 0.9191 (was 0.9191 — no retrain this week)

## Challenges / blockers

- None outstanding. The remaining work was writing and editing, not engineering.

## Next week's goal

- Final presentation and submission — the course ends this week.

## Individual contributions

- **Ciara (Data&Eval):** Report and presentation.
- **Chris (Engineering | Data&Eval):** Report and presentation.
- **Jonathan (Product | Engineering | Data&Eval):** Report and presentation.

## Lean canvas changes (if any)

- No change this week.
