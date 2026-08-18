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
| Urgency | Urgency | 92.8% | Urgency |
| Scarcity | **FOMO** | 98.5% | FOMO, Scarcity |
| FOMO | FOMO | 99.0% | FOMO |
| Fear appeal | Fear Appeals | 99.4% | Fear, Urgency |
| Social proof | **Exaggerated Claims** | 69.9% | Big claim, Social proof |
| Authority | Authority Manipulation | 98.0% | Authority |
| Exaggerated claims | **Scarcity** | 44.7% (suppressed) | Big claim |
| Several at once | Authority Manipulation | 87.7% | Authority, Fear, Urgency, Big claim, Scarcity |
| Clean ad | Neutral | 99.6% | *(none — no false alarm)* |

## Image results

Upload each from `images/`. OCR confidence is RapidOCR's own score.

| File | OCR | Spacing repaired | Model pick | Tactics shown |
|---|---|---|---|---|
| `supplement_ad.png` | 98.2% | yes | Authority Manipulation 53.6% | Authority, Social proof, Urgency, Fear, Big claim, Scarcity |
| `flash_sale_ad.png` | 97.2% | yes | FOMO 98.2% | FOMO, Scarcity, Urgency |
| `home_security_ad.png` | 97.3% | yes | Fear Appeals 99.4% | Fear, Authority, Urgency |
| `bakery_ad.png` | 97.8% | no | Neutral 99.6% | *(none — no false alarm)* |

`flash_sale_ad.png` is white-on-dark and `home_security_ad.png` uses tighter
type, so they exercise harder OCR than a clean black-on-white render.

## Two things these samples deliberately expose

**The clean ads now come back Neutral.** Under the earlier 7-class model the
bakery ad was a confident false alarm (75.8% Social Proof); after the dataset
rebuild added a Neutral class, both the pasted clean ad and `bakery_ad.png`
classify Neutral at 99.6% with no findings shown. Keep them in every demo —
"try to fool it" is the beat audiences remember.

**The two signals cover each other.** Three samples show it. The Scarcity
sample: the model confidently says FOMO (98.5%) and is wrong, but "Only 3
bottles left" and "while supplies last" match the guidelines lexicon, so
Scarcity still appears. The Social-proof sample: the model picks Exaggerated
Claims, but "Trusted by millions" and "best seller" surface Social proof via
phrases. The Exaggerated-claims sample: the model's pick (Scarcity, 44.7%)
falls below the 0.60 guard and is suppressed as "not sure" — but the phrase
lexicon still shows Big claim. Neither signal alone would produce the right
panel; together they do.

## Regenerating the images

```bash
python samples/make_images.py
```
