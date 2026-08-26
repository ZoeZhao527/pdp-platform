"""向量化：优先 Ollama 本地模型，失败时回退本地哈希向量。"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


def _ollama_embed_batch(client: httpx.Client, texts: list[str]) -> list[list[float]] | None:
    settings = get_settings()
    url = f"{settings.embedding_base_url.rstrip('/')}/embeddings"
    resp = client.post(
        url,
        json={"model": settings.embedding_model, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    items = sorted(data, key=lambda item: item.get("index", 0))
    embeddings = [item.get("embedding") for item in items]
    if len(embeddings) == len(texts) and all(isinstance(item, list) for item in embeddings):
        return embeddings
    return None


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    results: list[list[float]] = []
    if settings.embedding_provider == "ollama":
        try:
            with httpx.Client() as client:
                for start in range(0, len(texts), batch_size):
                    batch = texts[start : start + batch_size]
                    embeddings = _ollama_embed_batch(client, batch)
                    if embeddings is not None:
                        results.extend(embeddings)
                    else:
                        results.extend(_local_batch(batch))
                return results
        except Exception:  # noqa: BLE001
            pass
    return _local_batch(texts)


def _local_batch(texts: list[str]) -> list[list[float]]:
    from app.knowledge.service import local_embedding

    return [local_embedding(text) for text in texts]

