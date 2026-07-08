"""Word-level tokenizer and vocabulary for ad text.

Mirrors the cleaning already applied in the Group 6 repo
(datasets/text processing/main.py) so text preprocessed there and raw
text submitted at inference time land in the same token space.
"""
import json
import re
from collections import Counter

PAD, UNK, CLS = "<pad>", "<unk>", "<cls>"
PAD_ID, UNK_ID, CLS_ID = 0, 1, 2

_URL_RE = re.compile(r"http\S+|www\S+")
_CHARSET_RE = re.compile(r"[^a-z0-9\s.,!?$%\-]")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[.,!?$%\-]")


def clean_text(text: str) -> str:
    """Same normalization as the group repo's dataset builder."""
    text = str(text).lower()
    text = _URL_RE.sub("", text)
    text = _CHARSET_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(clean_text(text))


class Vocab:
    def __init__(self, itos: list[str]):
        self.itos = itos
        self.stoi = {tok: i for i, tok in enumerate(itos)}

    def __len__(self) -> int:
        return len(self.itos)

    @classmethod
    def build(cls, texts, min_freq: int = 2, max_size: int = 20000) -> "Vocab":
        counts = Counter(tok for t in texts for tok in tokenize(t))
        itos = [PAD, UNK, CLS]
        for tok, freq in counts.most_common(max_size - len(itos)):
            if freq < min_freq:
                break
            itos.append(tok)
        return cls(itos)

    def encode(self, text: str, max_len: int) -> list[int]:
        """Encode as [CLS] + tokens, truncated/padded to max_len."""
        ids = [CLS_ID]
        for tok in tokenize(text)[: max_len - 1]:
            ids.append(self.stoi.get(tok, UNK_ID))
        ids += [PAD_ID] * (max_len - len(ids))
        return ids

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.itos, f)

    @classmethod
    def load(cls, path: str) -> "Vocab":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))
