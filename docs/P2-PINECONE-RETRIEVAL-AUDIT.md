# P2 Diagnostic: Raw Pinecone Retrieval Audit (No Gemini QA)

## Context

P2 is a retrieval-only checkpoint used to isolate whether failures are caused by:
1) Pinecone retrieval quality, or
2) QA model behavior after retrieval.

This diagnostic bypasses Gemini answer generation and inspects raw Pinecone matches directly.

---

## Goal

For a given query, verify whether target source content appears in raw top-k retrieval before any QA processing.

---

## Decision Gate

- If target content is **missing** in raw top-k -> retrieval-side issue (topK/filter/chunking/metadata).
- If target content is **present** but final answer overreaches -> QA prompt/model compliance issue.

---

## How to Run

### Script path
`scripts/pinecone_retrieval_audit.py`

### Command
```bash
cd margai-ghost-tutor-pilot
source .venv/bin/activate
set -a && source .env && set +a

python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10
```

### Optional JSON export
```bash
python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10 \
  --json > /tmp/p2.json
```

---

## What to Inspect in Output

- Rank
- Similarity score
- Chunk id
- Source metadata (`source_file`, `source_slug`, `chunk_id`)
- Text preview

Check whether target content (for this case: Box 4.3 material and seven-cause evidence) is present among top results.

---

## Latest Recorded Result (2026-03-21)

Run configuration:
- `EMBED_MODEL = models/gemini-embedding-001`
- `INDEX = margai-ghost-tutor-v2`
- `NAMESPACE = 1`
- `TOP_K = 10`

Findings:
- Ranks 1-4: relevant Box 4.3 content appears.
- Ranks 5-6: contaminating adjacent-section content appears (Anantpur/fertiliser-subsidy style).

Conclusion:
- Retrieval is not fully missing target content.
- Mixed context is entering QA; prompt/model compliance must be controlled.
