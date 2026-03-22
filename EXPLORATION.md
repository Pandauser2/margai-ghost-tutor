# MargAI Ghost Tutor – 14-day pilot exploration

**Purpose:** Design and context for the bare-minimum pilot. **Implementation:** n8n (Telegram webhook) + Python scripts (ingestion, weekly report, cleanup); see [RUN.md](RUN.md) and [PLAN.md](PLAN.md).

**Doc map (kept in sync with code):** [MULTI-INSTITUTE-ONBOARDING.md](docs/MULTI-INSTITUTE-ONBOARDING.md) (many tenants), [PINECONE_NAMESPACE.md](docs/PINECONE_NAMESPACE.md) (index + namespace), [PRODUCTION-DEPLOYMENT-PLAN.md](docs/PRODUCTION-DEPLOYMENT-PLAN.md), [RAG-FAITHFULNESS-TRACKER.md](docs/RAG-FAITHFULNESS-TRACKER.md) (RAG quality).

---

## 1. Codebase and context

- **Pilot implementation** in this repo: **n8n** hosts the Telegram webhook. Workflow exports:
  - **`n8n-workflows/v6.json`** — full production-style flow. Embed node: **`modelName`:** `models/gemini-embedding-001`, **`dimensions`: 3072** (aligned with `lib/embedding.py` + Pinecone).
  - **`n8n-workflows/telegram-webhook.json`** — slimmer reference workflow (may differ on `topK`, credentials shape).
  **Python scripts:** ingestion (`scripts/ingest_pdf.py`), weekly report (`scripts/weekly_report.py`), log cleanup (`scripts/cleanup_logs.py`). No Vercel.
- **Reusable context in repo:**
  - `upsc-test-engine/` provides **PDF extraction** (pdfplumber, PyMuPDF, OCR via `pdf_extraction_service.py`). Ingestion runs from repo root and **reuses** `extract_hybrid()` when available.
  - **Chunking** (`lib/chunking.py`): target **1000** chars, overlap **200**, paragraph/section-aware splits (not a single naive fixed window).
  - Supabase (`institutes`, `uploads`, `query_logs`), Pinecone (**one shared index**, **namespace = string `institute_id`**), Gemini (**embedding 3072-dim** + **gemini-2.5-flash** for RAG in n8n).

**Conclusion:** Pilot: **Telegram** for students; **manual PDF ingestion** (teacher sends PDFs via Drive/WhatsApp → you run `ingest_pdf.py` to process and upsert to Pinecone with `namespace = institute_id`; see §5.2). **n8n** hosts the webhook; **scripts** handle ingestion, report, cleanup. Supabase (`institutes`, `uploads`, `query_logs`), Pinecone (one namespace per institute). Contact info (`email_for_report`, `ta_telegram_id`) in `institutes`. WhatsApp in Month 2 (§5.4).

---

## 2. Stack integration summary

| Component | Role in pilot | Notes |
|-----------|----------------|--------|
| **n8n** | Hosts the **Telegram webhook** (`v6.json` or `telegram-webhook.json`): receives updates → **Set `institute_id` + parse** → RAG (**LangChain** embed → Pinecone retriever → **Question and Answer** chain → Gemini Chat). Replies or clarify / escalate. **Pilot:** `institute_id` is **hardcoded** in the Set node (e.g. `1`), not derived from `chat_id` lookup. Uses **service role** for Supabase; credentials in n8n. | Import workflow; map every credential on target instance. Multi-institute: see [MULTI-INSTITUTE-ONBOARDING.md](docs/MULTI-INSTITUTE-ONBOARDING.md). |
| **Supabase** | Tables: `institutes`, `uploads`, `query_logs`. Webhook + scripts use **service role** (bypasses RLS). | RLS e.g. `institute_id = 1` for pilot if anon key ever used. |
| **Pinecone serverless** | Index e.g. **`margai-ghost-tutor-v2`**, dimension **3072** (must match `lib/embedding.py`). **Namespace = `str(institute_id)`** only (numeric id from Supabase, not slug string). | Same index for all institutes; namespaces isolate vectors. |
| **Telegram** | **Pilot:** One bot. Inbound → webhook; outbound → Bot API (`sendMessage` / `getFile`). | Multi-bot production: one bot per institute recommended (same doc above). |
| **Google Gemini** | (1) **Embedding:** `models/gemini-embedding-001`, **`output_dimensionality=3072`** (`lib/embedding.py`; ingestion + n8n embed node must match). (2) **Chat:** **gemini-2.5-flash** via n8n LangChain Gemini Chat sub-node. | **n8n UI** does not expose a **system message** on Gemini Chat; strict “context-only” prompt is **deferred** (see [RAG-FAITHFULNESS-TRACKER.md](docs/RAG-FAITHFULNESS-TRACKER.md) Task 2). Retrieval QA chain still supplies context + question. |

