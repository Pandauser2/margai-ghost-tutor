"""
Gemini embedding API: one vector per chunk; dimension 768 for text-embedding-004 / gemini-embedding-001.
"""
import logging
from typing import List

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Default model; dimension 768
EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSION = 768


def get_embedding(
    text: str,
    api_key: str,
    model: str = EMBEDDING_MODEL,
    task_type: str = "retrieval_document",
) -> List[float]:
    """Embed a single text. task_type: retrieval_document (chunks) or retrieval_query (user query)."""
    genai.configure(api_key=api_key)
    result = genai.embed_content(model=model, content=text, task_type=task_type)
    return result["embedding"]


def get_embeddings_batch(
    texts: List[str],
    api_key: str,
    model: str = EMBEDDING_MODEL,
    batch_size: int = 100,
) -> List[List[float]]:
    """Embed multiple texts. Processes in batches to respect rate limits."""
    genai.configure(api_key=api_key)
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for t in batch:
            result = genai.embed_content(model=model, content=t, task_type="retrieval_document")
            all_embeddings.append(result["embedding"])
    return all_embeddings
