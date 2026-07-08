# Ad Persuasion-Tactic Transformer

A from-scratch PyTorch transformer encoder that classifies ad text into the
persuasion tactics defined in the Group 6 final project
(`labeling_guidelines.md`): **urgency, scarcity, FOMO, fear appeal, social
proof, authority, exaggerated claim, neutral**.

This is the "Claim and Persuasion Analysis" model in the project's main
analysis stage — it consumes the unified extracted text produced by the input
processing layer (OCR / ASR / raw text) and emits per-tactic scores.

## Architecture

```
ad text ──► clean + tokenize ──► [CLS] w1 w2 ... wn <pad>...
                                        │
                          token embedding + position embedding   (B, T, 128)
                                        │
                          4 × pre-LN encoder block:
                              LayerNorm → multi-head self-attention (4 heads)
                              LayerNorm → FFN (128 → 512 → 128, GELU)
                              residual connections around both
                                        │
                          final LayerNorm, take [CLS] position    (B, 128)
                                        │
                          MLP head: 128 → 128 → 8                 (B, 8 logits)
                                        │
                          sigmoid per class (multi-label)
```

~1.5M parameters with a 20k vocab — trains in minutes on CPU for the ~7.7k-ad
dataset. No pretrained weights, so every component can be explained in the
report.

## Key design decisions

- **Multi-label, not multi-class.** The labeling guidelines state "ads may
  contain multiple labels" ("Act now, only 3 left" is urgency *and*
  scarcity). So the head outputs 8 independent sigmoid scores trained with
  `BCEWithLogitsLoss`, rather than a softmax that would force one winner.
- **Class-weighted loss.** Tactic frequencies will be skewed (lots of
  urgency/scarcity in scraped ad copy, less fear appeal). `pos_weight`
  up-weights rare classes so they aren't ignored.
- **[CLS] pooling.** A learned classification token is prepended to every
  sequence; after the encoder stack its hidden state summarizes the whole ad.
- **Pre-LayerNorm blocks.** More stable to train from scratch at small scale
  than the original post-LN arrangement.
- **Padding-aware attention.** Pad positions are masked to −∞ in the
  attention scores so short ads aren't polluted by padding.
- **Word-level tokenizer matching the repo's cleaning.** `tokenizer.clean_text`
  replicates the normalization in `datasets/text processing/main.py`, so the
  already-built `ads_dataset_full.csv` and raw user submissions tokenize
  identically. Vocab is built from the training split only.
- **Neutral fallback at inference.** If no tactic clears the 0.5 threshold,
  the ad is reported as neutral — matching the guideline that neutral means
  "no strong persuasive strategy is clearly present."

## Files

| File | Purpose |
|---|---|
| `tokenizer.py` | text cleaning, word tokenizer, vocab build/save/load |
| `dataset.py` | label parsing (handles `urgency\|scarcity`, `Fear Appeal, FOMO`, etc.), multi-hot targets |
| `model.py` | attention, encoder blocks, classifier — all from scratch |
| `train.py` | 80/10/10 split, AdamW + cosine schedule, early stopping on val macro-F1, per-class test report |
| `predict.py` | classify a single ad from a saved checkpoint |

## Usage

```bash
pip install -r requirements.txt

# after the dataset is annotated per labeling_guidelines.md:
python train.py --data "path/to/ads_dataset_labeled.csv"

python predict.py "Act now! Only 3 left — doctors recommend it."
```

The training CSV needs `ad_text` and `label` columns; multiple labels can be
separated by `|`, `,`, or `;`. Rows still carrying the placeholder label
`advertisement` from the dataset builder are skipped automatically.

## Current blocker: labels

`ads_dataset_full.csv` (7,768 ads) is entirely placeholder-labeled, so the
model can't be trained on it yet. Options, in increasing effort:

1. Weak labels: keyword rules from the guideline trigger phrases ("act now" →
   urgency, "only N left" → scarcity) to bootstrap, then hand-correct.
2. LLM-assisted annotation with human spot-checks against the guidelines.
3. Full manual annotation of a stratified subset (even ~1.5–2k ads is enough
   to fine-tune and evaluate meaningfully at this model size).

## Upgrade path

If from-scratch accuracy plateaus (likely with <10k labeled examples), the
same `dataset.py`/training-loop structure works with a pretrained encoder:
swap the model for `distilbert-base-uncased` + the same 8-way sigmoid head and
its tokenizer for `AutoTokenizer`. Expect a large F1 jump from transfer
learning; keep this from-scratch version as the report's baseline/ablation.
