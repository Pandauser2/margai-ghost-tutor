"""
Chunk full text for RAG: 800–1000 chars, overlap 100–200.
Stable IDs: prefix + hash(file_path + chunk_index) for idempotent upserts.
"""
import hashlib
from pathlib import Path
from typing import Iterator


CHUNK_SIZE = 1000
OVERLAP = 200


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks. Overlap is number of chars shared with next chunk.
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def chunk_with_ids(
    text: str,
    id_prefix: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[tuple[str, str]]:
    """
    Returns list of (id, text). id = prefix + "_" + hash(prefix + index) for stability.
    """
    raw = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    out: list[tuple[str, str]] = []
    for i, t in enumerate(raw):
        stable = hashlib.sha256(f"{id_prefix}_{i}".encode()).hexdigest()[:16]
        out.append((f"{id_prefix}_{stable}", t))
    return out


def id_prefix_from_path(file_path: str | Path, slug: str) -> str:
    """Stable prefix for chunk IDs: slug + short hash of file path."""
    path_str = str(Path(file_path).resolve())
    h = hashlib.sha256(path_str.encode()).hexdigest()[:8]
    return f"{slug}_{h}"
