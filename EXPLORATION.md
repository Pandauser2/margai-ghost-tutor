# MargAI Ghost Tutor – 14-day pilot exploration

**Purpose:** Understand and plan the bare-minimum pilot. No implementation yet.

---

## 1. Codebase and context

- **No existing MargAI/Ghost Tutor code** in this repo. The pilot is greenfield.
- **Reusable context in repo:**
  - `upsc-test-engine/` uses **Gemini** (REST + SDK), **PDF upload** (POST, save to `upload_dir`), and **PDF extraction** (pdfplumber, PyMuPDF, OCR via `pdf_extraction_service.py`). For MargAI we **reuse the upload system** (manual PDF upload; no sheet/download). Orchestration: n8n + serverless; we reuse concepts (chunk size, system prompt, “answer from context only”) not the code.
  - `create_kolkata_salary_presentation.py` and similar scripts show Python/script usage in the workspace; no direct reuse for n8n.

**Conclusion:** Pilot: **Telegram** for students; **manual PDF ingestion** (teacher sends PDFs via Drive/WhatsApp → you run script to process and upsert to Pinecone with `namespace = institute_id`; see §5.2). n8n workflows, Supabase (`institutes`, `uploads`, `query_logs`), Pinecone (one namespace per institute). Contact info (`email_for_report`, `ta_telegram_id`) in `institutes`. WhatsApp in Month 2 (§5.4).

---

## 2. Stack integration summary

| Component | Role in pilot | Notes |
|-----------|----------------|--------|
| **n8n (self-hosted)** | Orchestration: **manual PDF upload** (reuse upsc-test-engine upload) → backend extraction (text+OCR) → chunk → embed → Pinecone; webhook, Supabase, email. No sheet for PDF. | Ingestion: user **manually uploads** PDF; no "read sheet → download PDF". **No cron/scheduled triggers** — ingestion, weekly report, and log cleanup are all manual (run when you want). |
| **Supabase** | Tables: `institutes`, `uploads`, `query_logs`. No auth/dashboard. n8n uses **service role** key (bypasses RLS). | RLS with `institute_id = 1` for defense in depth if anon key is ever used. |
| **Pinecone serverless** | One **namespace per institute** = `institute_id` (or slug). Create index with dimension matching embedding model (e.g. **768**). | **Multi-tenancy:** Upsert with `namespace: institute_id`. Backend identifies which bot/institute a message belongs to and queries **only that namespace**. Institute A never sees Institute B data. |
| **Telegram** | **14-day pilot:** One bot (e.g. @MargAI_Success_Bot). Inbound → webhook or long polling; outbound → Bot API. | Free, ~5 min setup. Use pilot for success stories; pivot to **WhatsApp API** (paid) in Month 2. |
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

### 3.2 Student Telegram interaction (pilot)

