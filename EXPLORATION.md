# MargAI Ghost Tutor – 14-day pilot exploration

**Purpose:** Understand and plan the bare-minimum pilot. No implementation yet.

---

## 1. Codebase and context

- **No existing MargAI/Ghost Tutor code** in this repo. The pilot is greenfield.
- **Reusable context in repo:**
  - `upsc-test-engine/` uses **Gemini** (REST + SDK), **PDF upload** (POST, save to `upload_dir`), and **PDF extraction** (pdfplumber, PyMuPDF, OCR via `pdf_extraction_service.py`). For MargAI we **reuse the upload system** (manual PDF upload; no sheet/download). Orchestration: n8n + serverless; we reuse concepts (chunk size, system prompt, “answer from context only”) not the code.
  - `create_kolkata_salary_presentation.py` and similar scripts show Python/script usage in the workspace; no direct reuse for n8n.

**Conclusion:** Pilot: **manual PDF upload** (reuse upsc-test-engine upload), n8n workflows, Supabase, Pinecone. Sheet only for `email_for_report`, `ta_whatsapp_number`. No "read sheet → download PDF".

---

## 2. Stack integration summary

| Component | Role in pilot | Notes |
|-----------|----------------|--------|
| **n8n (self-hosted)** | Orchestration: **manual PDF upload** (reuse upsc-test-engine upload) → backend extraction (text+OCR) → chunk → embed → Pinecone; webhook, Supabase, email. No sheet for PDF. | Ingestion: user **manually uploads** PDF; no "read sheet → download PDF". **No cron/scheduled triggers** — ingestion, weekly report, and log cleanup are all manual (run when you want). |
| **Supabase** | Single table `query_logs`; no auth/dashboard. n8n uses **service role** key (bypasses RLS). | RLS with `institute_id = 1` for defense in depth if anon key is ever used. |
| **Pinecone serverless** | One namespace per institute = slug (e.g. `fiitjee-kolkata`). Create index with dimension matching embedding model (e.g. **768** for `text-embedding-004` or Gemini embedding). | Namespace created on first upsert. No separate “institute” table in DB. |
| **WhatsApp (Interakt or WATI)** | BYOK: institute’s number. Inbound → n8n webhook; outbound → provider API. | **Use provider more popular in India** (research online; both WATI and Interakt are leading). Webhook must return **200 within ~3s**. |
| **Google Gemini** | (1) **Embedding:** e.g. `text-embedding-004` or Gemini embedding API (e.g. `gemini-embedding-001` → 768 dim). (2) **Chat/vision:** **Gemini 2.5 only** (Gemini 2.0 deprecated). Use **gemini-2.5-flash** (stable 2.5 multimodal, free tier + vision). | n8n: “Embeddings Google Gemini” node; for generateContent (text + optional image) use HTTP Request or “Google Gemini” node. |

---

## 3. Flow-by-flow breakdown

### 3.1 PDF ingestion

