# MargAI Ghost Tutor – 14-day pilot exploration

**Purpose:** Understand and plan the bare-minimum pilot. No implementation yet.

---

## 1. Codebase and context

- **No existing MargAI/Ghost Tutor code** in this repo. The pilot is greenfield.
- **Reusable context in repo:**
  - `upsc-test-engine/` uses **Gemini** (REST + SDK), PDF extraction (pdfplumber, PyMuPDF, OCR), and chunking/LLM patterns. That stack is Python/FastAPI; the pilot is **n8n + serverless**, so we reuse concepts (chunk size, system prompt, “answer from context only”) not the code.
  - `create_kolkata_salary_presentation.py` and similar scripts show Python/script usage in the workspace; no direct reuse for n8n.

**Conclusion:** Pilot will be implemented in n8n (workflows + Code nodes), Supabase (SQL), and config (env/sheet). No dependency on existing app code.

---

## 2. Stack integration summary

| Component | Role in pilot | Notes |
|-----------|----------------|--------|
| **n8n (self-hosted)** | Orchestration: cron triggers, Google Sheet read, HTTP (PDF, APIs), PDF extract, chunking (Code), embed, Pinecone, webhook, Supabase, email. | Use Schedule Trigger for “every 4h” and “daily” / “Monday 09:00 IST”; no native “new row” trigger on sheet, so cron + “read sheet” and process (all rows or track last row). |
| **Supabase** | Single table `query_logs`; no auth/dashboard. n8n uses **service role** key (bypasses RLS). | RLS with `institute_id = 1` for defense in depth if anon key is ever used. |
| **Pinecone serverless** | One namespace per institute = slug (e.g. `fiitjee-kolkata`). Create index with dimension matching embedding model (e.g. **768** for `text-embedding-004` or Gemini embedding). | Namespace created on first upsert. No separate “institute” table in DB. |
| **WhatsApp (Interakt or WATI)** | BYOK: institute’s number. Inbound → n8n webhook; outbound → provider API. | Webhook must return **200 within ~3s**; do minimal work (e.g. enqueue or write to Supabase), then process async or in same workflow if fast enough. |
| **Google Gemini** | (1) **Embedding:** e.g. `text-embedding-004` or Gemini embedding API (e.g. `gemini-embedding-001` → 768 dim). (2) **Chat/vision:** latest stable multimodal with free tier (as of Feb 2026: e.g. **gemini-2.5-flash** or **gemini-2.0-flash**); vision = inline base64 image in `generateContent`. | n8n: “Embeddings Google Gemini” node exists; for generateContent (text + optional image) use HTTP Request or “Google Gemini” node if it supports image input. |

---

## 3. Flow-by-flow breakdown

### 3.1 PDF ingestion

- **Trigger:** Schedule Trigger every 4 hours (e.g. `0 */4 * * *`).
- **Input:** One Google Sheet per institute (pilot: one sheet, ID set in workflow/config). Columns: `institute_name`, `email_for_report`, `ta_whatsapp_number`, `pdf_file` (direct download URL).
- **Logic:**
  - Read all rows (or “new” rows if we track last processed index; for minimal pilot, “process all rows” each run is acceptable and idempotent if chunk IDs are deterministic: e.g. `slug + hash(pdf_url + chunk_index)`).
  - For each row: `slug = institute_name` → lowercase, replace spaces/special chars with hyphen.
  - Download PDF: HTTP Request (GET) to `pdf_file`. **Edge case:** Google Drive links often redirect or need “export” URL; “direct download URL” implies a link that returns PDF bytes (e.g. Drive “anyone with link” export link).
  - Extract text: n8n **Extract from File** (binary from HTTP) for text-based PDFs; image-only PDFs need OCR (out of scope for “bare minimum” or delegate to external API).
  - Chunk: Code node, 800–1000 chars, overlap (e.g. 100–200 chars). Output array of `{ text, id }` with stable IDs.
  - Embed: Embeddings Google Gemini (or HTTP to Gemini embedding API) for each chunk; get vectors.
  - Upsert: Pinecone (namespace = slug). n8n has **Pinecone Vector Store** (LangChain-style); for raw “upsert by namespace” we may need **HTTP Request** to Pinecone REST (upsert with `namespace` in body).