- **Trigger:** Telegram webhook or long polling when a message is received (14-day pilot uses Telegram; WhatsApp in Month 2 — see §5.4).
- **Requirement:** Respond quickly; then process (sync or async). **Security:** Validate Telegram secret token in webhook to avoid spoofed requests — see §10.
- **Input:** Telegram update: `message.from.id` (user ID), `message.chat.id` (chat ID for replies), `message.text`, `message.photo` (array; use file_id to download via getFile). For images, use Bot API `getFile` to download media.
- **Logic:**
  - Parse body; extract `query_text`, `is_photo` (type === image), and if photo then media ID/URL for later.
  - Insert into Supabase `query_logs`: `institute_id`, `student_telegram_id` (from `message.from.id` or `message.chat.id`), optionally `student_name` (from `message.from.first_name`), `timestamp`, `query_text`, `is_photo`, `escalated = false`. Storing `student_telegram_id` lets you identify which student queries the most and which student each escalation came from.
  - Resolve namespace: use `institute_id` (backend identifies which bot/institute this chat belongs to; see §5.1). Namespace = `institute_id` for Pinecone query.
  - Retrieve: Pinecone query with embedding of `query_text` (same embedding model as ingestion), namespace = institute_id, top K (e.g. 5–10).
  - Build prompt: system = “You are a helpful Indian coaching teacher… Answer only from context. If context doesn’t answer or unsure, respond with exactly: ESCALATE”; user = context chunks + user query (and if photo: add image part). **Context** = the retrieved chunks from Pinecone (relevant passages from the institute’s uploaded PDF study material). Use **Knowledge-lock** from §5.3: strict for content (e.g. "This wasn't covered… I've flagged this for your teacher!" or ESCALATE); flexible for tone; allow general logic to explain steps, never new facts.
  - Call Gemini generateContent: if `is_photo` then send image (inline base64) + text; else text only. Model = **gemini-2.5-flash** (Gemini 2.0 deprecated; use 2.5 only).
  - **When the model outputs ESCALATE:** Per the system prompt, the model returns exactly "ESCALATE" when (1) the provided context does **not** contain an answer to the student's question, or (2) the model is **unsure** (e.g. ambiguous question, only partially relevant context, or low confidence). **There is no separate layer** — Gemini itself judges whether it can answer or is unsure; we do not call a separate confidence API or a second model. We rely on the instruction ("If context doesn't answer or unsure, respond with exactly: ESCALATE") and the model's own reasoning to output ESCALATE when appropriate.
  - **ESCALATE check (when and how):** Trigger **immediately after** Gemini’s `generateContent` returns. Logic: take the **raw response text** from Gemini → `normalized = response.trim().toUpperCase()` → if `normalized === "ESCALATE"` then run clarifying-question branch (see below); else treat as the answer and reply to the student. So we only escalate when the model’s **entire** reply is exactly the word ESCALATE (allowing for leading/trailing whitespace and case). Phrases like “I will escalate” or “Answer: ESCALATE” do **not** match and are sent to the student as-is.
  - **Clarifying question before escalation:** When the model returns ESCALATE (or when retrieval is empty/no relevant chunks), **do not escalate immediately**. First send the student a **single clarifying message**, e.g. "I couldn't find a clear answer in your study material. Could you add a bit more detail (e.g. chapter or topic) or rephrase? If you'd prefer to send this to your TA, reply with **escalate**." Mark the `query_logs` row with `clarification_sent = true` (optional column) and do **not** set `escalated = true` or notify the TA. When the **next** message from the same `student_telegram_id` arrives: (1) If the new message text (normalized, e.g. trim + lowercase) is an explicit escalate intent (e.g. "escalate", "send to ta", "forward to ta"), then treat it as escalation: set `escalated = true` on the **previous** query_logs row (the one that had clarification_sent = true), reply to the student "We've escalated your doubt to your TA…", and send the TA the **original** doubt (text + image from that previous row). (2) Otherwise treat the new message as a **fresh query** (new row, full RAG again). So escalation happens only after at least one clarifying question, unless the student explicitly asks to escalate.
  - If after clarification the student asks to escalate (or we get ESCALATE again on a follow-up): set `escalated = true` in DB (on the relevant row), get `ta_telegram_id` from `institutes` (pilot; WhatsApp in Month 2). **Reply to the student first** with e.g. "We've escalated your doubt to your TA – they'll get back to you." Then send **Telegram** message to TA with **the full message that led to escalation**: include **who it's from** (e.g. "From: {student_telegram_id}" or "From: {student_name}" from the same query_logs row), then student text and student image when present (i.e. the whole WhatsApp message — text and/or photo). So: (1) send the original student text (if any), (2) attach the student’s image (if any) by fetching media from provider and re-sending to TA, so the TA sees exactly what the student sent.
  - Else: reply to student (to `chat_id`) with Gemini’s answer via provider’s “send message” API.
