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


def upsert_vectors(
    index,
    vectors: List[tuple[str, List[float], dict]],
    namespace: str,
) -> None:
    """
    vectors: list of (id, embedding, metadata). metadata often {"text": chunk_text}.
    namespace: str(institute_id).
    """
    if not vectors:
        return
    # Pinecone expects list of dicts: {"id": id, "values": embedding, "metadata": metadata}
    records = [
        {"id": vid, "values": vec, "metadata": meta or {}}
        for vid, vec, meta in vectors
    ]
    index.upsert(vectors=records, namespace=namespace)
    logger.info("Upserted %s vectors to namespace=%s", len(records), namespace)


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