- **Dependencies:** Google Sheet credentials, Gemini API key, Pinecone API key + index (created once, dimension = embedding size). No Supabase for this flow.
- **Edge cases / constraints:**
  - Empty or failed PDF download → error branch → email yourself.
  - Sheet columns or missing values → validate in Code node; skip row and log.
  - Same PDF URL in multiple rows → same chunks upserted (same IDs) → idempotent.
  - No “institute” table: slug is computed from `institute_name` each time; for second institute, duplicate workflow and use different sheet ID (and slug comes from that sheet).

**Open point:** Where to get `ta_whatsapp_number` and `email_for_report` at runtime for **Student WhatsApp** and **Weekly report**? Spec says “from form” / “from latest form row”. Options: (A) Read the same sheet “get last row” when handling escalation and when sending weekly email; (B) Store in Supabase (e.g. `institute_config`) and update during ingestion. Minimal approach = (A) to avoid extra table.

---

### 3.2 Student WhatsApp interaction

- **Trigger:** Webhook (POST) from Interakt/WATI when a message is received.
- **Requirement:** Respond with 200 quickly (e.g. within 3s); then process (sync or async).
- **Input:** Webhook body: e.g. `data.message` (text/type), `data.customer` (waId, etc.). For images, provider often gives a message ID or media URL; WATI has `GET .../messages/file/{message_id}` to download media.
- **Logic:**
  - Parse body; extract `query_text`, `is_photo` (type === image), and if photo then media ID/URL for later.
  - Insert into Supabase `query_logs`: `institute_id = 1`, `timestamp`, `query_text`, `is_photo`, `escalated = false`.
  - Resolve namespace: for pilot, slug is fixed (e.g. from workflow config, same as ingestion) or derived from a single “institute 1” name. So: **slug = hardcoded for pilot** (e.g. `fiitjee-kolkata`).
  - Retrieve: Pinecone query with embedding of `query_text` (same embedding model as ingestion), namespace = slug, top K (e.g. 5–10).
  - Build prompt: system = “You are a helpful Indian coaching teacher… Answer only from context. If context doesn’t answer or unsure, respond with exactly: ESCALATE”; user = context chunks + user query (and if photo: add image part).
  - Call Gemini generateContent: if `is_photo` then send image (inline base64) + text; else text only. Model = e.g. `gemini-2.5-flash` or `gemini-2.0-flash`.
  - If response (trimmed/uppercase) === `"ESCALATE"`: set `escalated = true` in DB (update row), get `ta_whatsapp_number` from sheet (read last row) or config, send WhatsApp to TA: “Low confidence doubt – please review:\n[original message]\n[photo if sent]”. For “photo if sent”: either attach same media (if provider API supports “send image by URL”) or “[Photo was attached by student]” + text.
  - Else: reply to student (to `waId`) with Gemini’s answer via provider’s “send message” API.
- **Dependencies:** Supabase (insert/update), Pinecone (query), Gemini (embed + generateContent), WhatsApp provider (send message). Sheet read only for escalation path (TA number).
- **Edge cases:**
  - Empty or failed Pinecone/Gemini → catch error → optionally escalate or reply “Sorry, try again”; and email yourself.
  - ESCALATE matching: normalize (trim, optional uppercase) and require exact `"ESCALATE"` to avoid false positives.
  - Rate limits (Gemini/WhatsApp) → retry or queue; for pilot, simple retry once may be enough.

**Open point:** Escalation message “photo if sent”: do we send the actual image to TA (need media URL/upload to provider) or only text “[Student sent a photo]”? Affects provider API usage.

---

### 3.3 Weekly insight report

