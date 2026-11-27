from __future__ import annotations

from project.backend.search_engine.models import ModelServerClient, SearchModelClient, coerce_embedding_batch
from project.backend.search_engine.schemas import Preference


async def refresh_preference_embedding(
    preference: Preference,
    model_client: SearchModelClient | None = None,
) -> Preference:
    """Generate and attach a vector only when its complete embedding space is known."""
    client = model_client or ModelServerClient()
    batch = coerce_embedding_batch(
        await client.embed([f"{preference.attribute} {preference.value}"])
    )
    if batch is None or not batch.embeddings:
        return preference.model_copy(update={"embedding": None, "embedding_space": None})
    return preference.model_copy(
        update={
            "embedding": batch.embeddings[0],
            "embedding_space": batch.space,
        }
    )
