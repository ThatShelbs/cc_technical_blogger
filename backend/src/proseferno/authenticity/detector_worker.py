"""Score text with two open AI-text detector models, on the CPU.

Run on its own, never imported by the app: ``local_detector.UvDetector`` starts it with
``uv run --no-project --with torch --with transformers python -I detector_worker.py`` so the heavy packages live in
uv's cache, not in the app's environment. Standard library only at import time. Reads JSON on stdin, writes JSON on
stdout.

Input::

    {"zero_shot": "openai-community/gpt2", "classifier": "<hf id>", "warmup": false,
     "texts": [{"sentences": ["...", ...], "paragraphs": ["...", ...]}, ...]}

Output::

    {"results": [{"curvature": {"score": float | null, "sentences": [float | null, ...]},
                  "classifier": {"score": float | null, "paragraphs": [float | null, ...]}}, ...]}

*Zero-shot* is Fast-DetectGPT in its analytic form: for each token the language model gives log p(token) and the mean
and variance of log p under its own distribution. (sum of log p - mean) / sqrt(sum of variance) is high when the text
is what the model would have written (machine texture) and near zero or below for human prose.

*Classifier* is a sequence classifier trained to tell human from AI text; its score is the probability of the AI
label, per paragraph and word-weighted over the post.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

WINDOW = 1024
STRIDE = 896  # windows overlap so every scored token has context
AI_LABEL_WORDS = ("ai", "fake", "machine", "generat", "gpt", "llm", "label_1")


def _criterion(stats: list[tuple[float, float, float]]) -> float | None:
    if len(stats) < 4:
        return None
    total = sum(lp - mean for lp, mean, _ in stats)
    var = sum(v for _, _, v in stats)
    return total / math.sqrt(var) if var > 0 else None


def _token_stats(torch: Any, model: Any, ids: list[int]) -> list[tuple[float, float, float]]:
    """(log p, mean, variance) for every token; the first token has no context and gets zeros."""
    out: list[tuple[float, float, float] | None] = [None] * len(ids)
    start = 0
    while True:
        chunk = ids[start : start + WINDOW]
        with torch.no_grad():
            logits = model(torch.tensor([chunk])).logits[0, :-1].float()
        log_probs = torch.log_softmax(logits, dim=-1)
        probs = log_probs.exp()
        target = torch.tensor(chunk[1:]).unsqueeze(-1)
        lp = log_probs.gather(-1, target).squeeze(-1)
        mean = (probs * log_probs).sum(-1)
        var = (probs * log_probs.square()).sum(-1) - mean.square()
        first = 0 if start == 0 else WINDOW - STRIDE - 1
        for j in range(first, len(chunk) - 1):
            out[start + j + 1] = (float(lp[j]), float(mean[j]), float(var[j]))
        if start + WINDOW >= len(ids):
            break
        start += STRIDE
    return [s if s is not None else (0.0, 0.0, 0.0) for s in out]


def join_spans(parts: list[str]) -> tuple[str, list[tuple[int, int]]]:
    """Join parts with single spaces; return the text and each part's (start, end) character span."""
    text = ""
    spans: list[tuple[int, int]] = []
    for part in parts:
        if text:
            text += " "
        spans.append((len(text), len(text) + len(part)))
        text += part
    return text, spans


def assign_tokens(offsets: list[tuple[int, int]], spans: list[tuple[int, int]]) -> list[list[int]]:
    """Token indexes (from 1: the first token is never scored) that start inside each span."""
    groups: list[list[int]] = [[] for _ in spans]
    span = 0
    for token in range(1, len(offsets)):
        begin = offsets[token][0]
        while span < len(spans) and begin >= spans[span][1]:
            span += 1
        if span >= len(spans):
            break
        if begin >= spans[span][0]:
            groups[span].append(token)
    return groups


