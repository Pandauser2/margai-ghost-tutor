#!/usr/bin/env python3
"""
Local test for ingestion pipeline: extraction + chunking only (no Supabase/Pinecone/Gemini).
Use to verify code with a sample PDF. Full ingest requires .env (SUPABASE_*, GEMINI_API_KEY, PINECONE_API_KEY).
Usage: python scripts/test_ingest_local.py <path_to.pdf> [institute_slug]
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UPSC_BACKEND = REPO_ROOT / "upsc-test-engine" / "backend"
if UPSC_BACKEND.exists():
    sys.path.insert(0, str(UPSC_BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def extract_text(file_path: Path) -> tuple[str, int, str | None]:
    try:
        from app.services.pdf_extraction_service import extract_hybrid
        result = extract_hybrid(file_path)
        if not result.is_valid:
            return result.text or "", result.page_count, result.error_message or "Extraction failed"
        return result.text, result.page_count, None
    except ImportError:
        import pymupdf
        doc = pymupdf.open(file_path)
        try:
            text = "\n\n".join(doc[i].get_text() for i in range(len(doc)))
            return text.strip(), len(doc), None
        finally:
            doc.close()
    except Exception as e:
        return "", 0, str(e)


def main() -> int:
    pdf_path = (Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "manual-qc-pdfs" / "small_test_upsc.pdf").resolve()
    slug = sys.argv[2] if len(sys.argv) > 2 else "test-institute"
    if not pdf_path.exists():
        print("PDF not found:", pdf_path, file=sys.stderr)
        return 1
    text, page_count, err = extract_text(pdf_path)
    if err:
        print("Extraction failed:", err, file=sys.stderr)
        return 1
    from lib.chunking import chunk_with_ids, id_prefix_from_path
    prefix = id_prefix_from_path(pdf_path, slug)
    chunks = chunk_with_ids(text, prefix)
    print("Extraction: page_count=%s total_chars=%s" % (page_count, len(text)))
    print("Chunking: num_chunks=%s" % len(chunks))
    if chunks:
        print("Sample chunk id=%s len=%s" % (chunks[0][0], len(chunks[0][1])))
    print("Local test OK. For full ingest set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY, PINECONE_API_KEY and run ingest_pdf.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
