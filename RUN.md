# Step-by-step: Run the MargAI Ghost Tutor pilot

Copy-paste bash commands and minimal manual steps. Assumes you're in the **monorepo root** (`Cursor_test_project`) unless noted.

---

## 1. Prerequisites

- Python 3.10+
- Node.js (for Vercel CLI)
- Accounts: Supabase, Pinecone, Google AI (Gemini), Telegram Bot

---

## 2. Supabase

**2.1** Create a project at [supabase.com](https://supabase.com) and get:
- Project URL → `SUPABASE_URL`
- Settings → API → `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`

**2.2** Run the schema (Supabase Dashboard → SQL Editor → New query):

```bash
# Or paste contents of the migration file:
cat margai-ghost-tutor-pilot/supabase/migrations/001_initial_schema.sql
```

Copy the SQL from `margai-ghost-tutor-pilot/supabase/migrations/001_initial_schema.sql` into the SQL Editor and run it.

**2.3** Insert your pilot institute (SQL Editor):

```sql
INSERT INTO institutes (id, slug, email_for_report, ta_telegram_id)
VALUES (1, 'test-institute', 'your@email.com', NULL)
ON CONFLICT (id) DO NOTHING;
```

---

## 3. Pinecone

**3.1** Create a serverless index (Pinecone console or Python):

```bash
cd margai-ghost-tutor-pilot
python3 -c "
from pinecone import Pinecone, ServerlessSpec
import os
key = os.environ.get('PINECONE_API_KEY') or input('PINECONE_API_KEY: ')
pc = Pinecone(api_key=key)
pc.create_index(
    name='margai-ghost-tutor',
    dimension=768,
    metric='cosine',
    spec=ServerlessSpec(cloud='aws', region='us-east-1'),
)
print('Index created.')
"
```

Or create it in the Pinecone dashboard: dimension **768**, metric **cosine**, serverless.

---

## 4. Telegram bot

**4.1** In Telegram, message [@BotFather](https://t.me/BotFather), create a bot, copy the token → `TELEGRAM_BOT_TOKEN`.

**4.2** (Optional) Generate a webhook secret and set it in BotFather / `setWebhook` as `secret_token` → `TELEGRAM_WEBHOOK_SECRET`:

```bash
openssl rand -hex 32
```

---

## 5. Environment and dependencies

**5.1** Create `.env` in the pilot folder:

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project/margai-ghost-tutor-pilot
cp .env.example .env
```

Edit `.env` and set:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME=margai-ghost-tutor`
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` (optional; leave empty if not using)
- `INSTITUTE_ID_DEFAULT=1` (matches the institute you inserted)

**5.2** Install Python deps (from repo root; use a venv if you prefer):

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project
python3 -m venv margai-ghost-tutor-pilot/.venv
source margai-ghost-tutor-pilot/.venv/bin/activate
pip install -r margai-ghost-tutor-pilot/requirements.txt
```

---

## 6. Verify ingestion (local)

**6.1** Local test (extraction + chunking only; no API keys needed):

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project
python3 margai-ghost-tutor-pilot/scripts/test_ingest_local.py manual-qc-pdfs/small_test_upsc.pdf test-institute
```

Expected: `Extraction: page_count=... total_chars=...` and `Chunking: num_chunks=...`.

**6.2** Full ingest (needs `.env` and Supabase/Pinecone/Gemini). From repo root:

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project
source margai-ghost-tutor-pilot/.venv/bin/activate
export $(grep -v '^#' margai-ghost-tutor-pilot/.env | xargs)
python3 margai-ghost-tutor-pilot/scripts/ingest_pdf.py manual-qc-pdfs/small_test_upsc.pdf test-institute
```

Expected: script runs without error; `uploads` and Pinecone namespace `1` get data.

---

## 7. Deploy webhook (Vercel)

**7.1** Install Vercel CLI and deploy from the **pilot** directory:

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project/margai-ghost-tutor-pilot
npx vercel --yes
```

Follow prompts (link existing project or create new). Set env vars in Vercel:

- Project → Settings → Environment Variables: add every variable from `.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `INSTITUTE_ID_DEFAULT`).

**7.2** Get your deployment URL (e.g. `https://margai-ghost-tutor-xxx.vercel.app`) and set the Telegram webhook:

```bash
# Replace BOT_TOKEN and YOUR_VERCEL_URL
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_URL>/api/telegram_webhook"
```

If you use a secret token:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<YOUR_VERCEL_URL>/api/telegram_webhook","secret_token":"<TELEGRAM_WEBHOOK_SECRET>"}'
```

---

## 8. Chat mapping (chat_id → institute_id)

The app maps each Telegram `chat_id` to an `institute_id`. For a single-bot pilot it uses `INSTITUTE_ID_DEFAULT` (e.g. `1`). To tie a specific chat to an institute, insert into Supabase (you’d add a table or use a config table; for pilot, default is enough).

Current behavior: if no mapping is found, `institute_id = INSTITUTE_ID_DEFAULT`.

---

## 9. Run and use

- **Students:** Open your bot in Telegram and send a message; they get RAG answers or clarify→escalate.
- **Weekly report:**  
  `python3 margai-ghost-tutor-pilot/scripts/weekly_report.py`  
  (with `.env` loaded) — prints email body.
- **Cleanup old logs:**  
  `python3 margai-ghost-tutor-pilot/scripts/cleanup_logs.py`  
  (optional `--dry-run` first).

---

## Quick reference

| Step | Command / action |
|------|-------------------|
| Schema | Run `001_initial_schema.sql` in Supabase SQL Editor |
| Institute | `INSERT INTO institutes ...` (id=1, slug=test-institute) |
| Pinecone | Create index dimension 768, name `margai-ghost-tutor` |
| Env | `cp .env.example .env` and fill in keys |
| Deps | `pip install -r margai-ghost-tutor-pilot/requirements.txt` |
| Local test | `python3 margai-ghost-tutor-pilot/scripts/test_ingest_local.py manual-qc-pdfs/small_test_upsc.pdf test-institute` |
| Ingest | `python3 margai-ghost-tutor-pilot/scripts/ingest_pdf.py manual-qc-pdfs/small_test_upsc.pdf test-institute` (from repo root, .env set) |
| Deploy | `cd margai-ghost-tutor-pilot && npx vercel --yes` |
| Webhook | `curl ... setWebhook?url=https://<YOUR_VERCEL_URL>/api/telegram_webhook` |
