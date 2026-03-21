"""
Pinecone upsert and query with namespace = institute_id.
One namespace per institute for multi-tenancy.
"""
import logging
from typing import List

from pinecone import Pinecone

logger = logging.getLogger(__name__)


def get_pinecone_index(api_key: str, index_name: str):
    """Return Pinecone index handle. Assumes index already exists (create via console or docs)."""
    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


# Pinecone request payload limit ~4 MB; batch to stay under it (e.g. 80 vectors per batch for 3072-dim + metadata).
UPSERT_BATCH_SIZE = 80


def upsert_vectors(
    index,
    vectors: List[tuple[str, List[float], dict]],
    namespace: str,
) -> None:
    """
    vectors: list of (id, embedding, metadata). metadata often {"text": chunk_text}.
    namespace: str(institute_id).
    Upserts in batches to stay under Pinecone's ~4 MB request limit.
    """
    if not vectors:
        return
    # Pinecone expects list of dicts: {"id": id, "values": embedding, "metadata": metadata}
    records = [
        {"id": vid, "values": vec, "metadata": meta or {}}
        for vid, vec, meta in vectors
    ]
    for i in range(0, len(records), UPSERT_BATCH_SIZE):
        batch = records[i : i + UPSERT_BATCH_SIZE]
        index.upsert(vectors=batch, namespace=namespace)
    logger.info("Upserted %s vectors to namespace=%s (batches of %s)", len(records), namespace, UPSERT_BATCH_SIZE)


def query_index(
    index,
    vector: List[float],
    namespace: str,
    top_k: int = 10,
    include_metadata: bool = True,
):
    """
    Query Pinecone in the given namespace. Returns matches with scores and metadata.
    """
    return index.query(
        vector=vector,
        namespace=namespace,
        top_k=top_k,
        include_metadata=include_metadata,
    )
