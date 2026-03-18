"""
Gemini embedding API: one vector per chunk; dimension 3072 for Pinecone index.
Uses models/gemini-embedding-001 with output_dimensionality=3072.
Retries on 429 (quota/rate limit) with exponential backoff.
"""
import logging
import time
from typing import List

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Supported by current Gemini API; 3072 dims to match Pinecone index (margai-ghost-tutor-v2).
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSION = 3072

# Retry on 429: max attempts, initial delay (seconds), backoff multiplier.
_MAX_RETRIES_429 = 3
_INITIAL_DELAY_429 = 2.0
_BACKOFF_429 = 2.0
# Small delay between batch items to avoid rate limit (seconds).
_DELAY_BETWEEN_EMBEDS = 0.3


def _embed_one(model: str, content: str):
    """Single embed_content call. Raises on failure."""
    return genai.embed_content(
        model=model,
        content=content,
        output_dimensionality=EMBEDDING_DIMENSION,
    )


def _is_rate_limit(exc: Exception) -> bool:
    """True if exception is 429 / quota exhausted."""
    if "429" in str(exc) or "quota" in str(exc).lower():
        return True
    try:
        from google.api_core.exceptions import ResourceExhausted
        return isinstance(exc, ResourceExhausted)
    except ImportError:
        return False


def _call_with_429_retry(model: str, content: str):
    """Call _embed_one with retries on 429 (ResourceExhausted)."""
    delay = _INITIAL_DELAY_429
    last_exc = None
    for attempt in range(_MAX_RETRIES_429):
        try:
            return _embed_one(model, content)
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e) and attempt < _MAX_RETRIES_429 - 1:
                logger.warning(
                    "Embedding rate limited (429), retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    _MAX_RETRIES_429,
                )
                time.sleep(delay)
                delay *= _BACKOFF_429
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Embedding failed after retries")


def get_embedding(
    text: str,
    api_key: str,
    model: str = EMBEDDING_MODEL,
    task_type: str = "retrieval_document",
) -> List[float]:
    """Embed a single text. task_type kept for call-site compatibility but not sent to Gemini API."""
    genai.configure(api_key=api_key)
    try:
        result = _call_with_429_retry(model, text)
        return result["embedding"]
    except Exception as e:
        logger.exception("embed_content failed for model=%s", model)
        raise RuntimeError(f"Embedding failed: {e}") from e


def get_embeddings_batch(
    texts: List[str],
    api_key: str,
    model: str = EMBEDDING_MODEL,
    batch_size: int = 100,
) -> List[List[float]]:
    """Embed multiple texts. Processes in batches. Retries on 429 with backoff."""
    genai.configure(api_key=api_key)
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for j, t in enumerate(batch):
            if j > 0:
                time.sleep(_DELAY_BETWEEN_EMBEDS)
            try:
                result = _call_with_429_retry(model, t)
                all_embeddings.append(result["embedding"])
            except Exception as e:
                logger.exception("embed_content failed for batch item (model=%s)", model)
                raise RuntimeError(f"Embedding failed: {e}") from e
    return all_embeddings
