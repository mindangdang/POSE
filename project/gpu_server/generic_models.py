from __future__ import annotations

import os
import threading
from typing import Any

from project.backend.app.manage.settings import get_settings


_settings = get_settings()
EMBEDDING_MODEL_ID = _settings.embedding_model
RERANKER_MODEL_ID = _settings.reranker_model
MAX_EMBEDDING_LENGTH = min(max(int(os.getenv("POSE_EMBEDDING_MAX_LENGTH", "2048")), 64), 8192)


class GenericModelRegistry:
    """Lazy text embedding and cross-encoder models; legacy SigLIP remains separate."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._embedding: tuple[Any, Any, Any, str] | None = None
        self._reranker: tuple[Any, Any, Any, str] | None = None

    @staticmethod
    def _device(torch: Any) -> str:
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(getattr(torch.backends, "mps", None), "is_available", None)
        return "mps" if mps and mps() else "cpu"

    def _load_embedding(self) -> tuple[Any, Any, Any, str]:
        with self._lock:
            if self._embedding is None:
                import torch
                from transformers import AutoModel, AutoTokenizer

                device = self._device(torch)
                tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_ID)
                model = AutoModel.from_pretrained(EMBEDDING_MODEL_ID)
                model.to(device).eval()
                self._embedding = (torch, tokenizer, model, device)
            return self._embedding

    def _load_reranker(self) -> tuple[Any, Any, Any, str]:
        with self._lock:
            if self._reranker is None:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                device = self._device(torch)
                tokenizer = AutoTokenizer.from_pretrained(RERANKER_MODEL_ID)
                model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL_ID)
                model.to(device).eval()
                self._reranker = (torch, tokenizer, model, device)
            return self._reranker

    def embed(self, texts: list[str], normalize: bool = True) -> tuple[list[list[float]], str]:
        torch, tokenizer, model, device = self._load_embedding()
        if not texts:
            return [], device
        results: list[list[float]] = []
        for start in range(0, len(texts), 8):
            encoded = tokenizer(
                texts[start : start + 8],
                padding=True,
                truncation=True,
                max_length=MAX_EMBEDDING_LENGTH,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                output = model(**encoded)
                hidden = output.last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                vectors = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                if normalize:
                    vectors = torch.nn.functional.normalize(vectors, p=2, dim=1)
            results.extend(vectors.float().cpu().tolist())
        return results, device

    def rerank(self, query: str, documents: list[dict[str, str]]) -> tuple[list[dict], str]:
        torch, tokenizer, model, device = self._load_reranker()
        if not documents:
            return [], device
        results = []
        batch_size = 8
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            encoded = tokenizer(
                [query] * len(batch),
                [item["text"] for item in batch],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                logits = model(**encoded).logits.reshape(-1).float().cpu().tolist()
            results.extend(
                {"id": item["id"], "raw_score": float(score)}
                for item, score in zip(batch, logits)
            )
        results.sort(key=lambda item: item["raw_score"], reverse=True)
        return results, device

    def status(self) -> dict[str, Any]:
        return {
            "embedding_model": EMBEDDING_MODEL_ID,
            "reranker_model": RERANKER_MODEL_ID,
            "embedding_loaded": self._embedding is not None,
            "reranker_loaded": self._reranker is not None,
        }


generic_models = GenericModelRegistry()