- **Trigger:** Schedule Trigger every Monday 09:00 IST (e.g. `0 9 * * 1` with timezone Asia/Kolkata).
- **Logic:**
  - Query Supabase: `query_logs` where `institute_id = 1` and `timestamp` in last 7 days.
  - Keywords: three arrays (JEE, NEET, UPSC) stored as JSON in workflow (e.g. in a Set node or Code node). Count matches in `query_text` (e.g. string includes, case-insensitive).
  - Compute: total queries, escalation % (where `escalated = true`), top 5 topics by count.
  - Get `email_for_report`: read Google Sheet (same as ingestion) last row, or from config.
  - Send plain-text email (e.g. Gmail SMTP or SendGrid) to `email_for_report` with summary.
- **Dependencies:** Supabase, Sheet (or config), email credentials.

---

### 3.4 Log cleanup

- **Trigger:** Schedule Trigger daily (e.g. `0 2 * * *`).
- **Logic:** Delete from `query_logs` where `timestamp` < now − 30 days. Supabase node “Delete” with filter, or raw SQL via Supabase (if supported) / HTTP.

---

## 4. Supabase schema (minimal)

- **Single table:** `query_logs`
  - `id` (uuid, default gen_random_uuid(), PK)
  - `institute_id` (int, not null) — pilot = 1
  - `timestamp` (timestamptz, default now())
  - `query_text` (text)
  - `is_photo` (boolean, default false)
  - `escalated` (boolean, default false)
- **RLS:** Enable RLS; one policy: `FOR ALL USING (institute_id = 1)` so that only institute 1 rows are visible when using non–service_role keys. n8n uses **service_role** and bypasses RLS.
- No auth, no dashboard; no `institutes` or `institute_config` table in the minimal version if we read TA/email from the sheet.

---

## 5. n8n workflow structure (conceptual)

- **Workflow 1 – Ingestion:** Schedule (0 */4 * * *) → Google Sheets (read rows) → Loop over rows → HTTP (get PDF) → Extract from File → Code (chunk) → Embeddings Google Gemini → Pinecone upsert (or HTTP to Pinecone). Error branch → email.
- **Workflow 2 – WhatsApp:** Webhook → Code (parse body, insert Supabase) → Embeddings Google Gemini (query text) → Pinecone query → Code (build prompt) → HTTP Gemini generateContent (or Google Gemini node) → IF response === ESCALATE → Supabase update + read Sheet (last row) + WhatsApp send to TA; ELSE → WhatsApp send to student.
- **Workflow 3 – Weekly report:** Schedule (Mon 09:00 IST) → Supabase get rows (filter last 7 days, institute_id=1) → Code (keyword counts, top 5, escalation %) → Read Sheet last row (email_for_report) → Send email.
- **Workflow 4 – Cleanup:** Schedule (daily) → Supabase delete (timestamp < now − 30 days).

Pinecone: if n8n’s Pinecone node does not support “namespace” and “raw upsert” cleanly, use **HTTP Request** to Pinecone Data API (upsert/query with `namespace` in body).

---

## 6. Error handling

- **Failed PDF download:** In ingestion, on HTTP error or empty body → send email to yourself (e.g. Gmail from n8n), optionally log row/sheet URL.
- **API failures (Gemini, Pinecone, WhatsApp):** In WhatsApp flow, try/catch; on failure send email to yourself and optionally reply to user “Something went wrong, please try again.”
- **Webhook timeout:** Keep webhook handler minimal (e.g. insert to Supabase + return 200); process in same workflow after response if n8n allows, or use a queue (e.g. “Execute Workflow” trigger) so provider gets 200 quickly.

---

## 7. Suggested manual test steps

