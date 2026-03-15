# Changelog

## Unreleased

### Added
- **n8n:** `n8n-workflows/telegram-webhook.json` + `README-telegram-webhook.md` – Telegram Ghost Tutor webhook with Supabase log, Gemini + Pinecone RAG, clarify-before-escalate path.

### Fixed
- **Embedding:** Switched from deprecated `text-embedding-004` to `models/gemini-embedding-001` with `output_dimensionality=768` (fixes 404 on ingest).
- **Embedding:** Retry on 429 (quota/rate limit) with exponential backoff; small delay between batch items to reduce rate-limit hits.
- **RUN.md:** Updated to remove Vercel deploy steps and show n8n import + Telegram webhook wiring; Python deps documented explicitly (no `requirements.txt`).

### Removed
- **docs/VERCEL_STEP_BY_STEP.md** – Step-by-step Vercel deploy and Telegram webhook (no prior experience assumed).
- **scripts/push_env_to_vercel.sh** – Pushed vars from `.env` to Vercel via CLI (`vercel env add`); no longer needed now that webhook runs on n8n.

### Changed
- **RUN.md** – Env step and ingestion remain; webhook section now assumes n8n (no Vercel) and points Telegram bot to the n8n webhook URL.
- **lib/config.py** – Loads `pilot/.env` when present (scripts work from repo root without exporting env manually).
