# Production deployment plan (Ghost Tutor pilot)

This doc follows a **code review** of `margai-ghost-tutor-pilot/` (Python, workflows, docs) and lists steps to push **safely** to production (n8n Cloud + Telegram + Supabase/Pinecone/Gemini used by the flow).

---

## Code review (2026-03-22 scope)

**Scope:** `margai-ghost-tutor-pilot/lib/*.py`, `scripts/*.py`, `n8n-workflows/*.json`, `.env.example`, `.gitignore`, `RUN.md` / tracker docs.  
**Not in scope:** `upsc-test-engine` (ingest dependency). **Canonical n8n export:** `margai-ghost-tutor-pilot/n8n-workflows/v6.json`.

### Looks good

- **Logging:** `ingest_pdf.py` uses `logging` with structured messages (extraction outcome, institute_id, errors); no stray `print` in the ingest hot path.
- **Error handling:** Ingest wraps the main pipeline in `try/except`, updates Supabase `uploads` to `failed` with `error_message`, and uses early exits with clear `logger.error` for missing env / bad PDF / short text.
- **Secrets:** `.env` and `.env.*` are gitignored; `.env.example` documents keys without values. API keys flow from env/settings, not hardcoded in Python.
- **Embedding resilience:** `lib/embedding.py` retries on 429 with backoff and spacing between batch calls.
- **Config:** `pydantic_settings` centralizes env loading with `extra = "ignore"`.

### Issues found

| Severity | Location | Issue | Suggested fix |
|----------|----------|--------|----------------|
| **MEDIUM** | `scripts/pinecone_retrieval_audit.py`, `test_ingest_local.py`, `cleanup_logs.py`, `weekly_report.py` | CLI tools use `print` to stdout/stderr | Acceptable for CLIs; optional: use `logging` + `--quiet` for consistency with `ingest_pdf.py`. |
| **MEDIUM** | `n8n-workflows/v6.json` (and exports) | Credential **IDs** are instance-specific (`googlePalmApi.id`, etc.) | On import into **your** n8n, re-bind every credential; document in runbook. Not secrets, but breaks copy-paste between instances. |
| **LOW** | `ingest_pdf.py` | Auto-creates `institutes` row if slug missing | Fine for pilot; for stricter prod, require pre-provisioned institute or admin-only creation. |
| **LOW** | Tracker / Phase A | Strict Gemini `systemMessage` removed (n8n UI limitation) | Documented in `RAG-FAITHFULNESS-TRACKER.md` Task 2; revisit via HTTP Gemini + `systemInstruction` or prompt template if faithfulness regressions appear. |

### Review summary

| Metric | Count |
|--------|-------|
| Files reviewed (pilot) | ~15 core artifacts |
| Critical issues | 0 |
| Warnings | 2 (CLI prints; n8n credential binding) |

**TypeScript / React / RLS:** Not applicable to this Python + n8n pilot; validate Supabase **RLS** and API exposure in Supabase dashboard separately for production.

---

## Production push plan

Execute in order; stop and roll back if any **gate** fails.

### Phase 0 — Preconditions

- [ ] **Branch clean:** intended changes committed; no accidental `.env` or `__pycache__` in git (`git status`).
- [ ] **Canonical workflow:** Import from `margai-ghost-tutor-pilot/n8n-workflows/v6.json` (or your saved export); keep one source of truth.
- [ ] **Secrets inventory:** n8n credentials for Supabase, Pinecone, Google Gemini, Telegram, SMTP (if used) all exist on **production** n8n instance with **production** keys.
- [ ] **Index alignment:** Pinecone index name in workflow matches prod index (e.g. `margai-ghost-tutor-v2`); embedding model/dims match index (3072 / `gemini-embedding-001` per `lib/embedding.py`).

### Phase 1 — Git / artifacts

- [ ] Push pilot repo (or monorepo path) to remote; tag optional e.g. `ghost-tutor-pilot-v0.x`.
- [ ] Update `CHANGELOG.md` **Unreleased** with this deploy note before tag (if you version releases).

