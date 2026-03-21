"""
Chunk full text for RAG: 800–1000 chars, overlap 100–200.
Stable IDs: prefix + hash(file_path + chunk_index) for idempotent upserts.
"""
import hashlib
import re
from pathlib import Path

CHUNK_SIZE = 1000
OVERLAP = 200


_BOX_HEADING_RE = re.compile(r"^Box\s+\d+\.\d+.*$")
_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)+\s+.+$")
_TITLE_HEADING_RE = re.compile(r"^[A-Z][A-Za-z\s]{5,}$")


def normalize_chunk_text(text: str) -> str:
    """Normalize newlines and whitespace noise before section split."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_heading(line: str) -> bool:
    """Heuristic heading detector for textbook PDFs."""
    s = (line or "").strip()
    if not s or len(s) < 6:
        return False
    if _BOX_HEADING_RE.match(s):
        return True
    if _NUMBERED_HEADING_RE.match(s):
        return True
    if _TITLE_HEADING_RE.match(s) and len(s.split()) <= 12:
        return True
    return False


def split_into_sections(text: str) -> list[str]:
    """
    Split text into sections using heading-like lines.
    Falls back to paragraph-style split when no heading is detected.
    """
    normalized = normalize_chunk_text(text)
    if not normalized:
        return []

    lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
    sections: list[str] = []
    current: list[str] = []
    seen_heading = False
    for ln in lines:
        if _looks_like_heading(ln):
            if current:
                sections.append("\n".join(current).strip())
            current = [ln]
            seen_heading = True
        else:
            current.append(ln)
    if current:
        sections.append("\n".join(current).strip())

    if seen_heading:
        return [s for s in sections if s.strip()]
    # No headings found: preserve existing paragraph-ish behavior.
    return [p.strip() for p in normalized.split("\n\n") if p.strip()]


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks, preferring paragraph boundaries.
    Overlap is number of chars shared with next chunk.
    """
    if not text or not text.strip():
        return []
    sections = split_into_sections(text)
    if not sections:
        return []

    chunks: list[str] = []
    for section in sections:
        paras = [p.strip() for p in section.split("\n\n") if p.strip()]
        if not paras:
            continue
        heading = paras[0].split("\n", 1)[0].strip()
        current = ""
        for para in paras:
            if len(para) > chunk_size:
                if current.strip():
                    chunks.append(current.strip())
                    current = ""
                start = 0
                first_piece = True
                while start < len(para):
                    end = start + chunk_size
                    piece = para[start:end].strip()
                    if piece:
                        if heading and not piece.startswith(heading) and not first_piece:
                            piece = f"{heading}\n\n{piece}"
                        chunks.append(piece)
                    first_piece = False
                    start = end - overlap
                    if start >= len(para):
                        break
                continue
            candidate = f"{current}\n\n{para}".strip() if current else para
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = para
        if current.strip():
            chunks.append(current.strip())

    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            current = chunks[i]
            prev_tail = overlapped[-1][-overlap:].strip()
            if not prev_tail:
                overlapped.append(current)
                continue
            sep = "\n\n"
            max_len = chunk_size + overlap
            available_tail = max(0, max_len - len(current) - len(sep))
            tail = prev_tail[-available_tail:] if available_tail > 0 else ""
            merged = f"{tail}{sep}{current}".strip() if tail else current
            overlapped.append(merged)
        chunks = overlapped

    return [c for c in chunks if c.strip()]


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
