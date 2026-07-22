# modeling/ — tokenizer

This directory is **tokenizer-only**. It turns the labeled ads dataset into
fixed-width tensors a pretrained transformer (`AutoModel`) can consume
directly. Model architecture, training loop, and label encoding are **not**
implemented here — that's the next step, owned by the model dev(s).

## What's in here

| File | What it is |
|---|---|
| [hf_tokenizer.py](hf_tokenizer.py) | `AdsTokenizer` (wraps a HF `AutoTokenizer`) + the script that builds the artifacts below |
| [tokenized_ads.pt](tokenized_ads.pt) | Pre-tokenized dataset, ready to load — see shapes below |
| [ads_tokenizer/](ads_tokenizer/) | Saved tokenizer files (`tokenizer.json`, `tokenizer_config.json`) so inference reuses the exact same vocab |
| [requirements.txt](requirements.txt) | `torch`, `pandas`, `transformers` |

Base model: **`distilbert-base-uncased`**, `max_len=128`.

## Quickstart: load the artifact

```bash
pip install -r requirements.txt
```

```python
import torch
b = torch.load("tokenized_ads.pt", weights_only=False)

input_ids, attention_mask, labels = b["input_ids"], b["attention_mask"], b["labels"]
```

### Shapes / contents (as of this handoff)

```
>>> import torch; b = torch.load('tokenized_ads.pt', weights_only=False)
>>> b['input_ids'].shape, b['input_ids'].dtype
torch.Size([3230, 128]) torch.int64
>>> b['attention_mask'].shape, b['attention_mask'].dtype
torch.Size([3230, 128]) torch.int64
>>> len(b['labels']), type(b['labels'][0])
3230 <class 'str'>
```

Bundle keys:

- `input_ids` — `(3230, 128)` int64 tensor, padded/truncated to `max_len=128`
- `attention_mask` — `(3230, 128)` int64 tensor, same shape as `input_ids`
- `labels` — list of 3230 raw label **strings** (untouched from the CSV — not yet encoded to ints/one-hot, that's on the model side)
- `texts` — list of 3230 original `ad_text` strings, aligned row-for-row with the tensors (useful for debugging/error analysis)
- `model_name` — `"distilbert-base-uncased"`
- `max_len` — `128`

Label distribution (7 classes, single-label per ad):

```
Exaggerated Claims       905
Urgency                  763
Scarcity                 449
Authority Manipulation   389
Fear Appeals             304
FOMO                     222
Social Proof             198
```

Classes are imbalanced (~4.6x between largest and smallest) — worth
accounting for in the loss (e.g. class weighting) or eval metrics (macro F1
over accuracy).

## Feeding a batch into a model

```python
from transformers import AutoModel

model = AutoModel.from_pretrained("distilbert-base-uncased")
out = model(input_ids=input_ids[:8], attention_mask=attention_mask[:8])
# out.last_hidden_state: (8, 128, 768) — feed [:, 0] (the [CLS] token) or a
# pooled representation into your classification head.
```

`AdsTokenizer` / `AdsHFDataset` in [hf_tokenizer.py](hf_tokenizer.py) are also
importable directly if you'd rather tokenize on the fly (e.g. for a
train/val/test split) instead of using the pre-baked `.pt` bundle:

```python
from hf_tokenizer import AdsTokenizer, AdsHFDataset, load_ads

tok = AdsTokenizer()  # or AdsTokenizer.from_pretrained("ads_tokenizer")
texts, labels = load_ads("../datasets/text_processing/ads_dataset_labeled.csv")
ds = AdsHFDataset(texts, labels, tok)
inputs, label = ds[0]  # inputs = {"input_ids": ..., "attention_mask": ...}
```

## Regenerating the artifacts

If the dataset changes, rebuild both the tensors and the saved tokenizer:

```bash
python hf_tokenizer.py \
    --data "../datasets/text_processing/ads_dataset_labeled.csv" \
    --out-tensors tokenized_ads.pt \
    --out-tokenizer ads_tokenizer
```

This prints a profile (subword length percentiles, a sample tokenization) so
you can sanity-check whether `--max-len 128` is still generous enough before
saving.

## Notes for whoever picks up model dev

- **Labels are strings, not ints.** Build your own label2id mapping (the 7
  classes are listed above); nothing here assumes an encoding.
- **Tokenizer is swappable.** Everything in `hf_tokenizer.py` works with any
  `AutoTokenizer`-compatible checkpoint — pass `--model bert-base-uncased` (or
  similar) and re-run if you want a different base model. Just make sure the
  base model you train against matches the tokenizer that produced
  `tokenized_ads.pt` (mismatched vocab = garbage ids).
- **No train/val/test split yet** — `tokenized_ads.pt` is the full dataset in
  original row order, aligned across `input_ids` / `attention_mask` /
  `labels` / `texts`. Split before training.
