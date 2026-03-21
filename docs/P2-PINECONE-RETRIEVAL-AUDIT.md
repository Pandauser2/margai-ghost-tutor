# P2 diagnostic — raw Pinecone retrieval (no Gemini)

**Goal:** Inspect Pinecone output before QA model generation.

Decision gate:
- Target content missing in top-k -> retrieval issue (topK/filter/chunking).
- Target content present but final answer still overreaches -> prompt/model compliance issue.

---

## Run (script)

```bash
cd margai-ghost-tutor-pilot
source .venv/bin/activate
set -a && source .env && set +a

python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10
```

Optional machine-readable output:

```bash
python scripts/pinecone_retrieval_audit.py --query "..." --namespace 1 --top-k 10 --json > /tmp/p2.json
```

---

## Latest recorded run (2026-03-21)

- `EMBED_MODEL = models/gemini-embedding-001`
- `INDEX = margai-ghost-tutor-v2`
- `NAMESPACE = 1`
- `TOP_K = 10`

Observed:
- Ranks 1-4 include Box 4.3-relevant chunks.
- Ranks 5-6 include contaminating adjacent-section chunks (e.g., Anantpur/fertiliser-subsidy content).

Conclusion:
- Retrieval is not fully missing target content.
- Mixed-context behavior is present; QA prompt/model compliance must be tightened.
