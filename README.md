# MargAI Ghost Tutor – 14-day pilot

Webhook now runs on **n8n** (no Vercel). Telegram bot points to n8n webhook URL.

RAG over institute PDFs; students ask on **Telegram**, get answers or clarify→escalate to TA. Multi-tenant via Pinecone namespaces (`institute_id`).

**→ Step-by-step run guide (bash commands): [RUN.md](RUN.md)**  
**→ Onboarding many institutes (bots, n8n, webhooks): [docs/MULTI-INSTITUTE-ONBOARDING.md](docs/MULTI-INSTITUTE-ONBOARDING.md)**  
**→ What each doc is for: [docs/README.md](docs/README.md)**

**Architecture / design narrative:** [EXPLORATION.md](EXPLORATION.md) (flows, schema, risks — kept aligned with `lib/`, workflows). **Pinecone:** [docs/PINECONE_NAMESPACE.md](docs/PINECONE_NAMESPACE.md). **Deploy:** [docs/PRODUCTION-DEPLOYMENT-PLAN.md](docs/PRODUCTION-DEPLOYMENT-PLAN.md). **RAG quality:** [docs/RAG-FAITHFULNESS-TRACKER.md](docs/RAG-FAITHFULNESS-TRACKER.md).

## Setup

1. **Supabase**  
   Run `supabase/migrations/001_initial_schema.sql` in the SQL Editor (or `supabase db push`). Insert at least one row in `institutes` (e.g. `slug`, `email_for_report`, `ta_telegram_id`).

2. **Pinecone**  
   Create a serverless index (dimension 3072, name `margai-ghost-tutor-v2`). See `docs/PINECONE_NAMESPACE.md` for namespace convention.

3. **Env**  
   Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` (optional).

4. **Telegram webhook**  
   Run the webhook workflow in n8n. Set Telegram webhook URL to your n8n webhook URL and optional `secret_token` via BotFather / setWebhook.

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
  Install deps for scripts (see `scripts/` and `lib/`), set `.env`, then from repo root:  
  `python margai-ghost-tutor-pilot/scripts/ingest_pdf.py manual-qc-pdfs/small_test_upsc.pdf test-institute`

## Observability

- **Webhook (n8n):** Log request duration (webhook received → reply sent) where n8n supports it.
- **Ingestion:** Logs extraction outcome (`total_chars`, `page_count`, `is_valid`) per upload to spot messy PDFs.

See `EXPLORATION.md` and `PLAN.md` for full design and task list. **Post-pilot multi-institute** summary is in `PLAN.md` § Multi-institute; diagrams and checklists in `docs/MULTI-INSTITUTE-ONBOARDING.md`.

## RAG quality

- **Faithfulness / overreach:** `docs/RAG-FAITHFULNESS-TRACKER.md` — prompts, retrieval tuning, test matrix, change log.
