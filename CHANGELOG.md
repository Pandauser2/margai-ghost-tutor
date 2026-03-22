# Changelog

## Unreleased

### Added
- **docs/README.md** — Index of `docs/*.md` roles; clarifies institute = tenant, single canonical onboarding doc.
- **docs/MULTI-INSTITUTE-ONBOARDING.md** — Merged former `MULTI-TENANT-PLAN-PROPOSAL.md` into § **Implementation backlog** (one doc, less redundancy).

### Changed
- **Docs consolidation:** `PINECONE_FROM_ZERO.md` + `P2-PINECONE-RETRIEVAL-AUDIT.md` merged into **`docs/PINECONE_NAMESPACE.md`** (setup + P2 §). `RAG-INCIDENT-PLAYBOOK.md` merged into **`docs/RAG-FAITHFULNESS-TRACKER.md` §12**. Updated `RUN.md`, `PRODUCTION-DEPLOYMENT-PLAN.md`, `docs/README.md`.
- **docs/MULTI-INSTITUTE-ONBOARDING.md** — Canonical multi-tenant plan (rewritten): executive Q&A, Mermaid diagrams (data plane, multi-bot n8n, shared-bot sequence, decision tree), onboarding + hardening. Linked from `PLAN.md`, `README.md`, `RUN.md`, `PRODUCTION-DEPLOYMENT-PLAN.md`, `PINECONE_NAMESPACE.md`.
- **docs/RAG-FAITHFULNESS-TRACKER.md** — Track RAG “context-only” failures (answers mixing other sections / general knowledge), fix phases, golden tests, change log.
- **n8n:** `n8n-workflows/telegram-webhook.json` + `README-telegram-webhook.md` — Telegram Ghost Tutor webhook: Supabase log, Gemini + Pinecone RAG, clarify→escalate path.

### Changed
- **n8n-workflows/v6.json:** Embed query (Gemini) parameters include **`dimensions`: 3072** alongside `modelName` (match `telegram-webhook.json` + `lib/embedding.py`).
- **Docs:** Architecture sync — `EXPLORATION.md` (3072, index name, workflows, chunking, namespace=`str(institute_id)`, pilot routing, n8n Gemini UI limits), `PLAN.md` (Pinecone 3072 + RAG step wording), `README.md` / `PRODUCTION-DEPLOYMENT-PLAN.md` / `MULTI-INSTITUTE-ONBOARDING.md` cross-links, `n8n-workflows/README-telegram-webhook.md` (topK/dim), `RAG-3072-FIX-PLAN.md` **rewritten** as current-state reference (removed stale 768 “current setup” tables), `COMMUNITY-NODES-EMBEDDING.md` (legacy note). **CHANGELOG Notes:** canonical `n8n-workflows/v6.json`; embed dimension verification.
- **Embedding (`lib/embedding.py`):** `models/gemini-embedding-001`, `output_dimensionality=3072` — must match Pinecone index (e.g. `margai-ghost-tutor-v2`).
- **Config (`lib/config.py`):** Default `pinecone_index_name` = `margai-ghost-tutor-v2`.
- **Pinecone (`lib/pinecone_client.py`):** Upsert in batches (`UPSERT_BATCH_SIZE=80`) to stay under ~4MB request limit.
- **Ingest (`scripts/ingest_pdf.py`):** Vector metadata includes `text`, `source_file`, `source_slug`, `chunk_id`; namespace = `str(institute_id)` from Supabase.
- **Chunking (`lib/chunking.py`):** Section/paragraph-oriented splitting + overlap (see module docstring).
- **RUN.md:** n8n import + Telegram wiring; Python deps documented (no root `requirements.txt` in pilot).

### Fixed
- **Embedding:** Retry on 429 with exponential backoff; small delay between batch embed calls.
- **Ingest:** Clearer error hint when `GEMINI_API_KEY` is rejected.

### Removed
- **docs/VERCEL_STEP_BY_STEP.md** — Vercel + Telegram webhook path (webhook on n8n now).
- **scripts/push_env_to_vercel.sh** — No longer used.

### Notes (verify in n8n UI)
- **Canonical workflow export:** `n8n-workflows/v6.json` (and slimmer `telegram-webhook.json`). **Gemini Chat:** no `systemMessage` in exports (n8n UI does not expose it; strict prompting deferred — see `docs/RAG-FAITHFULNESS-TRACKER.md` Task 2).
