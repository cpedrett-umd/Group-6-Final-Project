"""Subword tokenizer for the ads dataset, built on a pretrained base model.

Wraps a HuggingFace ``AutoTokenizer`` (DistilBERT by default) so ad text can
be fed straight into a pretrained transformer. This reuses the base model's
own subword vocabulary — the only tokenization a pretrained ``AutoModel`` will
accept, since its embedding table is indexed by that exact vocabulary.

Why subword over word2vec for a "base NLP model": a pretrained transformer
already ships contextual embeddings that beat static word2vec vectors on small
datasets like this one (~3k ads), and it *requires* its paired subword
tokenizer — you cannot hand it word2vec ids. So the most applicable tokenizer
for passing to a base NLP model is the model's own subword tokenizer.

This module is intentionally label-agnostic: model development and the label
scheme are handled by other devs. It turns the ``ad_text`` column into
``input_ids`` / ``attention_mask`` tensors and carries the ``label`` column
through untouched, so downstream code is free to encode labels however it
wants.

Usage (as a library):
    from hf_tokenizer import AdsTokenizer
    tok = AdsTokenizer()                     # distilbert-base-uncased
    enc = tok(["act now, only 3 left!"])     # dict of (N, T) tensors
    # enc["input_ids"], enc["attention_mask"] -> feed to AutoModel(**enc)

Usage (as a script) — tokenize the dataset and save the artifact:
    python hf_tokenizer.py \
        --data "../datasets/text_processing/ads_dataset_labeled.csv" \
        --out-tensors tokenized_ads.pt \
        --out-tokenizer ads_tokenizer
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import torch
from torch.utils.data import Dataset

# DistilBERT: a compact BERT (66M params) whose uncased subword vocab suits the
# already-lowercased ad text. Swap for "bert-base-uncased", "roberta-base",
# etc. — everything here works with any AutoTokenizer-compatible checkpoint.
DEFAULT_MODEL = "distilbert-base-uncased"
DEFAULT_MAX_LEN = 128

TEXT_COLUMN = "ad_text"
LABEL_COLUMN = "label"


class AdsTokenizer:
    """Thin wrapper over a pretrained ``AutoTokenizer`` for ad text.

    The base model's tokenizer already handles lowercasing, subword splitting,
    and the special tokens ([CLS]/[SEP]) it was pretrained with, so no manual
    cleaning is applied here — feeding it the raw ad text is what keeps it in
    the same token space the base model expects.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, max_len: int = DEFAULT_MAX_LEN):
        # Imported lazily so importing this module doesn't require transformers
        # until a tokenizer is actually constructed.
        from transformers import AutoTokenizer

        self.model_name = model_name
        self.max_len = max_len
        self._tok = AutoTokenizer.from_pretrained(model_name)

    @property
    def pad_token_id(self) -> int:
        return self._tok.pad_token_id

    @property
    def vocab_size(self) -> int:
        return self._tok.vocab_size

    def encode(self, texts, padding="max_length") -> dict[str, torch.Tensor]:
        """Tokenize a string or list of strings to batched tensors.

        Returns a dict with ``input_ids`` and ``attention_mask``, each shaped
        (N, T). ``padding="max_length"`` gives fixed-width T=max_len tensors so
        a plain DataLoader can collate them; pass ``padding="longest"`` for
        dynamic per-batch padding (use with a ``collate_fn``, more efficient).
        """
        if isinstance(texts, str):
            texts = [texts]
        return self._tok(
            list(texts),
            padding=padding,
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )

    # Callable sugar: tok(text) == tok.encode(text)
    __call__ = encode

    def convert_ids_to_tokens(self, ids) -> list[str]:
        """Inspect how a piece of text was split into subwords (debugging)."""
        if torch.is_tensor(ids):
            ids = ids.tolist()
        return self._tok.convert_ids_to_tokens(ids)

    def save(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        self._tok.save_pretrained(directory)

    @classmethod
    def from_pretrained(cls, directory: str, max_len: int = DEFAULT_MAX_LEN) -> "AdsTokenizer":
        return cls(model_name=directory, max_len=max_len)


class AdsHFDataset(Dataset):
    """Tokenized ad texts + their raw label strings, ready for a base model.

    Each item is ``(inputs, label)`` where ``inputs`` is a dict of
    ``input_ids``/``attention_mask`` (1-D, length max_len) that unpacks
    straight into ``AutoModel(**inputs)``, and ``label`` is the untouched
    string from the CSV. Encoding those label strings into targets is left to
    the model devs.
    """

    def __init__(self, texts, labels, tokenizer: AdsTokenizer):
        self.tokenizer = tokenizer
        self.texts = list(texts)
        self.labels = list(labels)
        enc = tokenizer.encode(self.texts)  # (N, T) fixed-width
        self.input_ids = enc["input_ids"]
        self.attention_mask = enc["attention_mask"]

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, i: int):
        inputs = {
            "input_ids": self.input_ids[i],
            "attention_mask": self.attention_mask[i],
        }
        return inputs, self.labels[i]