1. **Form/sheet:** Add a row to the Google Sheet with institute_name, email_for_report, ta_whatsapp_number, pdf_file (a small public PDF URL). Run ingestion once (or wait for cron); check Pinecone dashboard for namespace and vector count.
2. **WhatsApp text:** Send a text message to the WhatsApp Business number; confirm reply from Gemini and one new row in `query_logs`.
3. **WhatsApp photo:** Send a photo with a question; confirm reply or escalation; if escalation, confirm TA receives WhatsApp with message (and if implemented, photo or “[Photo attached]”).
4. **ESCALATE:** Ask something off-topic or not in the PDF; expect “ESCALATE” path and TA notification.
5. **Weekly report:** Trigger Monday workflow or run manually; confirm email at `email_for_report` with total queries, escalation %, top topics.
6. **Cleanup:** Insert an old row (or backdate in DB for test), run cleanup workflow, confirm row deleted.

---

## 8. Ambiguities and questions for you

1. **PDF URL type:** Should we assume “direct” PDF URLs only (e.g. S3, public link that returns `Content-Type: application/pdf`), or do you want support for **Google Drive** “share” links (which often need redirect handling or export format)? If Drive is required, we need a small helper (e.g. replace `/file/d/ID` with export URL) in the workflow.

2. **Image-based PDFs:** Pilot scope is “extract text” only; scanned/image-only PDFs won’t work with “Extract from File” alone. Confirm: pilot is **text-based PDFs only**, or we need an OCR path (e.g. Gemini vision per page, or external OCR API)?

3. **Escalation – photo to TA:** When student sends a photo, should the TA receive (a) the **actual image** (we’d need to fetch media from WATI/Interakt and re-upload to send to TA), or (b) only text “[Student sent a photo]” plus the student’s text? (b) is simpler and avoids media round-trip.

4. **Webhook response time:** Interakt/WATI expect 200 within ~3s. Full flow (Supabase insert → embed → Pinecone → Gemini → WhatsApp reply) can exceed that. Prefer: (A) webhook only inserts to Supabase and returns 200, then a **separate scheduled workflow** (e.g. every 1 min) processes new `query_logs` rows that don’t have a “replied” flag yet; or (B) we accept risk and run the whole flow in the webhook (and hope it’s under 3s for simple queries)? (A) is safer for production.

5. **Gemini model names:** As of Feb 2026, which exact model IDs should we use? (e.g. `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-embedding-001`). I’ll use “latest stable with free tier + vision” in docs; please confirm or specify.

6. **Embedding model and dimension:** Confirm embedding model (e.g. Gemini `text-embedding-004` or `gemini-embedding-001`) and **vector dimension** (e.g. 768) so the Pinecone index is created correctly.

7. **Institute 1 slug:** For pilot, should the namespace slug be (a) **hardcoded** in n8n (e.g. `fiitjee-kolkata`) or (b) taken from the **first/latest row** of the sheet each time? (a) is simpler and avoids reading the sheet in the WhatsApp path.

8. **Email for errors:** Where should “email yourself” go? Single address in n8n env (e.g. `ALERT_EMAIL`) or same as `email_for_report` from the sheet?

9. **Topic keywords:** Do you have initial JEE/NEET/UPSC keyword lists, or should we start with placeholder arrays (e.g. a few terms per exam) and you’ll refine later?

10. **Interakt vs WATI:** Which provider will you use first? Webhook payload and “send message” API differ slightly; we can abstract in the workflow but need one to test against.

---

## 9. Phasing (3 steps)

- **Phase 1 – Ingestion + storage:** Supabase schema, one n8n workflow: cron every 4h → read sheet → download one PDF → extract text → chunk → embed → Pinecone upsert. No WhatsApp yet. Validate: sheet row → Pinecone namespace with vectors.
- **Phase 2 – WhatsApp + RAG:** Webhook workflow: receive message → log to Supabase → Pinecone retrieval → Gemini → reply or escalate (TA number from sheet). Manual test with text and photo.
- **Phase 3 – Reports + cleanup:** Weekly report workflow (Monday 09:00 IST) and daily cleanup; error-handling emails.

Once you confirm the open points above, this exploration is enough to implement the pilot step by step.