- **Trigger:** **Manual upload** only. User manually uploads the PDF; no sheet, no download. After upload, run extraction + chunk + embed + Pinecone (e.g. “Run workflow” in n8n or a manual trigger node).
- **Input:** (1) **PDF:** Manual upload only (reuse upsc-test-engine: `POST /documents/upload` pattern — save to `upload_dir` as `{doc_id}.pdf`; see `upsc-test-engine/backend/app/api/documents.py`). (2) **Institute namespace:** **Manual input field** for institute name/slug, with **uniqueness validation** (check slug not already used, e.g. Pinecone namespaces or Supabase slugs table). (3) Sheet only for `email_for_report`, `ta_whatsapp_number` (not for PDF). PDF is **not** from the sheet. User **manually uploads** the PDF; reuse the upload system from upsc-test-engine (see below).
- **Logic:**
  - **Slug:** From manual input field (institute name → lowercase, spaces/special chars → hyphen). Validate uniqueness before upserting.
  - **Extract text + OCR:** Use **same detection logic as upsc-test-engine** (both native text and OCR). Latency is not an issue (backend). Reference: `upsc-test-engine/backend/app/services/pdf_extraction_service.py` — `extract_hybrid()`, constants, and `_should_run_ocr_for_page`:
    - **Native text:** PyMuPDF blocks + pdfplumber layout; per-page mojibake fix.
    - **OCR trigger per page:** native text &lt; threshold (e.g. 100 chars) OR garbled heuristics (Latin-1 supplement ratio, first-2-pages header threshold, garbled-pattern count). Doc-level: if total native text &lt; 5000 chars, treat as image-heavy → OCR all pages.
    - **OCR:** Tesseract hin+eng, OpenCV preprocessing (gray, adaptive threshold, denoise), ftfy, noise-line filter. Parallel OCR for pages that need it. Merge: use OCR when OCR length ≥ native × 0.8 or OCR &gt; native.
  - Implementation option: (A) n8n calls a **small backend service** (e.g. FastAPI) that receives PDF bytes or URL, runs `extract_hybrid()`, returns full text; or (B) replicate the logic in an n8n-executable form (e.g. Code node with PDF libs if available, or subprocess). For “same logic,” (A) reusing `pdf_extraction_service.py` is the most accurate; latency is acceptable.
  - Chunk: 800–1000 chars, overlap (e.g. 100–200 chars). Output `{ text, id }` with stable IDs (e.g. `slug + hash(file_path + chunk_index)`).
  - Embed: Embeddings Google Gemini; get vectors.
  - Upsert: Pinecone (namespace = slug). HTTP Request to Pinecone REST if n8n node doesn’t support namespace cleanly.
- **Dependencies:** Backend upload endpoint (reuse upsc-test-engine), Gemini API key, Pinecone API key + index. Sheet only for TA/email (read last row when escalating and for weekly report).
- **Edge cases:** Invalid/empty PDF → reject at upload; extraction failure → email to **ALERT_EMAIL**. Duplicate slug → uniqueness validation rejects or warns.

---

### 3.2 Student WhatsApp interaction

- **Trigger:** Webhook (POST) from Interakt/WATI when a message is received.
- **Requirement:** Respond with 200 quickly (e.g. within 3s); then process (sync or async). **Security:** Verify webhook signature (provider sends a secret; validate before processing) to avoid spoofed requests — see §10.
- **Input:** Webhook body: e.g. `data.message` (text/type), `data.customer` (waId, etc.). For images, provider often gives a message ID or media URL; WATI has `GET .../messages/file/{message_id}` to download media.
- **Logic:**
  - Parse body; extract `query_text`, `is_photo` (type === image), and if photo then media ID/URL for later.
  - Insert into Supabase `query_logs`: `institute_id`, `student_wa_id` (from webhook e.g. `data.customer.waId`), optionally `student_name` (e.g. `data.customer.name` or `senderName`), `timestamp`, `query_text`, `is_photo`, `escalated = false`. Storing `student_wa_id` lets you identify which student queries the most and which student each escalation came from.
  - Resolve namespace: slug from **manual input field** (same as ingestion), with uniqueness validation already done at ingestion.
  - Retrieve: Pinecone query with embedding of `query_text` (same embedding model as ingestion), namespace = slug, top K (e.g. 5–10).
  - Build prompt: system = “You are a helpful Indian coaching teacher… Answer only from context. If context doesn’t answer or unsure, respond with exactly: ESCALATE”; user = context chunks + user query (and if photo: add image part). **Context** = the retrieved chunks from Pinecone (relevant passages from the institute’s uploaded PDF study material).
  - Call Gemini generateContent: if `is_photo` then send image (inline base64) + text; else text only. Model = **gemini-2.5-flash** (Gemini 2.0 deprecated; use 2.5 only).
  - **When the model outputs ESCALATE:** Per the system prompt, the model returns exactly "ESCALATE" when (1) the provided context does **not** contain an answer to the student's question, or (2) the model is **unsure** (e.g. ambiguous question, only partially relevant context, or low confidence). **There is no separate layer** — Gemini itself judges whether it can answer or is unsure; we do not call a separate confidence API or a second model. We rely on the instruction ("If context doesn't answer or unsure, respond with exactly: ESCALATE") and the model's own reasoning to output ESCALATE when appropriate.
  - **ESCALATE check (when and how):** Trigger **immediately after** Gemini’s `generateContent` returns. Logic: take the **raw response text** from Gemini → `normalized = response.trim().toUpperCase()` → if `normalized === "ESCALATE"` then run escalation branch; else treat as the answer and reply to the student. So we only escalate when the model’s **entire** reply is exactly the word ESCALATE (allowing for leading/trailing whitespace and case). Phrases like “I will escalate” or “Answer: ESCALATE” do **not** match and are sent to the student as-is.
  - If response (trimmed/uppercase) === `"ESCALATE"`: set `escalated = true` in DB (update row), get `ta_whatsapp_number` from `institutes` (or sheet). **Reply to the student first** with e.g. "We've escalated your doubt to your TA – they'll get back to you." so they're not left without a reply. Then send WhatsApp to TA with **the full message that led to escalation**: include **who it's from** (e.g. "From: {student_wa_id}" or "From: {student_name}" from the same query_logs row), then student text and student image when present (i.e. the whole WhatsApp message — text and/or photo). So: (1) send the original student text (if any), (2) attach the student’s image (if any) by fetching media from provider and re-sending to TA, so the TA sees exactly what the student sent.
  - Else: reply to student (to `waId`) with Gemini’s answer via provider’s “send message” API.
