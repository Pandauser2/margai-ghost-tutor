# P2 diagnostic — raw Pinecone retrieval (no Gemini)

**Goal:** See exactly what Pinecone returns for a query **before** any LLM.  
**Decision gate:**
- Box 4.3 (or target) **missing** in top‑k → fix retrieval (topK, filters, chunking).
- Box 4.3 **present** but answer still adds facts → fix prompt / model compliance.

**Constraints:** This path does **not** change n8n prompts, `topK`, or chunking code.

---

## Option A — Python script (recommended)

Same embedding model and index as ingestion (`lib/embedding.py`, env from `lib/config.py`).

From repo root (or `margai-ghost-tutor-pilot/`):

```bash
cd margai-ghost-tutor-pilot
source .venv/bin/activate
set -a && source .env && set +a

python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10
```

- `--namespace` = Pinecone namespace string (usually `institute_id`, e.g. `1`).
- `--top-k` = match n8n retriever if you want (e.g. `30`).
- `--json` = full JSON for saving / diffing.

**Metadata note:** Ingest stores `text`, `source_file`, `source_slug`, `chunk_id`. There is **no `page`** in current metadata unless you add it later.

---

## Option B — n8n sub-workflow (manual)

1. Duplicate workflow or new workflow.
2. **Webhook** (POST) with body e.g. `{ "query": "...", "institute_id": 1 }`.
3. **Set** — map `query_text`, `institute_id`.
4. **Embed query (Gemini)** — `models/gemini-embedding-001` (same as prod).
5. **Pinecone** — retrieve only, same index + `pineconeNamespace` = `String(institute_id)`.
6. **Respond to Webhook** — return Pinecone JSON (or **Code** node: format top 10 with scores).

Do **not** connect **Question and Answer Chain** or **Gemini Chat**.

---

## What to check manually

For cotton farmers / Box 4.3:

- Chunk text includes **Box 4.3** heading or equivalent cotton-farmer distress passage.
- Seven scholar-listed causes appear **in the retrieved text**, not only in the model answer.

Then apply the decision gate above.