### Phase 2 — n8n (production)

- [ ] **Import** workflow JSON into **production** n8n (or overwrite existing workflow from canonical file).
- [ ] **Re-map credentials** on every node that needs them (imports carry IDs that may not exist on prod).
- [ ] **Webhook:** Confirm Telegram (or reverse proxy) points to the **production** webhook URL and path matches the Webhook node (`webhookId` / path as configured).
- [ ] **Activate** workflow; confirm no duplicate active workflows listening on the same Telegram webhook path.
- [ ] **Gate:** Manual **Execute workflow** with a test payload (or test Telegram message) → expect logged row in Supabase + Telegram reply.

### Phase 3 — Ingestion / data plane (if deploying new content)

- [ ] On a **trusted runner** (CI or admin laptop), set `.env` with **production** Supabase + Pinecone + Gemini (or use service-specific keys with least privilege where possible).
- [ ] Run `scripts/ingest_pdf.py` for each new PDF; verify `uploads.status = completed` and spot-check Pinecone namespace = `institute_id`.
- [ ] **Gate:** Run `scripts/pinecone_retrieval_audit.py` for 1–2 representative queries; confirm top-k sources look sane.

### Phase 4 — Smoke tests (production)

- [ ] **Happy path:** Telegram question with known answer in corpus → coherent answer.
- [ ] **ESCALATE path:** Question outside material → clarifying / ESCALATE branch behaves as designed.
- [ ] **Photo path** (if used): small image → pipeline completes or fails gracefully with user-visible message.
- [ ] **Failure alert** (if configured): trigger controlled failure → email or log visible.

### Phase 5 — Rollback

- [ ] Keep **previous** workflow export JSON and n8n **version history** (or duplicate inactive workflow) for one-click restore.
- [ ] If RAG quality drops: revert workflow; optionally adjust `topK` only after measuring (see `RAG-FAITHFULNESS-TRACKER.md`).

### Phase 6 — Post-deploy

- [ ] Note deploy time + git SHA in internal doc or Linear.
- [ ] Schedule or run `scripts/weekly_report.py` / monitoring as needed.
- [ ] Revisit **Task 2** (strict answering) if hallucinations or cross-PDF bleed recur.

### Multi-tenant production (second+ institute)

When onboarding **more than one** coaching center, do **not** fork the whole workflow unless required for compliance. Follow **[`docs/MULTI-INSTITUTE-ONBOARDING.md`](MULTI-INSTITUTE-ONBOARDING.md)**:

- [ ] Add **institute** row in Supabase; ingest PDFs with `ingest_pdf.py … <institute_slug>` (namespace = new `id`).
- [ ] **Telegram:** new BotFather bot + webhook pointing at a **dedicated path** (or router) that sets the correct **`institute_id`** in n8n.
- [ ] **n8n:** wire **per-bot Telegram credentials** (or secure token lookup); verify Pinecone **`pineconeNamespace`** uses `String($json.institute_id)` for **every** branch.
- [ ] **RLS / reports:** move beyond `institute_id = 1` pilot policies; scope weekly reports per tenant.
- [ ] **Gate:** retrieval audit + manual chat test **per** new institute before go-live.

---

## Quick reference

| Component | Where configured |
|-----------|------------------|
| Telegram → n8n | BotFather token; webhook URL → n8n Webhook node |
| RAG | n8n: Pinecone + Retrieval QA + Gemini Chat |
| Ingest | `margai-ghost-tutor-pilot/.env` + `scripts/ingest_pdf.py` |
| Multi-institute | **`docs/MULTI-INSTITUTE-ONBOARDING.md`** (bots, webhooks, namespaces) |
| Design narrative | **`EXPLORATION.md`** (stack, flows, risks — sync with code) |
| Docs | `RUN.md`, `RAG-FAITHFULNESS-TRACKER.md` (includes §12 incident playbook), `PINECONE_NAMESPACE.md` |