---

## 3. Flow-by-flow breakdown

### 3.1 PDF ingestion

- **Trigger:** **Manual** — run `scripts/ingest_pdf.py` when you have a PDF to ingest (e.g. after teacher sends via Drive/WhatsApp). No sheet; you pass PDF path and institute slug. See RUN.md.
- **Input:** (1) **PDF:** Local path to the PDF (teacher sends file; you save it and pass path to the script). (2) **Institute:** Institute slug or `institute_id` (script maps to Pinecone namespace). Uniqueness: ensure institute exists in Supabase `institutes`; namespace = `institute_id`. (3) Contact info (`email_for_report`, `ta_telegram_id`) lives in `institutes` table, not a sheet.
- **Logic:**
  - **Slug:** From manual input field (institute name → lowercase, spaces/special chars → hyphen). Validate uniqueness before upserting.
  - **Extract text + OCR:** Use **same detection logic as upsc-test-engine** (both native text and OCR). Latency is not an issue (backend). Reference: `upsc-test-engine/backend/app/services/pdf_extraction_service.py` — `extract_hybrid()`, constants, and `_should_run_ocr_for_page`:
    - **Native text:** PyMuPDF blocks + pdfplumber layout; per-page mojibake fix.
    - **OCR trigger per page:** native text &lt; threshold (e.g. 100 chars) OR garbled heuristics (Latin-1 supplement ratio, first-2-pages header threshold, garbled-pattern count). Doc-level: if total native text &lt; 5000 chars, treat as image-heavy → OCR all pages.
    - **OCR:** Tesseract hin+eng, OpenCV preprocessing (gray, adaptive threshold, denoise), ftfy, noise-line filter. Parallel OCR for pages that need it. Merge: use OCR when OCR length ≥ native × 0.8 or OCR &gt; native.
  - **Pilot:** The ingestion script runs from repo root and calls `extract_hybrid()` from upsc-test-engine when available (same logic as `pdf_extraction_service.py`).
  - Chunk: **`lib/chunking.py`** — `CHUNK_SIZE=1000`, `OVERLAP=200`, section/paragraph-aware; stable IDs (`prefix + hash(...)`).
  - Embed: Gemini via `lib/embedding.py` — **3072** dimensions (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`).
  - Upsert: Pinecone with **`namespace=str(institute_id)`**; vector metadata includes `text`, `source_file`, `source_slug`, `chunk_id`.
- **Dependencies:** Gemini API key, Pinecone API key + index, Supabase. TA/email from `institutes` table.
- **Edge cases:** Invalid/empty PDF → reject at upload; extraction failure → email to **ALERT_EMAIL**. Duplicate slug → uniqueness validation rejects or warns.

---

### 3.2 Student Telegram interaction (pilot)

- **Trigger:** **Telegram webhook** (n8n) when a message is received (14-day pilot uses Telegram; WhatsApp in Month 2 — see §5.4).
- **Requirement:** Respond quickly; then process (sync or async). **Security:** Validate Telegram secret token in webhook to avoid spoofed requests — see §10.
- **Input:** Telegram update: `message.from.id` (user ID), `message.chat.id` (chat ID for replies), `message.text`, `message.photo` (array; use file_id to download via getFile). For images, use Bot API `getFile` to download media.
- **Logic:**
  - Parse body; extract `query_text`, `is_photo` (type === image), and if photo then media ID/URL for later.
  - Insert into Supabase `query_logs`: `institute_id`, `student_telegram_id` (from `message.from.id` or `message.chat.id`), optionally `student_name` (from `message.from.first_name`), `timestamp`, `query_text`, `is_photo`, `escalated = false`. Storing `student_telegram_id` lets you identify which student queries the most and which student each escalation came from.
  - Resolve namespace: use `institute_id` (backend identifies which bot/institute this chat belongs to; see §5.1). Namespace = `institute_id` for Pinecone query.
  - Retrieve: Pinecone query with embedding of `query_text` (**same 3072-dim model/dims as ingestion**), `namespace = str(institute_id)`. **Retriever `topK`:** e.g. **30** in `n8n-workflows/v6.json`, **12** in `telegram-webhook.json` (tune per faithfulness/latency).
  - **Prompting in n8n:** Implemented as **LangChain Question and Answer** + **Gemini Chat** sub-node. There is **no** configurable system message in the Gemini Chat **UI** today; behavior follows the chain’s default QA template + model. **Target behavior** (Knowledge-lock, exact **ESCALATE**) remains as in §5.3 / §3.2 for product intent; optional future: HTTP Gemini with `systemInstruction`, or custom prompt node. **Context** = retrieved chunks; multimodal if photo path enabled.
  - Call Gemini (via chain): model **gemini-2.5-flash** where configured.
  - **When the model outputs ESCALATE (design intent):** The model should return exactly **ESCALATE** when (1) the provided context does **not** contain an answer, or (2) it is **unsure**. **No separate confidence API** — relies on prompt/chain + model behavior. With the current n8n setup (no system message in UI), achieving strict ESCALATE discipline may require a future **custom prompt** or **HTTP Gemini** path; see [RAG-FAITHFULNESS-TRACKER.md](docs/RAG-FAITHFULNESS-TRACKER.md).
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

- **Trigger:** **Manual** — run `scripts/weekly_report.py` when you want the report. No schedule; you send the email yourself (script outputs report text).
- **Logic:**
  - Query Supabase: `query_logs` where `institute_id` = chosen id (default **1**; override with `python scripts/weekly_report.py --institute-id N`) and `timestamp` in last 7 days.
  - Keywords: three arrays (JEE, NEET, UPSC) — **start with placeholders from online research** (e.g. JEE: kinematics, thermodynamics, electrochemistry, chemical bonding; NEET: biology, anatomy, physiology; UPSC: polity, history, geography, economy, environment). Store as JSON in the script or config. Count matches in `query_text` (string includes, case-insensitive).
  - Compute: total queries, escalation % (where `escalated = true`), top 5 topics by count. Optionally: **top N students by query count** (GROUP BY `student_telegram_id`), and **which students had escalations** (rows where `escalated = true` with `student_telegram_id` / `student_name`) so the report shows who queries most and who escalated.
  - **Generate the email body text** (plain-text insight report with the summary above). Optionally include a "To:" line (e.g. from `email_for_report` from sheet last row) so you can copy and paste. **Do not send the email** — output the generated text only; you send the email manually.
- **Dependencies:** Supabase. "To:" from `institutes.email_for_report`. No email-sending credentials in the script; you send the email manually.

---

### 3.4 Log cleanup

- **Trigger:** **Manual** — run `scripts/cleanup_logs.py` when you want to prune old logs. No schedule.
- **Logic:** Delete from `query_logs` where `timestamp` < now − 30 days. Script uses Supabase client (see `scripts/cleanup_logs.py`).

---

## 4. Supabase schema (minimal)

- **Table: `institutes`** (optional but recommended for multi-institute)
  - `id` (int, **auto-generated** — `SERIAL` or `GENERATED BY DEFAULT AS IDENTITY`, PK). Supabase/Postgres generates 1, 2, 3… on INSERT.
  - `slug` (text, unique, not null) — e.g. `fiitjee-kolkata`; used by **ingest** to resolve **`institute_id`**. **Pinecone namespace** = **`str(institute_id)`**, not the slug string.
  - `email_for_report` (text, nullable) — where to send the weekly insight report (plain-text email). Can be set from sheet or manually; scripts and webhook read from here (not a sheet).
  - `ta_telegram_id` (text, nullable) — **Pilot:** Telegram user/chat ID for TA; used when escalating (send full student message here). Month 2: add `ta_whatsapp_number` when offering WhatsApp.
  - Optionally: `created_at` (timestamptz). When adding an institute, `INSERT INTO institutes (slug, email_for_report, ta_telegram_id) VALUES (...) RETURNING id` gives the new `institute_id`. You can sync these from the sheet (e.g. "last row") into `institutes` so scripts read from Supabase (no sheet).
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
- **Emails:** `email_for_report` and `ta_telegram_id` (pilot) live on `institutes`; no separate emails table. For alerts (e.g. ALERT_EMAIL), keep a single address in env (e.g. `ALERT_EMAIL`); optional: add `alert_email` (text) to `institutes` if you want per-institute alert targets.
- **RLS:** Enable RLS; e.g. `FOR ALL USING (institute_id = 1)` for pilot so only institute 1 rows are visible when using non–service_role keys. Webhook and scripts use **service_role** and bypass RLS.
- **Auto-generated `institute_id`:** Yes — use an `institutes` table with `id` as `SERIAL` or `IDENTITY`; each new institute gets the next id automatically. For pilot, insert one row and use that id (typically 1) everywhere.

---

## 5. Pilot implementation (n8n + scripts)

- **Ingestion:** Run `scripts/ingest_pdf.py` with PDF path and institute slug. Script uses `extract_hybrid()` (from upsc-test-engine when available) → chunk → embed (`lib/embedding.py`) → Pinecone upsert (`namespace = institute_id`). On error, alert (e.g. ALERT_EMAIL).
- **Telegram:** **n8n** hosts the webhook (`v6.json` or `telegram-webhook.json`). Flow: optional secret_token → parse → escalate-intent branch if needed → insert `query_logs` → embed (**3072-dim**) → Pinecone (`namespace=str(institute_id)`) → **LangChain Retrieval QA** + **Gemini Chat** → normalize answer → if **ESCALATE** then clarifying path; else reply. See §3.2 for prompt/UI limits.
- **Weekly report:** Run `scripts/weekly_report.py`. Script reads Supabase (last 7 days, institute_id), computes keyword counts, escalation %, top topics, optional top students → outputs email body text; you send the email manually. "To:" from `institutes.email_for_report`.
- **Cleanup:** Run `scripts/cleanup_logs.py`. Deletes `query_logs` where `timestamp` < now − 30 days.

Pinecone: use `namespace = institute_id` for all upserts and queries (ingestion script and n8n webhook).

---

### 5.1 Multi-tenancy (multiple coaching centers)

- **Mechanism:** Pinecone **namespaces**. Each coaching center has a unique `institute_id` in Supabase.
- **Upsert:** Pinecone `namespace=str(institute_id)` only (matches `ingest_pdf.py` + n8n expression `String($json.institute_id)`).
- **Query:** When a Telegram message comes in, the backend identifies **which bot/institute** the conversation belongs to (e.g. bot token, or deep link / start parameter). It then queries Pinecone **only in that institute's namespace**. Institute A never sees Institute B's data.
- **RLS:** Supabase RLS by `institute_id` adds defense in depth for any non–service_role access.

---

### 5.2 Teacher onboarding

- **MVP (14-day pilot) – High-touch for you, low-touch for them:**
  1. Teacher sends you their PDFs via **Google Drive** or **WhatsApp**.
  2. You (founder) run a **script** to process and upload them to that institute's **Pinecone namespace** (extract → chunk → embed → upsert with `namespace = institute_id`).
  3. You provide the teacher with a **Telegram Bot link** (e.g. @MargAI_Success_Bot) to share with students.
- **Scale (V2):** A simple **dashboard** where teachers drag-and-drop files; a backend (n8n or similar) automatically triggers the embedding pipeline and upserts to the correct namespace.

---

### 5.3 Knowledge-lock (strict content, flexible tone)

- **Rule:** **Strict for content, flexible for tone** — product intent for answers and **ESCALATE** behavior (§3.2).
- **Implementation note:** n8n **Gemini Chat** node has **no system-message field** in the UI; the exported workflow uses **`options: {}`**. Enforcing Knowledge-lock in production may require **HTTP Request → Gemini API** (`systemInstruction`), a **custom prompt** node, or a future n8n release. Track experiments in [RAG-FAITHFULNESS-TRACKER.md](docs/RAG-FAITHFULNESS-TRACKER.md).
- **Reference wording (for future prompts):** *Use ONLY the provided context… If not in context, respond with exactly: ESCALATE* (then workflow runs clarify → escalate path).
- **Exception (intent):** General English/Math **logic** to explain steps already in context is OK; **no new facts** outside context.

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
- **Webhook timeout:** Keep webhook handler minimal (e.g. insert to Supabase + return 200); process in same request or use a queue (e.g. “Execute Workflow” trigger) so provider gets 200 quickly. **Recommendation:** Return 200 within ~3s then process async; use `replied_at` and retry unreplied rows (e.g. `replied_at IS NULL` and `created_at` in last 1 hour).

---

## 7. Suggested manual test steps

1. **Ingestion:** Run `scripts/ingest_pdf.py` with a PDF path and institute slug (see RUN.md). Check Pinecone dashboard for namespace and vector count.
2. **Telegram text:** Send a text message to the Telegram bot; confirm reply from Gemini and one new row in `query_logs`.
3. **Telegram photo:** Send a photo with a question; confirm reply or escalation; if escalation, confirm TA receives the **full message** (student text + student image as sent) via Telegram.
4. **Clarify then escalate:** Ask something off-topic or not in the PDF; expect clarifying question first (e.g. add more detail or reply escalate). Reply with "escalate"; then expect escalation confirmation and TA receiving full message (From: student, text/image).
5. **Weekly report:** Run `scripts/weekly_report.py`; copy the **generated email text** and send it yourself to `email_for_report`. Confirm the report contains total queries, escalation %, top topics.
6. **Cleanup:** Insert an old row (or backdate in DB for test), run `scripts/cleanup_logs.py`, confirm row deleted.

---

## 8. Ambiguities and questions for you

1. **PDF URL type:** Should we assume “direct” PDF URLs only (e.g. S3, public link that returns `Content-Type: application/pdf`), or do you want support for **Google Drive** “share” links (which often need redirect handling or export format)? If Drive is required, we need a small helper (e.g. replace `/file/d/ID` with export URL) in the ingestion script.

2. **Webhook response time:** Telegram allows a few seconds. Full flow (Supabase insert → embed → Pinecone → Gemini → Telegram reply) can exceed that. Prefer: (A) webhook only inserts to Supabase and returns 200, then a **separate process** (e.g. run manually or on a timer, e.g. every 1 min) processes new `query_logs` rows that don’t have a “replied” flag yet; or (B) we accept risk and run the whole flow in the webhook (and hope it’s under 3s for simple queries)? (A) is safer for production.

3. **Embedding model and dimension (resolved):** **`models/gemini-embedding-001`**, **`output_dimensionality=3072`** in `lib/embedding.py`. Pinecone index **`margai-ghost-tutor-v2`** (or your name) must be **3072** cosine; n8n embed node must match ingestion.

4. **Institute slug (resolved):** **Manual input field** for institute name/slug. **Uniqueness validation** (e.g. check Pinecone namespaces or Supabase slugs table) so no duplicate slug.

5. **Alert email (resolved):** **Single address** in env (e.g. `ALERT_EMAIL`). Use for all error/alert emails.

6. **Topic keywords (resolved):** **Start with placeholders from online research** (JEE/NEET/UPSC). Refine later; see §3.3 for example terms.

7. **Channel (resolved):** **Telegram first** for 14-day pilot (§5.4). Use success stories to sell **WhatsApp API** (e.g. WATI/Interakt) in Month 2.

---

## 9. Phasing (3 steps)

- **Phase 1 – Ingestion + storage:** Supabase schema; **manual upload** (or script from teacher's Drive/WhatsApp PDFs; see §5.2) → backend text+OCR → chunk → embed → Pinecone upsert (namespace = institute_id). Manual input: institute name/slug (uniqueness validation). No Telegram bot yet. Validate: uploaded PDF → Pinecone namespace with vectors.
- **Phase 2 – Telegram + RAG (pilot):** Webhook (n8n; verify secret_token): receive Telegram message → log to Supabase → Pinecone retrieval (namespace = institute_id) → Gemini (Knowledge-lock prompt §5.3) → reply or clarify → escalate (reply to student, then notify TA via Telegram from `institutes.ta_telegram_id`). Manual test with text and photo.
- **Phase 3 – Reports + cleanup:** Weekly report script: **manual run** (`scripts/weekly_report.py`), generate insight report email text (you send email manually). Cleanup script: **manual run** (`scripts/cleanup_logs.py`) when you want to prune old logs. Error-handling emails.

**§8.3 embedding dimension:** resolved in code (3072). Remaining §8 items (e.g. async webhook, Drive URLs) are still product choices.

---

## 10. Risks, security, latency, and customer experience

- **Security**
  - **Webhook spoofing:** The webhook URL is public; anyone could POST and inject fake `query_logs` or trigger flows. **Mitigation:** Verify Telegram webhook secret_token (validate before processing). For WhatsApp in Month 2, use provider signature verification (WATI/Interakt). Reject requests with invalid or missing signature.
  - **Secrets:** Keep Supabase **service_role** key, Gemini API key, and Telegram bot token (pilot; WhatsApp credentials in Month 2) in env / n8n credentials (or a secrets manager). Never commit them or log them.
  - **PII:** `query_logs` contains PII (student_telegram_id, student_name, query_text). Restrict access (RLS, service_role only from webhook/scripts). Retention: 30-day cleanup is documented; ensure that matches your policy.

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

  - **Latency:** If the reply path runs on n8n (or similar), end-to-end time includes Supabase + Pinecone + Gemini. For a student expecting an instant answer on Telegram, a 5+ second delay feels like a bug. **Logging:** Log request duration (e.g. time from webhook received to reply sent); alert or inspect when duration exceeds a threshold (e.g. 5s) to spot slow patterns.
  - **Parsing messy PDFs:** The current plan uses text + OCR (e.g. pdfplumber, PyMuPDF, Tesseract). Coaching notes are often **tables, diagrams, or handwritten scans**; basic PDF parsers can fail or produce poor text. **Fallback fix:** Consider **LlamaParse** or **Unstructured.io** for better table/formula extraction if extraction quality becomes a problem. **Logging:** Log extraction outcomes per upload (e.g. total chars extracted, page count, per-page char counts, or extraction errors); low char counts or repeated failures can signal messy PDFs that need a better parser.
