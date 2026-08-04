# samples/ — test material

Ads for exercising both input paths, with the results they actually produce.
Every figure below was measured against the committed model, not estimated.

| File | Use |
|---|---|
| [ad_texts.md](ad_texts.md) | Nine ad texts to copy-paste — one per tactic, plus a multi-tactic and a clean one |
| `images/` | Four ad screenshots for the OCR path |
| [make_images.py](make_images.py) | Regenerates the screenshots (they are committed; this is only for changing them) |

## Text results

Paste each into **Paste ad text**. "Model pick" is the classifier; "tactics
shown" is what the panel lists, which merges the model's pick with trigger
phrases found in the words themselves.

| Sample | Model pick | Confidence | Tactics shown |
|---|---|---|---|
| Urgency | Urgency | 94.4% | Urgency |
| Scarcity | **FOMO** | 99.1% | FOMO, Scarcity |
| FOMO | FOMO | 99.1% | FOMO |
| Fear appeal | Fear Appeals | 98.6% | Fear, Urgency |
| Social proof | Social Proof | 97.8% | Social proof |
| Authority | Authority Manipulation | 98.0% | Authority |
| Exaggerated claims | Exaggerated Claims | 85.7% | Big claim |
| Several at once | Authority Manipulation | 89.6% | Authority, Urgency, Fear, Big claim, Scarcity |
| Clean ad | **Social Proof** | 75.8% | **Social proof** ← wrong, see below |

## Image results

Upload each from `images/`. OCR confidence is RapidOCR's own score.

| File | OCR | Spacing repaired | Tactics shown |
|---|---|---|---|
| `supplement_ad.png` | 98.2% | yes | Social proof, Big claim, Authority, Scarcity, Fear, Urgency |
| `flash_sale_ad.png` | 97.2% | yes | FOMO, Scarcity, Urgency |
| `home_security_ad.png` | 97.3% | yes | Fear, Authority, Urgency |
| `bakery_ad.png` | 97.8% | no | Urgency ← wrong, see below |

`flash_sale_ad.png` is white-on-dark and `home_security_ad.png` uses tighter
type, so they exercise harder OCR than a clean black-on-white render.

## Two things these samples deliberately expose

**The classifier cannot say "this ad is fine."** `ads_dataset_labeled.csv` has
no `Neutral` rows, so softmax must put its mass on one of the seven tactics.
The bakery ad is genuinely clean, and the model still calls it Social Proof at
75.8% (text) or Urgency at 86.6% (image) — confidently, with no trigger phrase
anywhere in it.

The low-confidence guard in `app/tactics.py` suppresses this only below 0.60,
so these get through and are reported as findings. Raising the threshold is not
the fix: it would also suppress correct single-tactic detections scoring in the
70s. **The fix is dataset-side — add Neutral examples and retrain.** Until then,
expect false alarms on clean ads, and say so when demoing.

**The two signals cover each other.** The Scarcity sample is a good case: the
model confidently calls it FOMO (99.1%) and is wrong, but "Only 3 bottles left",
"Limited supply", and "while supplies last" all match the guidelines lexicon, so
Scarcity still appears in the panel. Neither signal alone would have produced
the right answer.

## Regenerating the images

```bash
python samples/make_images.py
```
