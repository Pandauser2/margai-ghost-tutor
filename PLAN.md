# MargAI Ghost Tutor – 14-day pilot implementation plan

**Overall Progress:** `100%`

Webhook now runs on **n8n** (no Vercel). Telegram bot points to n8n webhook URL.

---

## TLDR

Build a **14-day pilot** where students ask doubts over **Telegram** and get answers from RAG over their institute’s PDFs. Multi-tenant via **Pinecone namespaces** (`institute_id`). When the model can’t answer, **ask one clarifying question** first; escalate to TA only after that (or if the student replies “escalate”). **Manual** PDF ingestion (teacher sends PDFs → you run script → upsert to Pinecone) and **manual** weekly report and log cleanup. Goal: validate the flow and collect success stories to sell **WhatsApp API** in Month 2.

---

## Critical decisions

- **Telegram first** — Free, ~5 min setup; WhatsApp (e.g. WATI/Interakt) in Month 2 after success stories.
- **Pinecone namespace = `institute_id`** — One namespace per coaching center; backend always queries only that namespace so Institute A never sees Institute B data.
- **Knowledge-lock** — Strict for content (answer only from context; “This wasn’t covered… I’ve flagged this for your teacher!” or ESCALATE); flexible for tone; allow general English/Math logic to explain steps, never new facts.
- **Clarify before escalate** — On ESCALATE or empty retrieval, send one clarifying message; only escalate when the student later replies “escalate” (or similar) or we get ESCALATE again on follow-up.
- **Manual triggers only** — No cron: ingestion, weekly report, and log cleanup are all run manually (script or n8n “Run workflow”).
- **Reuse extraction approach** — Same text+OCR logic as `upsc-test-engine` (pdfplumber, PyMuPDF, Tesseract); optional fallback later: LlamaParse/Unstructured.io if messy PDFs become a problem.
- **Risks as fallback** — n8n webhook latency and messy PDF parsing are documented; do not change the plan now; add logs where possible to detect them.

---

## Tasks

- [x] 🟩 **Step 1: Supabase schema and config**
  - [x] 🟩 Create `institutes` table: `id` (SERIAL/IDENTITY), `slug` (unique), `email_for_report`, `ta_telegram_id`, optional `created_at`.
  - [x] 🟩 Create `uploads` table: `id`, `institute_id` (FK → `institutes.id`), `file_path`, `filename`, `status` (processing/completed/failed), `created_at`, optional `completed_at`, `error_message`.
  - [x] 🟩 Create `query_logs` table: `id`, **`institute_id` (not null, FK → `institutes.id`)**, `student_telegram_id`, `student_name`, `timestamp`, `query_text`, `is_photo`, `escalated`, optional `clarification_sent`, `replied_at`. Ensure every row is linked to an institute.
  - [x] 🟩 Enable **RLS** on `institutes` and `query_logs` (e.g. policy `FOR ALL USING (institute_id = 1)` for pilot so rows are scoped by institute). n8n/backend uses service_role and bypasses RLS.

- [x] 🟩 **Step 2: Pinecone index and namespace convention**
  - [x] 🟩 Create Pinecone serverless index with dimension matching embedding model (e.g. 768).
  - [x] 🟩 Document convention: upsert and query always use `namespace = institute_id` (or stable slug); one namespace per institute.

- [x] 🟩 **Step 3: PDF ingestion pipeline (Phase 1)**
  - [x] 🟩 Backend: upload endpoint or script that accepts PDF (reuse upsc-test-engine pattern: save to `upload_dir`, return path/doc_id).
  - [x] 🟩 Extraction: call or reuse logic from `upsc-test-engine` (text + OCR via `pdf_extraction_service.py` style: PyMuPDF, pdfplumber, Tesseract hin+eng where needed). Insert `uploads` row (status = processing).
  - [x] 🟩 Chunk: 800–1000 chars, overlap 100–200; stable IDs (e.g. slug + hash(file_path + chunk_index)).
  - [x] 🟩 Embed with Gemini embedding API; upsert to Pinecone with `namespace = institute_id`. Update `uploads.status = 'completed'` or `'failed'` + `error_message`.
  - [x] 🟩 Manual input: institute slug/name with uniqueness check. On failure, email ALERT_EMAIL.

- [x] 🟩 **Step 4: Telegram webhook and chat → institute mapping (Phase 2)**
  - [x] 🟩 **Build and host the Telegram webhook on n8n**: register bot, set webhook URL to n8n, validate secret_token on incoming requests.
  - [x] 🟩 **Map incoming `chat_id` (or bot context) to `institute_id` in Supabase** so the handler knows which Pinecone namespace to query. For pilot: single bot → single institute (e.g. hardcode `institute_id = 1` or read from config). For multi-tenant later: use a Supabase lookup (e.g. table mapping chat_id/bot to institute_id, or `institutes` row per bot).
  - [x] 🟩 On message: parse `message.from.id`, `message.chat.id`, `message.text`, `message.photo`; resolve `institute_id` via the mapping above before inserting into `query_logs` and querying Pinecone.

- [x] 🟩 **Step 5: RAG + reply flow (Phase 2)**
  - [x] 🟩 Insert into `query_logs` (institute_id, student_telegram_id, student_name, query_text, is_photo, escalated=false).
  - [x] 🟩 Embed query text; Pinecone query with `namespace = institute_id`, top K 5–10.
  - [x] 🟩 Build prompt: Knowledge-lock system prompt (§5.3 EXPLORATION) + “If you cannot answer from context, respond with exactly: ESCALATE.” User = context chunks + query (+ image if photo). Call Gemini **gemini-2.5-flash** (text + optional image).
  - [x] 🟩 If response normalized === "ESCALATE": send clarifying message to student; set `clarification_sent = true` on row; do not escalate. If next message from same student is “escalate” (normalized): set `escalated = true` on previous row; reply to student; send TA full message (From: student, text + image) via Telegram using `institutes.ta_telegram_id`. Else: reply to student with Gemini answer via Telegram sendMessage.
  - [x] 🟩 Empty/weak retrieval: same clarifying-question path. On API failure: email ALERT_EMAIL, reply “Something went wrong.”

- [x] 🟩 **Step 6: Weekly report and cleanup (Phase 3)**
  - [x] 🟩 Weekly report: manual trigger; query `query_logs` last 7 days, institute_id=1; compute total queries, escalation %, top 5 topics (JEE/NEET/UPSC placeholder keywords); optional top students and who escalated. Generate email body text only; do not send (you send manually).
  - [x] 🟩 Cleanup: manual trigger; delete from `query_logs` where `timestamp` < now − 30 days.

- [x] 🟩 **Step 7: Observability (optional, not blocking)**
  - [x] 🟩 Where possible, log request duration (webhook received → reply sent) to detect latency (n8n).
  - [x] 🟩 Where possible, log per-upload extraction outcome (e.g. total chars, page count, errors) to detect messy PDFs (fallback: LlamaParse/Unstructured.io).

---

*Reference: `margai-ghost-tutor-pilot/EXPLORATION.md` for full flows, schema, edge cases, and risks.*
