# modeling/ — tokenizer, classifier training, and evaluation studies

This directory holds the full modeling pipeline: the tokenizer that turns the
labeled ads dataset into fixed-width tensors, the DistilBERT training and
hyperparameter-tuning scripts, non-neural baselines, and the evaluation
notebooks. The shipped checkpoint lives in `hyperopt_results/best_distilbert_model/`
(Git LFS, float16) and is what `app/predict.py` serves.

## What's in here

| File | What it is |
|---|---|
| [hf_tokenizer.py](hf_tokenizer.py) | `AdsTokenizer` (wraps a HF `AutoTokenizer`) + the script that builds the artifacts below |
| [train_hyperopt.py](train_hyperopt.py) | Hyperopt TPE search (3 trials) + retrain-winner + held-out evaluation |
| [train_best.py](train_best.py) | Retrains just the winning config from `hyperopt_results/best_parameters.txt` |
| [train_baseline.py](train_baseline.py) | Default-hyperparameter DistilBERT fine-tune |
| [train_baselines.py](train_baselines.py) | Majority-class and TF-IDF + LogReg baselines on the same split (0.045 / 0.895 macro F1 vs 0.919 for the tuned model) |
| [compress_model.py](compress_model.py) | float32 → float16 weight compression before committing |
| [vlm_extraction.ipynb](vlm_extraction.ipynb) | OCR-vs-VLM extraction study on six real ads (inputs: see [data/README.md](data/README.md)) |
| [sentence_attribution.ipynb](sentence_attribution.ipynb) | Per-sentence classification study on a video-ad transcript |
| [occlusion_attribution.ipynb](occlusion_attribution.ipynb) | Leave-one-sentence-out attribution study |
| [requirements.txt](requirements.txt) | `torch`, `pandas`, `transformers` |

Generated artifacts (written to `../datasets/text_processing/`):

| Artifact | What it is |
|---|---|
| [tokenized_ads.pt](../datasets/text_processing/tokenized_ads.pt) | Pre-tokenized dataset, ready to load — see shapes below |
| [ads_tokenizer/](../datasets/text_processing/ads_tokenizer/) | Saved tokenizer files (`tokenizer.json`, `tokenizer_config.json`) so inference reuses the exact same vocab |

Base model: **`distilbert-base-uncased`**, `max_len=128`.

## Quickstart: load the artifact

```bash
pip install -r requirements.txt
```

```python
import torch
b = torch.load("../datasets/text_processing/tokenized_ads.pt", weights_only=False)

input_ids, attention_mask, labels = b["input_ids"], b["attention_mask"], b["labels"]
```

### Shapes / contents (current — the merged 8-class corpus)

```
>>> import torch; b = torch.load('../datasets/text_processing/tokenized_ads.pt', weights_only=False)
>>> b['input_ids'].shape, b['input_ids'].dtype
torch.Size([4374, 128]) torch.int64
>>> b['attention_mask'].shape, b['attention_mask'].dtype
torch.Size([4374, 128]) torch.int64
>>> len(b['labels']), type(b['labels'][0])
4374 <class 'str'>
```

Bundle keys:

- `input_ids` — `(4374, 128)` int64 tensor, padded/truncated to `max_len=128`
- `attention_mask` — `(4374, 128)` int64 tensor, same shape as `input_ids`
- `labels` — list of 4,374 raw label **strings** (the training scripts build their own label2id)
- `texts` — list of 4,374 original `ad_text` strings, aligned row-for-row with the tensors (useful for debugging/error analysis)
- `model_name` — `"distilbert-base-uncased"`
- `max_len` — `128`

Label distribution (8 classes, single-label per ad — from
`ads_dataset_merged.csv`):

```
Urgency                  959
Exaggerated Claims       905
Scarcity                 798
Social Proof             510
Authority Manipulation   389
Fear Appeals             304
Neutral                  287
FOMO                     222
```

Classes are imbalanced (~4.3x between largest and smallest); the training
scripts compensate with class-weighted cross-entropy and report macro F1.

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

tok = AdsTokenizer()  # or AdsTokenizer.from_pretrained("../datasets/text_processing/ads_tokenizer")
texts, labels = load_ads("../datasets/text_processing/ads_dataset_labeled.csv")
ds = AdsHFDataset(texts, labels, tok)
inputs, label = ds[0]  # inputs = {"input_ids": ..., "attention_mask": ...}
```

## Regenerating the artifacts

If the dataset changes, rebuild both the tensors and the saved tokenizer.
**Note:** the script's `--data` default still points at the original
`ads_dataset_labeled.csv` (3,230 rows, 7 classes); the committed artifacts were
built from the merged corpus, so pass it explicitly:

```bash
python hf_tokenizer.py --data "../datasets/text_processing/ads_dataset_merged.csv"
```

Equivalent to spelling out the defaults:

```bash
python hf_tokenizer.py \
    --data "../datasets/text_processing/ads_dataset_labeled.csv" \
    --out-tensors "../datasets/text_processing/tokenized_ads.pt" \
    --out-tokenizer "../datasets/text_processing/ads_tokenizer"
```

This prints a profile (subword length percentiles, a sample tokenization) so
you can sanity-check whether `--max-len 128` is still generous enough before
saving.

## Notes

- **Labels are strings, not ints.** Build your own label2id mapping (the 8
  classes are listed above); nothing here assumes an encoding.
- **Tokenizer is swappable.** Everything in `hf_tokenizer.py` works with any
  `AutoTokenizer`-compatible checkpoint — pass `--model bert-base-uncased` (or
  similar) and re-run if you want a different base model. Just make sure the
  base model you train against matches the tokenizer that produced
  `tokenized_ads.pt` (mismatched vocab = garbage ids).
- **No train/val/test split yet** — `tokenized_ads.pt` is the full dataset in
  original row order, aligned across `input_ids` / `attention_mask` /
  `labels` / `texts`. Split before training.
