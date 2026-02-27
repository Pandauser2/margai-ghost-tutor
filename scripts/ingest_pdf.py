#!/usr/bin/env python3
"""
PDF ingestion for MargAI Ghost Tutor: extract (reuse upsc-test-engine), chunk, embed, upsert to Pinecone.
Usage: python scripts/ingest_pdf.py <path_to.pdf> <institute_slug> [--upload-dir DIR]
- Resolves institute_id from Supabase (by slug); inserts uploads row (processing) then completes/fails.
- Namespace = institute_id. Logs extraction outcome (chars, page_count) for observability.
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse upsc-test-engine extraction when run from repo root (Cursor_test_project)
REPO_ROOT = Path(__file__).resolve().parents[2]
UPSC_BACKEND = REPO_ROOT / "upsc-test-engine" / "backend"
if UPSC_BACKEND.exists():
    sys.path.insert(0, str(UPSC_BACKEND))

# Project lib
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client

from lib.chunking import chunk_with_ids, id_prefix_from_path
from lib.embedding import get_embeddings_batch
from lib.pinecone_client import get_pinecone_index, upsert_vectors

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_text(file_path: Path) -> tuple[str, int, str | None]:
    """
    Extract text using upsc-test-engine hybrid extraction when available.
    Returns (text, page_count, error_message). error_message set on failure.
    """
    try:
        from app.services.pdf_extraction_service import extract_hybrid
    except ImportError:
        logger.warning("upsc-test-engine not found; using minimal PyMuPDF extraction")
        try:
            import pymupdf
            doc = pymupdf.open(file_path)
            try:
                text = "\n\n".join(doc[i].get_text() for i in range(len(doc)))
                return text.strip(), len(doc), None
            finally:
                doc.close()
        except Exception as e:
            return "", 0, str(e)

    result = extract_hybrid(file_path)
    # Observability: log extraction outcome (chars, page count)
    logger.info(
        "extraction outcome: total_chars=%s page_count=%s is_valid=%s",
        len(result.text), result.page_count, result.is_valid,
    )
    if not result.is_valid:
        return result.text or "", result.page_count, result.error_message or "Extraction failed"
    return result.text, result.page_count, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF into Pinecone for an institute")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument("institute_slug", type=str, help="Institute slug (e.g. fiitjee-kolkata)")
    parser.add_argument("--upload-dir", type=Path, default=None, help="Optional upload dir for file_path in DB")
    parser.add_argument("--supabase-url", type=str, default=None, help="Supabase URL (or env SUPABASE_URL)")
    parser.add_argument("--supabase-key", type=str, default=None, help="Supabase service_role key (or env)")
    args = parser.parse_args()

    pdf_path = args.pdf_path.resolve()
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    import os
    from lib.config import get_settings
    settings = get_settings()
    supabase_url = args.supabase_url or settings.supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = args.supabase_key or settings.supabase_service_role_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        logger.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or .env)")
        sys.exit(1)

    sb = create_client(supabase_url, supabase_key)

    # Resolve institute_id by slug (create if missing for pilot)
    r = sb.table("institutes").select("id").eq("slug", args.institute_slug).execute()
    if r.data and len(r.data) > 0:
        institute_id = int(r.data[0]["id"])
    else:
        ins = sb.table("institutes").insert({"slug": args.institute_slug}).execute()
        if not ins.data or len(ins.data) == 0:
            logger.error("Failed to create institute for slug %s", args.institute_slug)
            sys.exit(1)
        institute_id = int(ins.data[0]["id"])
    logger.info("Using institute_id=%s for slug=%s", institute_id, args.institute_slug)

    file_path_stored = str(args.upload_dir / pdf_path.name) if args.upload_dir else str(pdf_path)
    upload_row = sb.table("uploads").insert({
        "institute_id": institute_id,
        "file_path": file_path_stored,
        "filename": pdf_path.name,
        "status": "processing",
    }).execute()
    if not upload_row.data or len(upload_row.data) == 0:
        logger.error("Failed to insert uploads row")
        sys.exit(1)
    upload_id = upload_row.data[0]["id"]

    try:
        text, page_count, err = extract_text(pdf_path)
        if err:
            sb.table("uploads").update({
                "status": "failed",
                "error_message": err,
            }).eq("id", upload_id).execute()
            logger.error("Extraction failed: %s", err)
            sys.exit(1)

        if not text or len(text.strip()) < 100:
            sb.table("uploads").update({
                "status": "failed",
                "error_message": "Extracted text too short or empty",
            }).eq("id", upload_id).execute()
            logger.error("Extracted text too short (chars=%s)", len(text.strip()))
            sys.exit(1)

        prefix = id_prefix_from_path(pdf_path, args.institute_slug)
        chunks_with_ids = chunk_with_ids(text, prefix)
        if not chunks_with_ids:
            sb.table("uploads").update({"status": "failed", "error_message": "No chunks produced"}).eq("id", upload_id).execute()
            sys.exit(1)

        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("Set GEMINI_API_KEY")
            sb.table("uploads").update({"status": "failed", "error_message": "GEMINI_API_KEY not set"}).eq("id", upload_id).execute()
            sys.exit(1)

        embeddings = get_embeddings_batch([t for _, t in chunks_with_ids], api_key)
        vectors = [
            (cid, emb, {"text": t})
            for (cid, t), emb in zip(chunks_with_ids, embeddings)
        ]

        pc_key = settings.pinecone_api_key or os.environ.get("PINECONE_API_KEY")
        if not pc_key:
            logger.error("Set PINECONE_API_KEY")
            sb.table("uploads").update({"status": "failed", "error_message": "PINECONE_API_KEY not set"}).eq("id", upload_id).execute()
            sys.exit(1)

        index = get_pinecone_index(pc_key, settings.pinecone_index_name or os.environ.get("PINECONE_INDEX_NAME", "margai-ghost-tutor"))
        upsert_vectors(index, vectors, namespace=str(institute_id))

        sb.table("uploads").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", upload_id).execute()
        logger.info("Ingestion complete: upload_id=%s namespace=%s chunks=%s", upload_id, institute_id, len(vectors))
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        sb.table("uploads").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", upload_id).execute()
        sys.exit(1)


if __name__ == "__main__":
    main()