- **Dependencies:** Supabase (insert/update), Pinecone (query), Gemini (embed + generateContent), WhatsApp provider (send message + media upload for escalation). Sheet read only for escalation path (TA number).
- **Edge cases:**
  - **Photo-only (no text):** If `query_text` is empty, use a placeholder for Pinecone embedding (e.g. "student sent an image") or skip retrieval; decide whether to escalate or send image-only to Gemini with minimal context.
  - **Media URL expiry:** Provider media URLs may expire; fetch and re-upload to TA soon after webhook (don't delay in async flow).
  - Empty or failed Pinecone/Gemini → catch error → optionally escalate or reply “Sorry, try again”; and email **ALERT_EMAIL**.
  - ESCALATE matching: normalize (trim, optional uppercase) and require exact `"ESCALATE"` to avoid false positives.
  - Rate limits (Gemini/WhatsApp) → retry or queue; for pilot, simple retry once may be enough.

---

### 3.3 Weekly insight report

- **Trigger:** **Manual** — run the workflow when you want the report. No schedule; you send the email yourself.
- **Logic:**
  - Query Supabase: `query_logs` where `institute_id = 1` and `timestamp` in last 7 days.
  - Keywords: three arrays (JEE, NEET, UPSC) — **start with placeholders from online research** (e.g. JEE: kinematics, thermodynamics, electrochemistry, chemical bonding; NEET: biology, anatomy, physiology; UPSC: polity, history, geography, economy, environment). Store as JSON in workflow. Count matches in `query_text` (string includes, case-insensitive).
  - Compute: total queries, escalation % (where `escalated = true`), top 5 topics by count. Optionally: **top N students by query count** (GROUP BY `student_wa_id`), and **which students had escalations** (rows where `escalated = true` with `student_wa_id` / `student_name`) so the report shows who queries most and who escalated.
  - **Generate the email body text** (plain-text insight report with the summary above). Optionally include a "To:" line (e.g. from `email_for_report` from sheet last row) so you can copy and paste. **Do not send the email** — output the generated text only; you send the email manually.
- **Dependencies:** Supabase. Sheet (or config) optional for "To:" in the generated text. No email-sending credentials needed.

---

### 3.4 Log cleanup

- **Trigger:** **Manual** — run the workflow when you want to prune old logs. No schedule.
- **Logic:** Delete from `query_logs` where `timestamp` < now − 30 days. Supabase node “Delete” with filter, or raw SQL via Supabase (if supported) / HTTP.

---

## 4. Supabase schema (minimal)

- **Table: `institutes`** (optional but recommended for multi-institute)
  - `id` (int, **auto-generated** — `SERIAL` or `GENERATED BY DEFAULT AS IDENTITY`, PK). Supabase/Postgres generates 1, 2, 3… on INSERT.
  - `slug` (text, unique, not null) — e.g. `fiitjee-kolkata`; used as Pinecone namespace.
  - `email_for_report` (text, nullable) — where to send the weekly insight report (plain-text email). Can be set from sheet or manually; workflows read from here instead of sheet.
  - `ta_whatsapp_number` (text, nullable) — WhatsApp number for TA; used when escalating (send full student message here). Can be set from sheet or manually.
  - Optionally: `created_at` (timestamptz). When adding an institute (e.g. from manual input with uniqueness check), `INSERT INTO institutes (slug, email_for_report, ta_whatsapp_number) VALUES (...) RETURNING id` gives the new `institute_id`. You can sync these from the sheet (e.g. "last row") into `institutes` so workflows read from Supabase instead of the sheet.
- **Table: `uploads`** — track PDF uploads per institute (audit trail, status, link to ingestion).
  - `id` (uuid, default gen_random_uuid(), PK)
  - `institute_id` (int, not null, FK → `institutes.id`)
  - `file_path` (text, nullable) — path or storage key of the uploaded PDF (e.g. in upload_dir or Supabase Storage).
  - `filename` (text, nullable) — original filename.
  - `status` (text, not null, default `'processing'`) — e.g. `processing` | `completed` | `failed`.
  - `created_at` (timestamptz, default now()). Optionally: `completed_at` (timestamptz), `error_message` (text) for failures.
  - After upload (backend saves file), insert a row here; after extraction + Pinecone upsert, update `status = 'completed'` (or `'failed'` and `error_message` on error). Weekly report / ingestion can query by `institute_id` and `created_at`.
- **Table: `query_logs`**
  - `id` (uuid, default gen_random_uuid(), PK)
  - `institute_id` (int, not null, FK → `institutes.id`) — for pilot, use the id returned when you insert the first institute (e.g. 1).
  - `student_wa_id` (text, nullable) — **WhatsApp ID of the student** (from webhook e.g. `data.customer.waId`). Identifies who sent the message. Use this to: (1) **see which student is querying the most** — e.g. `GROUP BY student_wa_id ORDER BY COUNT(*) DESC`; (2) **see which student an escalation came from** — each row has `student_wa_id` and `escalated`; filter `WHERE escalated = true` and you know who escalated. Optional: `student_name` (text) if the provider sends a display name (e.g. `data.customer.name` or `senderName`) for friendlier reports.
  - `timestamp` (timestamptz, default now())
  - `query_text` (text)
  - `is_photo` (boolean, default false)
  - `escalated` (boolean, default false)
  - Optionally: `replied_at` (timestamptz, nullable) or `status` (e.g. `pending` | `replied` | `failed`) — if you process webhooks **async** (return 200 then process later), you need a way to find rows that were never replied to so you can retry or alert. Prefer setting `replied_at = now()` when the reply is successfully sent to the student (or when escalation message is sent to TA).
- **Identifying students:** Store `student_wa_id` (and optionally `student_name`) on every insert from the webhook. Then: "who queries the most?" = aggregate by `student_wa_id`; "who did this escalation come from?" = read `student_wa_id` (and `query_text`) from the same row. When notifying the TA, include "From: {student_wa_id}" or "From: {student_name}" in the message so the TA knows who sent it without opening the DB.
- **Emails:** `email_for_report` and `ta_whatsapp_number` live on `institutes`; no separate emails table. For alerts (e.g. ALERT_EMAIL), keep a single address in n8n env; optional: add `alert_email` (text) to `institutes` if you want per-institute alert targets.
- **RLS:** Enable RLS; e.g. `FOR ALL USING (institute_id = 1)` for pilot so only institute 1 rows are visible when using non–service_role keys. n8n uses **service_role** and bypasses RLS.
- **Auto-generated `institute_id`:** Yes — use an `institutes` table with `id` as `SERIAL` or `IDENTITY`; each new institute gets the next id automatically. For pilot, insert one row and use that id (typically 1) everywhere.

---

## 5. n8n workflow structure (conceptual)

- **Workflow 1 – Ingestion (manual):** **Manual upload** (reuse upsc-test-engine upload) → Backend extraction (text+OCR, same logic as upsc-test-engine) → Code (chunk) → Embeddings Google Gemini → Pinecone upsert. Manual input: institute name/slug (with uniqueness validation). Error branch → email to ALERT_EMAIL.
- **Workflow 2 – WhatsApp:** Webhook → Code (parse body, insert Supabase) → Embeddings Google Gemini (query text) → Pinecone query → Code (build prompt) → HTTP Gemini generateContent (**gemini-2.5-flash**) → IF response === ESCALATE → Supabase update + read Sheet (last row) + WhatsApp send to TA **with full message (student text + student image when present)**; ELSE → WhatsApp send to student.
- **Workflow 3 – Weekly report (manual):** Manual trigger → Supabase get rows (filter last 7 days, institute_id=1) → Code (keyword counts, top 5, escalation %) → **Generate email body text** (insight report). Optionally read Sheet last row for "To: email_for_report". Output = report text only; you send the email manually.
- **Workflow 4 – Cleanup (manual):** Manual trigger → Supabase delete (timestamp < now − 30 days). Run when you want to prune old logs.

Pinecone: if n8n’s Pinecone node does not support “namespace” and “raw upsert” cleanly, use **HTTP Request** to Pinecone Data API (upsert/query with `namespace` in body).

---

## 6. Error handling

- **Failed upload/extraction:** On invalid PDF or extraction failure → send email to **ALERT_EMAIL**. Set `uploads.status = 'failed'` and `error_message` so rows don't stay in `processing`.
- **API failures (Gemini, Pinecone, WhatsApp):** In WhatsApp flow, try/catch; on failure send email to **ALERT_EMAIL** and reply to user “Something went wrong, please try again.”
- **Webhook timeout:** Keep webhook handler minimal (e.g. insert to Supabase + return 200); process in same workflow after response if n8n allows, or use a queue (e.g. “Execute Workflow” trigger) so provider gets 200 quickly. **Recommendation:** Return 200 within ~3s then process async; use `replied_at` and retry unreplied rows (e.g. `replied_at IS NULL` and `created_at` in last 1 hour).

---

## 7. Suggested manual test steps

1. **Ingestion:** Manually upload a PDF (via upload UI/API reused from upsc-test-engine), enter institute name/slug in the manual input field (uniqueness validated). Run extraction + chunk + embed + Pinecone; check Pinecone dashboard for namespace and vector count.
2. **WhatsApp text:** Send a text message to the WhatsApp Business number; confirm reply from Gemini and one new row in `query_logs`.
3. **WhatsApp photo:** Send a photo with a question; confirm reply or escalation; if escalation, confirm TA receives the **full message** (student text + student image as sent).
4. **ESCALATE:** Ask something off-topic or not in the PDF; expect “ESCALATE” path and TA notification.
5. **Weekly report:** Run the weekly report workflow manually; copy the **generated email text** (insight report) and send the email yourself to `email_for_report`. Confirm the report contains total queries, escalation %, top topics.
6. **Cleanup:** Insert an old row (or backdate in DB for test), run cleanup workflow, confirm row deleted.

---

## 8. Ambiguities and questions for you

1. **PDF URL type:** Should we assume “direct” PDF URLs only (e.g. S3, public link that returns `Content-Type: application/pdf`), or do you want support for **Google Drive** “share” links (which often need redirect handling or export format)? If Drive is required, we need a small helper (e.g. replace `/file/d/ID` with export URL) in the workflow.

2. **Webhook response time:** Interakt/WATI expect 200 within ~3s. Full flow (Supabase insert → embed → Pinecone → Gemini → WhatsApp reply) can exceed that. Prefer: (A) webhook only inserts to Supabase and returns 200, then a **separate workflow** (run manually or on a timer, e.g. every 1 min) processes new `query_logs` rows that don’t have a “replied” flag yet; or (B) we accept risk and run the whole flow in the webhook (and hope it’s under 3s for simple queries)? (A) is safer for production.

3. **Embedding model and dimension:** Confirm embedding model (e.g. `gemini-embedding-001`) and **vector dimension** (e.g. 768) so the Pinecone index is created correctly.

4. **Institute slug (resolved):** **Manual input field** for institute name/slug. **Uniqueness validation** (e.g. check Pinecone namespaces or Supabase slugs table) so no duplicate slug.

5. **Alert email (resolved):** **Single address** in n8n env (e.g. `ALERT_EMAIL`). Use for all error/alert emails.

6. **Topic keywords (resolved):** **Start with placeholders from online research** (JEE/NEET/UPSC). Refine later; see §3.3 for example terms.

7. **Provider (resolved):** Use the **provider more popular in India** (research online). Both WATI and Interakt are leading; pick one for pilot and document webhook/API; can switch later.

---

## 9. Phasing (3 steps)

- **Phase 1 – Ingestion + storage:** Supabase schema; **manual upload** (reuse upsc-test-engine upload) → backend text+OCR (same logic as upsc-test-engine) → chunk → embed → Pinecone upsert. Manual input: institute name/slug (uniqueness validation). No WhatsApp yet. Validate: uploaded PDF → Pinecone namespace with vectors.
- **Phase 2 – WhatsApp + RAG:** Webhook workflow: receive message → log to Supabase → Pinecone retrieval → Gemini → reply or escalate (TA number from sheet). Manual test with text and photo.
- **Phase 3 – Reports + cleanup:** Weekly report workflow: **manual run**, generate insight report email text (you send email manually). Cleanup workflow: **manual run** when you want to prune old logs. Error-handling emails.

Once you confirm the open points above, this exploration is enough to implement the pilot step by step.

---

## 10. Risks, security, latency, and customer experience

- **Security**
  - **Webhook spoofing:** The webhook URL is public; anyone could POST and inject fake `query_logs` or trigger flows. **Mitigation:** Verify webhook signature (WATI/Interakt provide a secret and sign payloads; validate before processing). Reject requests with invalid or missing signature.
  - **Secrets:** Keep Supabase **service_role** key, Gemini API key, and WhatsApp provider credentials in n8n env (or a secrets manager). Never commit them or log them.
  - **PII:** `query_logs` contains PII (student_wa_id, student_name, query_text). Restrict access (RLS, service_role only from n8n). Retention: 30-day cleanup is documented; ensure that matches your policy.

- **Latency and timeouts**
  - **Webhook 3s limit:** Full flow (embed → Pinecone → Gemini → send) often exceeds 3s. **Mitigation:** Webhook inserts to Supabase and returns 200; a separate step (manual run or timer) processes and replies. Otherwise the provider may retry (duplicate) or mark delivery failed.
  - **Student wait:** If sync, student may wait 5–15+ seconds with no feedback. Optional: send a quick "Got it, looking that up..." then send the real reply when ready (requires two WhatsApp sends).

- **Crashes and partial failure**
  - **APIs down (Gemini/Pinecone/WhatsApp 5xx):** Retry once; on repeated failure email ALERT_EMAIL and reply "Something went wrong." With async + `replied_at`, unreplied rows can be retried later.
  - **Upload stuck in `processing`:** If extraction crashes after inserting `uploads`, set a timeout or manual step to mark `status = 'failed'` and `error_message` so you don't have orphaned rows.
  - **Wrong reply to wrong student:** In async flow, always pass `student_wa_id` (or query_logs row id) through the pipeline and use it when sending the reply; never rely on "current" context that might have changed.

- **Customer experience**
  - **Escalation:** Student must get a reply when we escalate (e.g. "We've escalated your doubt to your TA – they'll get back to you.") so they're not left wondering. Documented in §3.2.
  - **Photo-only query:** If student sends only an image with no text, define behaviour: placeholder for retrieval, or escalate, or ask for text. Documented in §3.2 edge cases.
  - **Model hallucination:** Gemini might ignore "answer only from context" and invent an answer. For pilot, accept this risk; later you could add a check (e.g. "does the reply cite the context?") or stricter prompt.
