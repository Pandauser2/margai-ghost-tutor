# MargAI Ghost Tutor – 14-day pilot

RAG over institute PDFs; students ask on **Telegram**, get answers or clarify→escalate to TA. Multi-tenant via Pinecone namespaces (`institute_id`).

**→ Step-by-step run guide (bash commands): [RUN.md](RUN.md)**

## Setup

1. **Supabase**  
   Run `supabase/migrations/001_initial_schema.sql` in the SQL Editor (or `supabase db push`). Insert at least one row in `institutes` (e.g. `slug`, `email_for_report`, `ta_telegram_id`).

2. **Pinecone**  
   Create a serverless index (dimension 768). See `docs/PINECONE_NAMESPACE.md` for namespace convention.

3. **Env**  
   Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` (optional).

4. **Telegram webhook**  
   Deploy to Vercel (`vercel` from project root). Set webhook URL to `https://<your-domain>/api/telegram_webhook` and optional `secret_token` via BotFather / setWebhook.

## Usage

- **Ingest PDF:**  
  `python scripts/ingest_pdf.py path/to/file.pdf institute-slug`  
  (Reuses extraction from `upsc-test-engine` when run from repo root.)

- **Weekly report:**  
  `python scripts/weekly_report.py`  
  Prints email body; you send manually.

- **Cleanup:**  
  `python scripts/cleanup_logs.py`  
  Deletes `query_logs` older than 30 days.

## Testing

- **Local (no Supabase/Pinecone/Gemini):**  
  From repo root:  
  `python margai-ghost-tutor-pilot/scripts/test_ingest_local.py manual-qc-pdfs/small_test_upsc.pdf test-institute`  
  Verifies extraction and chunking only.

- **Full ingest:**  
  Install deps (`pip install -r margai-ghost-tutor-pilot/requirements.txt`), set `.env`, then from repo root:  
  `python margai-ghost-tutor-pilot/scripts/ingest_pdf.py manual-qc-pdfs/small_test_upsc.pdf test-institute`

## Observability

- **Webhook:** Logs `request_duration_seconds` (webhook received → reply sent) to spot cold-start latency.
- **Ingestion:** Logs extraction outcome (`total_chars`, `page_count`, `is_valid`) per upload to spot messy PDFs.

See `EXPLORATION.md` and `PLAN.md` for full design and task list.
