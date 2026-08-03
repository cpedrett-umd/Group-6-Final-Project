---
team: AdInsight
week: 1
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
  value: 86%
  previous: N/A
---

## Shipped this week
- Used the tokenized ads for training of a DistilBert-based classification model specializing in persuasion tactic detection with quantifiable performance metrics


## User / validation learning
- <update>

## Metrics snapshot
- Labeled ads tokenized: ~3,230 rows (was 0)

## Challenges / blockers
- None this week

## Next week's goal
- Define and train the baseline NLP model against the tokenized dataset

## Individual contributions
- Chris (Engineering | Data&Eval): Wrote `hf_tokenizer.py` (HuggingFace DistilBERT-based `AdsTokenizer`), removed the old custom dataset/tokenizer/model pipeline in favor of it, and tokenized `ads_dataset_labeled.csv`, saving the tensors to `tokenized_ads.pt` and the tokenizer to `ads_tokenizer/`. (evidence: commit 845a68a)
- Ciara (Data&Eval): <update>
- Jonathan (Product | Engineering | Data&Eval): Finalized training of baseline model to be further hyperparameter tuned

## Lean canvas changes (if any)
- <update>
