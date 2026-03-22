# Telegram Ghost Tutor Webhook (n8n)

## Workflow: Telegram Ghost Tutor Webhook

Implements PLAN.md Step 4 + 5: receive Telegram updates → log to Supabase → RAG (embed → Pinecone → Gemini) → reply or clarify → escalate.

### Node list (order)

1. **Webhook** – POST `/webhook`. For secret_token: in n8n Webhook node use **Header Auth** (header name `X-Telegram-Bot-Api-Secret-Token`, value = `TELEGRAM_WEBHOOK_SECRET` from env), or add an IF node after Webhook that checks the header and responds 403 if missing/wrong.
2. **Set institute_id and parse** – `institute_id = 1`; parse `student_telegram_id`, `student_name`, `query_text`, `is_photo`, `chat_id`, `photo_file_id` from `body.message`.
3. **IF escalate intent** – `message.text` (lowercase) contains `"escalate"`. True → handle escalate (see below). False → continue to 4.
4. **Supabase Insert query_logs** – Insert row (institute_id, student_telegram_id, student_name, query_text, is_photo, escalated=false).
5. **IF photo** – True → HTTP Request Telegram `getFile`, then merge with context. False → continue.
6. **Merge** – Combine branches so one item has `query_text` (and optional file_path).
7. **Embed query (Gemini)** – Model `gemini-embedding-001` (dimension 3072; must match Pinecone index).
8. **Pinecone query** – Index from env (e.g. `margai-ghost-tutor-v2`), **namespace** `String(institute_id)`, **dimension 3072** (must match ingest). **Retriever `topK`:** `12` in this JSON; **`v6.json`** uses `30` — tune per latency/faithfulness.
9. **Gemini Chat** – gemini-2.5-flash; system prompt: answer only from context; if unsure reply exactly ESCALATE; multimodal if photo.
10. **IF response == ESCALATE** – Normalize response (trim, uppercase); equals "ESCALATE".
    - **True** → Telegram send clarifying message → Supabase update that row `clarification_sent=true` → Respond to Webhook 200.
    - **False** → Telegram reply with answer → Respond to Webhook 200.
11. **Respond to Webhook** – Return 200, body `{"ok":true}`.
12. **Email ALERT_EMAIL** – On error path (or Error Trigger subflow), send email to `ALERT_EMAIL`.

### Escalate-intent branch (when student sends "escalate")

- Supabase: get last row where `student_telegram_id` = current and `clarification_sent = true`.
- Supabase: update that row `escalated = true`.
- Telegram: send to student "We've escalated your doubt to your TA – they'll get back to you."
- Telegram: send to TA (`institutes.ta_telegram_id`) full thread (From: student, text + image).
- Respond to Webhook 200.

### Credentials (create in n8n)

- **Supabase** – URL + service_role key.
- **Google Gemini API** – API key (for embed + chat).
- **Pinecone** – API key (and index name in env).
- **Telegram API** – Bot token.
- **SMTP** – For ALERT_EMAIL.

### Env / config

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `GEMINI_API_KEY`, `ALERT_EMAIL`.

---

## Test steps

1. **Set webhook URL in BotFather / Telegram**
   - Use your n8n webhook URL: `https://<your-n8n-host>/webhook/<webhook-path>` (or the Production Webhook URL shown in the n8n Webhook node).
   - Optional: set `secret_token` to match `TELEGRAM_WEBHOOK_SECRET` in n8n env.

2. **Send a test message**
   - Open the bot in Telegram; send a short text question that is covered by your ingested PDF (namespace `1`).
   - Expect: bot replies with an answer from context.

3. **Test ESCALATE**
   - Send a question that is not in the PDF or is ambiguous.
   - Expect: bot sends the clarifying message (“Could you add more detail… reply **escalate** to send to your TA”).
   - Reply with `escalate`.
   - Expect: “We've escalated your doubt to your TA”; TA receives the full thread (if `ta_telegram_id` is set).

4. **Test photo (optional)**
   - Send a photo with a caption; confirm bot uses context + image if your flow supports multimodal.

5. **Check Supabase**
   - `query_logs` has new rows; after clarify, `clarification_sent = true`; after escalate, `escalated = true`.

### Validation (after implementation)

- **Confirm Pinecone returns matches (length > 0):** For a query that should hit ingested content, the retriever/Pinecone step should return at least one match.
- **Confirm matches contain `metadata.text`:** Retriever output (or chain context) should have each match with `metadata.text` containing chunk content.
- **Confirm QA chain returns non-empty answer:** For a question covered by the ingested PDF, the chain output should be non-empty (and not only "ESCALATE" when context is present).
- **Confirm no dimension mismatch errors:** No "Vector dimension X does not match index dimension Y" in n8n or ingestion logs.

### Many institutes (same workflow)

Pilot hardcodes **`institute_id = 1`**. For **second+ institutes**, keep **this** RAG chain — add **webhook branches** (or Supabase `chat_id` lookup) and **per-bot Telegram credentials**. See **`docs/MULTI-INSTITUTE-ONBOARDING.md`** (Mermaid diagrams + checklist).