def load_ads(csv_path: str) -> tuple[list[str], list[str]]:
    """Read (ad_text, label) columns from the dataset CSV."""
    df = pd.read_csv(csv_path)
    missing = {TEXT_COLUMN, LABEL_COLUMN} - set(df.columns)
    if missing:
        raise ValueError(f"CSV {csv_path!r} is missing column(s): {sorted(missing)}")
    df = df.dropna(subset=[TEXT_COLUMN])
    return df[TEXT_COLUMN].astype(str).tolist(), df[LABEL_COLUMN].astype(str).tolist()


def tokenize_dataset(csv_path: str, tokenizer: AdsTokenizer) -> dict:
    """Tokenize the whole dataset into fixed-width tensors + carried labels.

    Returns a dict ready to ``torch.save``: ``input_ids`` and
    ``attention_mask`` are (N, max_len) tensors aligned row-for-row with the
    ``labels`` list and the original ``texts``.
    """
    texts, labels = load_ads(csv_path)
    enc = tokenizer.encode(texts)  # padding="max_length"
    return {
        "input_ids": enc["input_ids"],
        "attention_mask": enc["attention_mask"],
        "labels": labels,
        "texts": texts,
        "model_name": tokenizer.model_name,
        "max_len": tokenizer.max_len,
    }


def _print_profile(bundle: dict, tokenizer: AdsTokenizer) -> None:
    """Report subword-length stats + a sample split, to sanity-check max_len."""
    texts, labels = bundle["texts"], bundle["labels"]
    # Real token counts (no padding/truncation) to see if max_len is generous.
    raw = tokenizer._tok(texts, padding=False, truncation=False)["input_ids"]
    lengths = sorted(len(ids) for ids in raw)
    n = len(lengths)
    pct = lambda p: lengths[min(n - 1, int(p * n))]

    print(f"model:            {tokenizer.model_name}")
    print(f"vocab size:       {tokenizer.vocab_size:,}")
    print(f"ads tokenized:    {n:,}")
    print(f"tensor shape:     {tuple(bundle['input_ids'].shape)}  (rows x max_len)")
    print("\nsubword length per ad (incl. [CLS]/[SEP]):")
    print(f"  min / median / max:  {lengths[0]} / {pct(0.50)} / {lengths[-1]}")
    print(f"  90th / 95th / 99th:  {pct(0.90)} / {pct(0.95)} / {pct(0.99)}")
    within = sum(l <= tokenizer.max_len for l in lengths) / n
    print(f"  ads within max_len={tokenizer.max_len}: {within:.1%}")

    print("\nsample tokenization:")
    print(f"  text:   {texts[0][:88]}{'...' if len(texts[0]) > 88 else ''}")
    print(f"  label:  {labels[0]}")
    print(f"  tokens: {tokenizer.convert_ids_to_tokens(bundle['input_ids'][0])[:22]} ...")


def main() -> None:
    here = os.path.dirname(__file__)
    parser = argparse.ArgumentParser(description="Tokenize the ads dataset.")
    parser.add_argument(
        "--data",
        default=os.path.join(here, "..", "datasets", "text_processing", "ads_dataset_labeled.csv"),
        help="input CSV with ad_text,label columns",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="base model / tokenizer name")
    parser.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    parser.add_argument(
        "--out-tensors",
        default=os.path.join(here, "tokenized_ads.pt"),
        help="where to save the tokenized tensors (.pt)",
    )
    parser.add_argument(
        "--out-tokenizer",
        default=os.path.join(here, "ads_tokenizer"),
        help="directory to save the tokenizer files (for reuse at inference)",
    )
    args = parser.parse_args()

    tokenizer = AdsTokenizer(model_name=args.model, max_len=args.max_len)
    bundle = tokenize_dataset(args.data, tokenizer)
    _print_profile(bundle, tokenizer)

    torch.save(bundle, args.out_tensors)
    tokenizer.save(args.out_tokenizer)
    print(f"\nsaved tensors    -> {args.out_tensors}")
    print(f"saved tokenizer  -> {args.out_tokenizer}")
    print("\nload downstream with:")
    print(f'  bundle = torch.load("{os.path.basename(args.out_tensors)}", weights_only=False)')
    print("  input_ids, attention_mask, labels = "
          "bundle['input_ids'], bundle['attention_mask'], bundle['labels']")


if __name__ == "__main__":
    main()