- **Dependencies:** Supabase (insert/update), Pinecone (query), Gemini (embed + generateContent), **Telegram Bot API** (send message + send photo for escalation). TA from `institutes.ta_telegram_id` (pilot).
- **Edge cases:**
  - **Photo-only (no text):** If `query_text` is empty, use a placeholder for Pinecone embedding (e.g. "student sent an image") or skip retrieval; decide whether to escalate or send image-only to Gemini with minimal context.
  - **Media URL expiry:** Provider media URLs may expire; fetch and re-upload to TA soon after webhook (don't delay in async flow).
  - Empty or failed Pinecone/Gemini → catch error → optionally send clarifying message or reply “Sorry, try again”; and email **ALERT_EMAIL**.
  - **Empty or weak retrieval:** When Pinecone returns no or very few relevant chunks, use the same **clarifying question** as for ESCALATE (ask for more detail or offer "reply escalate to send to your TA") instead of escalating immediately.
  - ESCALATE matching: normalize (trim, optional uppercase) and require exact `"ESCALATE"` to avoid false positives.
  - Rate limits (Gemini/Telegram) → retry or queue; for pilot, simple retry once may be enough.

---

### 3.3 Weekly insight report

- **Trigger:** **Manual** — run the workflow when you want the report. No schedule; you send the email yourself.
- **Logic:**
  - Query Supabase: `query_logs` where `institute_id = 1` and `timestamp` in last 7 days.
  - Keywords: three arrays (JEE, NEET, UPSC) — **start with placeholders from online research** (e.g. JEE: kinematics, thermodynamics, electrochemistry, chemical bonding; NEET: biology, anatomy, physiology; UPSC: polity, history, geography, economy, environment). Store as JSON in workflow. Count matches in `query_text` (string includes, case-insensitive).
  - Compute: total queries, escalation % (where `escalated = true`), top 5 topics by count. Optionally: **top N students by query count** (GROUP BY `student_telegram_id`), and **which students had escalations** (rows where `escalated = true` with `student_telegram_id` / `student_name`) so the report shows who queries most and who escalated.
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
  - `ta_telegram_id` (text, nullable) — **Pilot:** Telegram user/chat ID for TA; used when escalating (send full student message here). Month 2: add `ta_whatsapp_number` when offering WhatsApp.
  - Optionally: `created_at` (timestamptz). When adding an institute, `INSERT INTO institutes (slug, email_for_report, ta_telegram_id) VALUES (...) RETURNING id` gives the new `institute_id`. You can sync these from the sheet (e.g. "last row") into `institutes` so workflows read from Supabase instead of the sheet.
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
  - `student_telegram_id` (text, nullable) — **Pilot:** Telegram user/chat ID (from `message.from.id` or `message.chat.id`). Identifies who sent the message. Use to: (1) **see which student is querying the most** — e.g. `GROUP BY student_telegram_id ORDER BY COUNT(*) DESC`; (2) **see which student an escalation came from** — filter `WHERE escalated = true`. Optional: `student_name` (text) from `message.from.first_name` for friendlier reports.
  - `timestamp` (timestamptz, default now())
  - `query_text` (text)
  - `is_photo` (boolean, default false)
  - `escalated` (boolean, default false)
  - Optionally: `clarification_sent` (boolean, default false) — set true when we send the "clarifying question" after ESCALATE; used to know which row to escalate when the student later replies "escalate".
  - Optionally: `replied_at` (timestamptz, nullable) or `status` (e.g. `pending` | `replied` | `failed`) — if you process webhooks **async** (return 200 then process later), you need a way to find rows that were never replied to so you can retry or alert. Prefer setting `replied_at = now()` when the reply is successfully sent to the student (or when escalation message is sent to TA).
- **Identifying students:** Store `student_telegram_id` (and optionally `student_name`) on every insert from the Telegram webhook. Then: "who queries the most?" = aggregate by `student_telegram_id`; "who did this escalation come from?" = read `student_telegram_id` (and `query_text`) from the same row. When notifying the TA, include "From: {student_telegram_id}" or "From: {student_name}" in the message.
- **Emails:** `email_for_report` and `ta_telegram_id` (pilot) live on `institutes`; no separate emails table. For alerts (e.g. ALERT_EMAIL), keep a single address in n8n env; optional: add `alert_email` (text) to `institutes` if you want per-institute alert targets.
- **RLS:** Enable RLS; e.g. `FOR ALL USING (institute_id = 1)` for pilot so only institute 1 rows are visible when using non–service_role keys. n8n uses **service_role** and bypasses RLS.
- **Auto-generated `institute_id`:** Yes — use an `institutes` table with `id` as `SERIAL` or `IDENTITY`; each new institute gets the next id automatically. For pilot, insert one row and use that id (typically 1) everywhere.

---

## 5. n8n workflow structure (conceptual)

- **Workflow 1 – Ingestion (manual):** **Manual upload** (reuse upsc-test-engine upload) → Backend extraction (text+OCR, same logic as upsc-test-engine) → Code (chunk) → Embeddings Google Gemini → Pinecone upsert. Manual input: institute name/slug (with uniqueness validation). Error branch → email to ALERT_EMAIL.
- **Workflow 2 – Telegram (pilot):** Webhook (verify secret_token) → Code (parse update; if incoming text is "escalate" and there is a recent row for this student with `clarification_sent = true`, treat as escalate that row → Supabase update + reply to student + notify TA via Telegram) → else insert Supabase → Embeddings Google Gemini (query text) → Pinecone query (namespace = institute_id) → Code (build prompt; Knowledge-lock §5.3) → HTTP Gemini generateContent (**gemini-2.5-flash**) → IF response === ESCALATE → send **clarifying question** to student (set `clarification_sent = true`); ELSE IF student previously asked to escalate → reply "We've escalated…" + get `ta_telegram_id` from `institutes` + Telegram to TA with full message; ELSE → Telegram sendMessage answer to student.
- **Workflow 3 – Weekly report (manual):** Manual trigger → Supabase get rows (filter last 7 days, institute_id=1) → Code (keyword counts, top 5, escalation %, optional top students / who escalated) → **Generate email body text** (insight report). Optionally "To:" from `institutes.email_for_report` or sheet. Output = report text only; you send the email manually.
- **Workflow 4 – Cleanup (manual):** Manual trigger → Supabase delete (timestamp < now − 30 days). Run when you want to prune old logs.

Pinecone: use `namespace = institute_id` when upserting/querying. If the n8n Pinecone node does not support namespace and raw upsert cleanly, use **HTTP Request** to Pinecone Data API (upsert/query with `namespace` in body).

---

### 5.1 Multi-tenancy (multiple coaching centers)

- **Mechanism:** Pinecone **namespaces**. Each coaching center has a unique `institute_id` in Supabase.
- **Upsert:** When processing PDFs for an institute, specify Pinecone `namespace: institute_id` (or a stable slug). All vectors for that institute live in that namespace.
- **Query:** When a Telegram message comes in, the backend identifies **which bot/institute** the conversation belongs to (e.g. bot token, or deep link / start parameter). It then queries Pinecone **only in that institute's namespace**. Institute A never sees Institute B's data.
- **RLS:** Supabase RLS by `institute_id` adds defense in depth for any non–service_role access.

---

### 5.2 Teacher onboarding

- **MVP (14-day pilot) – High-touch for you, low-touch for them:**
  1. Teacher sends you their PDFs via **Google Drive** or **WhatsApp**.
  2. You (founder) run a **script** to process and upload them to that institute's **Pinecone namespace** (extract → chunk → embed → upsert with `namespace = institute_id`).
  3. You provide the teacher with a **Telegram Bot link** (e.g. @MargAI_Success_Bot) to share with students.
- **Scale (V2):** A simple **dashboard** where teachers drag-and-drop files; a **Vercel** (or similar) backend automatically triggers the embedding pipeline and upserts to the correct namespace.

---

### 5.3 Knowledge-lock (strict content, flexible tone)

- **Rule:** **Strict for content, flexible for tone.**
- **System prompt (core):** *"You are an assistant for [Institute Name]. Use ONLY the provided context to answer. If the answer is not in the context, do not make it up. Instead, say: 'This wasn't covered in our current notes. I've flagged this for your teacher!'"*
- **Exception:** Allow the LLM to use **general English/Math logic** to explain the teacher's steps more clearly (e.g. rephrasing, breaking into steps). **Never** introduce new outside facts or content not in the provided context.
- In the pilot flow, "flagged for your teacher" ties into the existing **clarify → escalate** path (e.g. student can reply "escalate" to send to TA).

---

### 5.4 Telegram vs WhatsApp

- **Decision:** **Telegram first** for the 14-day pilot.
- **Reasoning:** You can spin up a Telegram bot in ~5 minutes for free. Use the pilot to collect **success stories** (e.g. "Our AI solved 500 doubts in 2 days").
- **Pivot:** Use those success stories to convince the institute owner to **pay for WhatsApp API setup** in Month 2 (e.g. Interakt/WATI).

---

### 5.5 V3 evaluation (vision-to-JSON) – future

- **Approach:** **Vision-to-JSON** for handwritten-answer evaluation.
- **Flow:** The student takes a photo of their handwritten answer. You send it to **gpt-4o** or **gemini-1.5-pro** along with the teacher's **Model Answer PDF**.
- **Output:** The AI does not just give a mark; it generates a **Comparison Table**, e.g.:
  - **Teacher's key point:** e.g. "Mention the 1857 Revolt."
  - **Student's answer:** e.g. "Mentioned, but missed the date."
  - **AI feedback:** e.g. "You got the concept, but accuracy on dates is needed for WBCS/UPSC."

---

## 6. Error handling

- **Failed upload/extraction:** On invalid PDF or extraction failure → send email to **ALERT_EMAIL**. Set `uploads.status = 'failed'` and `error_message` so rows don't stay in `processing`.
- **API failures (Gemini, Pinecone, Telegram):** In Telegram flow, try/catch; on failure send email to **ALERT_EMAIL** and reply to user “Something went wrong, please try again.”
- **Webhook timeout:** Keep webhook handler minimal (e.g. insert to Supabase + return 200); process in same workflow after response if n8n allows, or use a queue (e.g. “Execute Workflow” trigger) so provider gets 200 quickly. **Recommendation:** Return 200 within ~3s then process async; use `replied_at` and retry unreplied rows (e.g. `replied_at IS NULL` and `created_at` in last 1 hour).

---

## 7. Suggested manual test steps

1. **Ingestion:** Manually upload a PDF (via upload UI/API reused from upsc-test-engine), enter institute name/slug in the manual input field (uniqueness validated). Run extraction + chunk + embed + Pinecone; check Pinecone dashboard for namespace and vector count.
2. **Telegram text:** Send a text message to the Telegram bot; confirm reply from Gemini and one new row in `query_logs`.
3. **Telegram photo:** Send a photo with a question; confirm reply or escalation; if escalation, confirm TA receives the **full message** (student text + student image as sent) via Telegram.
4. **Clarify then escalate:** Ask something off-topic or not in the PDF; expect clarifying question first (e.g. add more detail or reply escalate). Reply with "escalate"; then expect escalation confirmation and TA receiving full message (From: student, text/image).
5. **Weekly report:** Run the weekly report workflow manually; copy the **generated email text** (insight report) and send the email yourself to `email_for_report`. Confirm the report contains total queries, escalation %, top topics.
6. **Cleanup:** Insert an old row (or backdate in DB for test), run cleanup workflow, confirm row deleted.

---

## 8. Ambiguities and questions for you

1. **PDF URL type:** Should we assume “direct” PDF URLs only (e.g. S3, public link that returns `Content-Type: application/pdf`), or do you want support for **Google Drive** “share” links (which often need redirect handling or export format)? If Drive is required, we need a small helper (e.g. replace `/file/d/ID` with export URL) in the workflow.

2. **Webhook response time:** Telegram allows a few seconds. Full flow (Supabase insert → embed → Pinecone → Gemini → Telegram reply) can exceed that. Prefer: (A) webhook only inserts to Supabase and returns 200, then a **separate workflow** (run manually or on a timer, e.g. every 1 min) processes new `query_logs` rows that don’t have a “replied” flag yet; or (B) we accept risk and run the whole flow in the webhook (and hope it’s under 3s for simple queries)? (A) is safer for production.

3. **Embedding model and dimension:** Confirm embedding model (e.g. `gemini-embedding-001`) and **vector dimension** (e.g. 768) so the Pinecone index is created correctly.

4. **Institute slug (resolved):** **Manual input field** for institute name/slug. **Uniqueness validation** (e.g. check Pinecone namespaces or Supabase slugs table) so no duplicate slug.

5. **Alert email (resolved):** **Single address** in n8n env (e.g. `ALERT_EMAIL`). Use for all error/alert emails.

6. **Topic keywords (resolved):** **Start with placeholders from online research** (JEE/NEET/UPSC). Refine later; see §3.3 for example terms.

7. **Channel (resolved):** **Telegram first** for 14-day pilot (§5.4). Use success stories to sell **WhatsApp API** (e.g. WATI/Interakt) in Month 2.

---

## 9. Phasing (3 steps)

- **Phase 1 – Ingestion + storage:** Supabase schema; **manual upload** (or script from teacher's Drive/WhatsApp PDFs; see §5.2) → backend text+OCR → chunk → embed → Pinecone upsert (namespace = institute_id). Manual input: institute name/slug (uniqueness validation). No Telegram bot yet. Validate: uploaded PDF → Pinecone namespace with vectors.
- **Phase 2 – Telegram + RAG (pilot):** Webhook workflow (verify secret_token): receive Telegram message → log to Supabase → Pinecone retrieval (namespace = institute_id) → Gemini (Knowledge-lock prompt §5.3) → reply or clarify → escalate (reply to student, then notify TA via Telegram from `institutes.ta_telegram_id`). Manual test with text and photo.
- **Phase 3 – Reports + cleanup:** Weekly report workflow: **manual run**, generate insight report email text (you send email manually). Cleanup workflow: **manual run** when you want to prune old logs. Error-handling emails.

Once you confirm the open points above, this exploration is enough to implement the pilot step by step.

---

## 10. Risks, security, latency, and customer experience

- **Security**
  - **Webhook spoofing:** The webhook URL is public; anyone could POST and inject fake `query_logs` or trigger flows. **Mitigation:** Verify Telegram webhook secret_token (validate before processing). For WhatsApp in Month 2, use provider signature verification (WATI/Interakt). Reject requests with invalid or missing signature.
  - **Secrets:** Keep Supabase **service_role** key, Gemini API key, and Telegram bot token (pilot; WhatsApp credentials in Month 2) in n8n env (or a secrets manager). Never commit them or log them.
  - **PII:** `query_logs` contains PII (student_telegram_id, student_name, query_text). Restrict access (RLS, service_role only from n8n). Retention: 30-day cleanup is documented; ensure that matches your policy.

- **Latency and timeouts**
  - **Webhook 3s limit:** Full flow (embed → Pinecone → Gemini → send) often exceeds 3s. **Mitigation:** Webhook inserts to Supabase and returns 200; a separate step (manual run or timer) processes and replies. Otherwise the provider may retry (duplicate) or mark delivery failed.
  - **Student wait:** If sync, student may wait 5–15+ seconds with no feedback. Optional: send a quick "Got it, looking that up..." then send the real reply when ready (requires two Telegram sends).

- **Crashes and partial failure**
  - **APIs down (Gemini/Pinecone/Telegram 5xx):** Retry once; on repeated failure email ALERT_EMAIL and reply "Something went wrong." With async + `replied_at`, unreplied rows can be retried later.
  - **Upload stuck in `processing`:** If extraction crashes after inserting `uploads`, set a timeout or manual step to mark `status = 'failed'` and `error_message` so you don't have orphaned rows.
  - **Wrong reply to wrong student:** In async flow, always pass `student_telegram_id` (or query_logs row id) through the pipeline and use it when sending the reply; never rely on "current" context that might have changed.

- **Customer experience**
  - **Escalation:** Student must get a reply when we escalate (e.g. "We've escalated your doubt to your TA – they'll get back to you.") so they're not left wondering. Documented in §3.2.
  - **Photo-only query:** If student sends only an image with no text, define behaviour: placeholder for retrieval, or escalate, or ask for text. Documented in §3.2 edge cases.
  - **Model hallucination:** Gemini might ignore "answer only from context" and invent an answer. For pilot, accept this risk; later you could add a check (e.g. "does the reply cite the context?") or stricter prompt.

- **What to watch out for (fallback mitigations — do not change the plan now)**  
  These are known risks to monitor. Keep the current plan as-is; treat the following as **fallback** options if issues show up. **Add logs where possible** to detect when they occur (not a hard requirement).

  - **Cold start latency:** If the reply path runs on Vercel (or similar) serverless, functions can "sleep" when idle. For a student expecting an instant answer on Telegram, a 5+ second delay feels like a bug. **Fallback fix:** Use Vercel's **Edge** runtime where possible to reduce cold starts. **Logging:** Log request duration (e.g. time from webhook received to reply sent); alert or inspect when duration exceeds a threshold (e.g. 5s) to spot cold-start patterns.
  - **Parsing messy PDFs:** The current plan uses text + OCR (e.g. pdfplumber, PyMuPDF, Tesseract). Coaching notes are often **tables, diagrams, or handwritten scans**; basic PDF parsers can fail or produce poor text. **Fallback fix:** Consider **LlamaParse** or **Unstructured.io** for better table/formula extraction if extraction quality becomes a problem. **Logging:** Log extraction outcomes per upload (e.g. total chars extracted, page count, per-page char counts, or extraction errors); low char counts or repeated failures can signal messy PDFs that need a better parser.
