"""Transformer encoder for multi-label persuasion-tactic classification.

Implemented from scratch (attention included) rather than with
nn.TransformerEncoder so every moving part of the architecture is
visible and explainable in the final report.

Shapes use B = batch, T = sequence length, D = d_model, H = heads.
"""
import math

import torch
import torch.nn as nn


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.out = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, pad_mask: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D); pad_mask: (B, T) bool, True at padding positions
        B, T, D = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)

        def heads(t: torch.Tensor) -> torch.Tensor:
            return t.view(B, T, self.n_heads, self.d_head).transpose(1, 2)  # (B, H, T, d_head)

        q, k, v = heads(q), heads(k), heads(v)
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_head)  # (B, H, T, T)
        scores = scores.masked_fill(pad_mask[:, None, None, :], float("-inf"))
        attn = self.dropout(torch.softmax(scores, dim=-1))
        ctx = (attn @ v).transpose(1, 2).reshape(B, T, D)
        return self.out(ctx)


class EncoderBlock(nn.Module):
    """Pre-LayerNorm block: more stable to train than post-LN at this scale."""

    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = MultiHeadSelfAttention(d_model, n_heads, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, pad_mask: torch.Tensor) -> torch.Tensor:
        x = x + self.dropout(self.attn(self.ln1(x), pad_mask))
        x = x + self.dropout(self.ff(self.ln2(x)))
        return x


class AdTransformerClassifier(nn.Module):
    """Encoder-only transformer; the [CLS] position summarizes the ad.

    Outputs raw logits, one per tactic class. Apply sigmoid (not softmax)
    at inference: an ad can use several tactics at once.
    """

    def __init__(
        self,
        vocab_size: int,
        n_classes: int,
        d_model: int = 128,
        n_heads: int = 4,
        n_layers: int = 4,
        d_ff: int = 512,
        max_len: int = 128,
        dropout: float = 0.1,
        pad_id: int = 0,
    ):
        super().__init__()
        self.pad_id = pad_id
        self.tok_emb = nn.Embedding(vocab_size, d_model, padding_idx=pad_id)
        self.pos_emb = nn.Embedding(max_len, d_model)
        self.emb_dropout = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(
            EncoderBlock(d_model, n_heads, d_ff, dropout) for _ in range(n_layers)
        )
        self.ln_final = nn.LayerNorm(d_model)
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, n_classes),
        )
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.trunc_normal_(module.weight, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.trunc_normal_(module.weight, std=0.02)

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        # ids: (B, T) with [CLS] at position 0
        pad_mask = ids == self.pad_id  # (B, T)
        positions = torch.arange(ids.size(1), device=ids.device)
        x = self.emb_dropout(self.tok_emb(ids) + self.pos_emb(positions))
        for block in self.blocks:
            x = block(x, pad_mask)
        cls = self.ln_final(x)[:, 0]  # (B, D)
        return self.head(cls)  # (B, n_classes) logits
