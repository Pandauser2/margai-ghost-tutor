# Changelog

## Unreleased

### Fixed
- **Embedding:** Switched from deprecated `text-embedding-004` to `models/gemini-embedding-001` with `output_dimensionality=768` (fixes 404 on ingest).
- **Embedding:** Retry on 429 (quota/rate limit) with exponential backoff; small delay between batch items to reduce rate-limit hits.
- **Vercel:** `vercel.json` pattern changed from `api/**/*.py` to `api/*.py` so the Python serverless function is matched and the build succeeds.

### Added
- **docs/PINECONE_FROM_ZERO.md** – Pinecone setup from zero (account, API key, create index via dashboard).
- **docs/VERCEL_STEP_BY_STEP.md** – Step-by-step Vercel deploy and Telegram webhook (no prior experience assumed).
- **scripts/push_env_to_vercel.sh** – Pushes vars from `.env` to Vercel via CLI (`vercel env add`).
- **scripts/test_ingest_local.py** – Local test for extraction + chunking only (no Supabase/Pinecone/Gemini).

### Changed
- **RUN.md** – Env step: optional `.env` copy if file exists; Sensitive toggle note (Production + Preview only); build-failure troubleshooting; link to Vercel step-by-step and Pinecone-from-zero.
- **lib/config.py** – Loads `pilot/.env` when present (scripts work from repo root without exporting env manually).
