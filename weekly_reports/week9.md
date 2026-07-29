---
team: AdInsight
week: 9
date: 2026-07-22
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
  metric: task success rate
  value: 100%
  previous: 100%
---

## Shipped this week
- Built `AdsTokenizer`, a standalone HuggingFace (DistilBERT-base-uncased) tokenizer wrapper in `modeling/hf_tokenizer.py`, replacing the earlier custom dataset/tokenizer/model/train/predict scripts (commit 845a68a)
- Tokenized the full labeled ad dataset (~3,230 rows in `ads_dataset_labeled.csv`) into fixed-width `input_ids`/`attention_mask` tensors, saving them to `modeling/tokenized_ads.pt` and the fitted tokenizer to `modeling/ads_tokenizer/`

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
- Jonathan (Product | Engineering | Data&Eval): Experimenting with tokenized inputs in training of the baseline model

## Lean canvas changes (if any)
- <update>
