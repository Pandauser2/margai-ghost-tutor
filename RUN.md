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

**New to Pinecone?** Follow **[docs/PINECONE_FROM_ZERO.md](docs/PINECONE_FROM_ZERO.md)** for account, API key, and creating the index via the dashboard (no Python required).

**3.1** Install the Pinecone client (use the same env you'll use for ingestion, or any Python 3.10+):

```bash
pip install "pinecone>=5.0.0"
```

**3.2** Create a serverless index (Pinecone console or Python):

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

**4.1** In Telegram, message [@BotFather](https://t.me/BotFather), create a bot. Copy the token it shows (“You can use this token to access HTTP API: …”) — that **is** `TELEGRAM_BOT_TOKEN`; put it in `.env` as `TELEGRAM_BOT_TOKEN`.

**4.2** (Optional) Generate a webhook secret and set it in BotFather / `setWebhook` as `secret_token` → `TELEGRAM_WEBHOOK_SECRET`:

```bash
openssl rand -hex 32
```

---

## 5. Environment and dependencies

**5.1** Create `.env` in the pilot folder (only if it doesn’t exist yet):

```bash
cd /Users/rajeshmukherjee/Desktop/04_Data_Science/Projects/Cursor_test_project/margai-ghost-tutor-pilot
[ -f .env ] || cp .env.example .env
```

If `.env` already exists, skip the copy and just edit it to add or update keys.

**5.1b How to edit `.env`:** Open `margai-ghost-tutor-pilot/.env` in Cursor (or any editor). Each line is `KEY=value` (no spaces around `=`). Replace the placeholder values with your real keys:

| Variable | Where to get it | Example |
|----------|-----------------|--------|
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL | `https://abcdefgh.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → `service_role` (secret) | `eyJhbGciOiJIUzI1NiIs...` |
| `PINECONE_API_KEY` | Pinecone console → API Keys | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `PINECONE_INDEX_NAME` | Name you gave the index | `margai-ghost-tutor` |
| `GEMINI_API_KEY` | Google AI Studio / API key for Gemini | `AIza...` |
| `TELEGRAM_BOT_TOKEN` | BotFather “token to access HTTP API” | `7123456789:AAH...` |
| `TELEGRAM_WEBHOOK_SECRET` | Optional; from `openssl rand -hex 32` or leave empty | `` or `a1b2c3...` |
| `INSTITUTE_ID_DEFAULT` | Must match the `id` you used in `INSERT INTO institutes` (e.g. 1) | `1` |

Example `.env` (with fake values):

```env
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
PINECONE_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PINECONE_INDEX_NAME=margai-ghost-tutor
GEMINI_API_KEY=AIzaSy...
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_WEBHOOK_SECRET=
INSTITUTE_ID_DEFAULT=1
```

Do not commit `.env` to git (it should be in `.gitignore`).

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
[ -f margai-ghost-tutor-pilot/.env ] && export $(grep -v '^#' margai-ghost-tutor-pilot/.env | xargs)
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

Follow prompts (link existing project or create new). **Set env vars in Vercel** (choose one):

**Option A – Script (from pilot folder, after `vercel login`):**
```bash
cd margai-ghost-tutor-pilot
chmod +x scripts/push_env_to_vercel.sh
./scripts/push_env_to_vercel.sh
```
This reads `.env` and runs `vercel env add` for each of: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `INSTITUTE_ID_DEFAULT`, `TELEGRAM_WEBHOOK_SECRET`. If the CLI prompts (e.g. “Add to Production?”), press Enter.

**Option B – Manual:** Project → Settings → Environment Variables → Add each variable from your `.env` (same names as above). For secrets (keys, tokens), set **Environments** to **Production** and **Preview** only (uncheck Development)—then the **Sensitive** toggle becomes available.

Then **redeploy** so the new env vars are used: Deployments → … on latest → Redeploy, or run `npx vercel --prod`.

**If build fails** with “pattern doesn’t match any Serverless Functions”: (1) Ensure your repo has an `api` folder with `telegram_webhook.py` at the project root (or at the path set as “Root Directory” in Vercel). (2) Push the current `vercel.json` (pattern `api/*.py`, maxDuration 30) to your `main` branch and redeploy from Vercel.

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
