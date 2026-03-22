# Pinecone: namespace, setup, and retrieval audit

**Multi-institute:** One shared index + **one namespace per `institute_id`**. Telegram/n8n routing: [MULTI-INSTITUTE-ONBOARDING.md](MULTI-INSTITUTE-ONBOARDING.md).

This file replaces the former **`PINECONE_FROM_ZERO.md`** (setup tutorial) and **`P2-PINECONE-RETRIEVAL-AUDIT.md`** (diagnostic) — one place for Pinecone.

---

## Index and metric

- **Serverless** index, dimension **3072** (for `gemini-embedding-001`), metric **cosine**.
- **Name:** **`margai-ghost-tutor-v2`** — match `PINECONE_INDEX_NAME` in `.env` (do not reuse old index names from 768-dim era).

---

## Namespace convention

- **One namespace per institute.** Use `institute_id` from Supabase `institutes.id` as the namespace **string** (e.g. `"1"`), not the slug.
- **Upsert:** `namespace=str(institute_id)` on ingest.
- **Query:** Same namespace after resolving `institute_id` for the request.

---

## Python examples

```python
# Upsert after ingestion
index.upsert(vectors=vectors, namespace=str(institute_id))

# Query when replying to student
results = index.query(vector=query_embedding, top_k=10, namespace=str(institute_id))
```

---

## Setup from zero (first-time)

*Formerly `PINECONE_FROM_ZERO.md`.*

This app uses Pinecone to store **embeddings** of PDF text so RAG can find relevant chunks. You need an account, API key, and one index.

### 1. Account and API key

1. Sign up at [pinecone.io](https://www.pinecone.io).
2. Console → **API Keys** → create a key; copy it.
3. In `margai-ghost-tutor-pilot/.env`:

```env
PINECONE_API_KEY=your-copied-key-here
PINECONE_INDEX_NAME=margai-ghost-tutor-v2
```

### 2. Create the index

**Option A — Dashboard (easiest)**  
Indexes → Create index → name **`margai-ghost-tutor-v2`**, dimensions **3072**, metric **Cosine**, serverless (e.g. AWS `us-east-1`). Wait until **Ready**.

**Option B — Python**

```bash
cd margai-ghost-tutor-pilot
pip install "pinecone>=5.0.0"
export $(grep -v '^#' .env | xargs)   # macOS/Linux
python3 -c "
from pinecone import Pinecone, ServerlessSpec
import os
key = os.environ.get('PINECONE_API_KEY')
assert key, 'PINECONE_API_KEY not set'
pc = Pinecone(api_key=key)
pc.create_index(
    name='margai-ghost-tutor-v2',
    dimension=3072,
    metric='cosine',
    spec=ServerlessSpec(cloud='aws', region='us-east-1'),
)
print('Index created; wait until Ready in console.')
"
```

### 3. Why 3072 and cosine?

Gemini `gemini-embedding-001` outputs **3072** dimensions; the index must match. **Cosine** matches how similarity is used in retrieval.

### 4. Checklist

- [ ] API key in `.env`
- [ ] `PINECONE_INDEX_NAME=margai-ghost-tutor-v2`
- [ ] Index **Ready** with **3072** / **cosine** / serverless

Continue with Telegram in [RUN.md](../RUN.md).

---

## P2 diagnostic: raw retrieval audit (no Gemini QA)

*Formerly `P2-PINECONE-RETRIEVAL-AUDIT.md`.*

**Purpose:** Decide if a failure is **retrieval** (wrong/missing chunks) vs **QA** (model overreach after good retrieval).

**Gate:** Target content **missing** in raw top-k → retrieval work (`topK`, chunking, metadata). Target content **present** but answer bad → QA / prompt / `topK` exposure.

### Run

`scripts/pinecone_retrieval_audit.py`

```bash
cd margai-ghost-tutor-pilot
source .venv/bin/activate
set -a && source .env && set +a

python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10
```

JSON export:

```bash
python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10 \
  --json > /tmp/p2.json
```

### Inspect output

Rank, score, chunk id, metadata (`source_file`, `source_slug`, `chunk_id`), text preview.

### Recorded example (2026-03-21)

- Index `margai-ghost-tutor-v2`, namespace `1`, top_k 10.
- Ranks 1–4: Box 4.3–relevant material.
- Ranks 5–6: adjacent-section contamination.
- **Conclusion:** Mixed context reaches QA; control prompt/compliance and/or `topK`.

---

## Related

- [RAG-FAITHFULNESS-TRACKER.md](RAG-FAITHFULNESS-TRACKER.md) — gates, tasks, **incident playbook** (§12).
- [RUN.md](../RUN.md) — full pilot steps.
