# Changelog

## Unreleased

### Added
- **docs/RAG-FAITHFULNESS-TRACKER.md** — Track RAG “context-only” failures (answers mixing other sections / general knowledge), fix phases, golden tests, change log.
- **n8n:** `n8n-workflows/telegram-webhook.json` + `README-telegram-webhook.md` — Telegram Ghost Tutor webhook: Supabase log, Gemini + Pinecone RAG, clarify→escalate path.

### Changed
- **Embedding (`lib/embedding.py`):** `models/gemini-embedding-001`, `output_dimensionality=3072` — must match Pinecone index (e.g. `margai-ghost-tutor-v2`).
- **Config (`lib/config.py`):** Default `pinecone_index_name` = `margai-ghost-tutor-v2`.
- **Pinecone (`lib/pinecone_client.py`):** Upsert in batches (`UPSERT_BATCH_SIZE=80`) to stay under ~4MB request limit.
- **Ingest (`scripts/ingest_pdf.py`):** Vector metadata includes `text`, `source_file`, `source_slug`, `chunk_id`; namespace = `str(institute_id)` from Supabase.
- **Chunking (`lib/chunking.py`):** Section/paragraph-oriented splitting + overlap (see module docstring).
- **RUN.md:** n8n import + Telegram wiring; Python deps documented (no root `requirements.txt` in pilot).

### Fixed
- **Embedding:** Retry on 429 with exponential backoff; small delay between batch embed calls.
- **Ingest:** Clearer error hint when `GEMINI_API_KEY` is rejected.

### Removed
- **docs/VERCEL_STEP_BY_STEP.md** — Vercel + Telegram webhook path (webhook on n8n now).
- **scripts/push_env_to_vercel.sh** — No longer used.

### Notes (verify in n8n UI)
- Latest workflow export may live at repo root as `v6.json` (not always in sync with `n8n-workflows/telegram-webhook.json`). **Gemini Chat `systemMessage`:** empty in some exports — set in n8n for strict context-only answers (see tracker doc).