def curvature(torch: Any, tokenizer: Any, model: Any, sentences: list[str]) -> dict[str, Any]:
    text, spans = join_spans(sentences)
    empty = {"score": None, "sentences": [None] * len(sentences)}
    if not text.strip():
        return empty
    encoded = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
    ids: list[int] = list(encoded["input_ids"])
    offsets = [tuple(o) for o in encoded["offset_mapping"]]
    if len(ids) < 5:
        return empty
    stats = _token_stats(torch, model, ids)
    groups = assign_tokens(offsets, spans)  # type: ignore[arg-type]
    return {"score": _criterion(stats[1:]), "sentences": [_criterion([stats[t] for t in g]) for g in groups]}


HUMAN_LABELS = ("human", "real", "label_0", "0", "human-written", "human_written")


def ai_label_index(labels: dict[int, str]) -> int:
    """Which output is "AI": the first label that names it, else the last one."""
    for index, label in sorted(labels.items()):
        name = str(label).lower()
        if name not in HUMAN_LABELS and any(word in name for word in AI_LABEL_WORDS):
            return int(index)
    return max(labels) if labels else 1


def classify(torch: Any, tokenizer: Any, model: Any, paragraphs: list[str]) -> dict[str, Any]:
    if not paragraphs:
        return {"score": None, "paragraphs": []}
    ai = ai_label_index(dict(model.config.id2label or {}))
    probs: list[float | None] = []
    for paragraph in paragraphs:
        if len(paragraph.split()) < 8:
            probs.append(None)
            continue
        inputs = tokenizer(paragraph, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = model(**inputs).logits[0].float()
        probs.append(float(torch.softmax(logits, dim=-1)[ai]))
    weights = [(p, len(text.split())) for p, text in zip(probs, paragraphs, strict=True) if p is not None]
    total = sum(w for _, w in weights)
    return {"score": sum(p * w for p, w in weights) / total if total else None, "paragraphs": probs}


class Models:
    """The loaded models, kept between requests in serve mode (reloaded only when a request names others)."""

    def __init__(self) -> None:
        import torch

        self.torch = torch
        self.loaded: dict[str, tuple[str, Any, Any]] = {}

    def get(self, kind: str, name: str | None) -> tuple[Any, Any] | None:
        if not name:
            return None
        current = self.loaded.get(kind)
        if current is None or current[0] != name:
            from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

            auto = AutoModelForCausalLM if kind == "zero_shot" else AutoModelForSequenceClassification
            self.loaded[kind] = (name, AutoTokenizer.from_pretrained(name), auto.from_pretrained(name).eval())
        _, tokenizer, model = self.loaded[kind]
        return tokenizer, model

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        zero_shot = self.get("zero_shot", request.get("zero_shot"))
        classifier = self.get("classifier", request.get("classifier"))
        if request.get("warmup"):
            return {"ready": True, "torch": self.torch.__version__, "models": sorted(self.loaded)}
        results = []
        for item in request.get("texts", []):
            result: dict[str, Any] = {}
            if zero_shot is not None:
                result["curvature"] = curvature(self.torch, *zero_shot, [str(s) for s in item.get("sentences", [])])
            if classifier is not None:
                result["classifier"] = classify(self.torch, *classifier, [str(p) for p in item.get("paragraphs", [])])
            results.append(result)
        return {"results": results}


def main() -> int:
    """One request on stdin, or with ``--serve`` one JSON request per line, each answered with one JSON line."""
    stdin = open(sys.stdin.fileno(), encoding="utf-8", closefd=False)  # noqa: SIM115
    models = Models()
    if "--serve" not in sys.argv:
        sys.stdout.write(json.dumps(models.handle(json.loads(stdin.read() or "{}"))))
        return 0
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()
    for line in stdin:
        if not line.strip():
            continue
        try:
            reply = models.handle(json.loads(line))
        except Exception as exc:  # noqa: BLE001 - report and keep serving
            reply = {"error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
