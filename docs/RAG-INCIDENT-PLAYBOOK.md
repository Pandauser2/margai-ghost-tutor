# RAG Incident Playbook (Ghost Tutor)

## Purpose

Fast response checklist when answer quality regresses (hallucinations, missing facts, overreach, unexpected `ESCALATE`).

This playbook is designed for production debugging with minimal guesswork.

---

## When to use

Trigger this playbook if any of these happen:

- Answer includes facts not in source chunks.
- Bot says “context missing” for content known to exist.
- Sudden rise in `ESCALATE`.
- Telegram replies become `undefined`/empty.

---

## 5-command diagnostic loop

Run from `margai-ghost-tutor-pilot/` with `.venv` and `.env` loaded.

```bash
# 1) Verify embedding + index settings are aligned
python - <<'PY'
from lib.config import get_settings
from lib.embedding import EMBEDDING_MODEL, EMBEDDING_DIMENSION
s=get_settings()
print("EMBED_MODEL", EMBEDDING_MODEL)
print("EMBED_DIM", EMBEDDING_DIMENSION)
print("INDEX", s.pinecone_index_name)
PY

# 2) Inspect index namespace counts
python - <<'PY'
from lib.config import get_settings
from pinecone import Pinecone
s=get_settings()
pc=Pinecone(api_key=s.pinecone_api_key)
idx=pc.Index(s.pinecone_index_name)
print(idx.describe_index_stats())
PY

# 3) Run retrieval-only audit for failing query
python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10

# 4) Save machine-readable audit for diffing
python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10 \
  --json > /tmp/rag_audit.json

# 5) Check recent evaluation logs (if Supabase logger is enabled)
# Run in Supabase SQL editor:
# select created_at, question, escalate, forbidden_hits from public.rag_eval_logs order by created_at desc limit 20;
```

---

## 5 n8n checks (UI)

1. **Input integrity**
   - Confirm `query_text` is populated in `Set institute_id and parse`.
   - Confirm same question reaches QA branch.

2. **Embedding node**
   - Model must be `models/gemini-embedding-001`.
   - No credential fallback to deprecated config.

3. **Pinecone params**
   - Index = expected (`margai-ghost-tutor-v2`).
   - Namespace = `String(institute_id)` and matches ingest namespace.
   - `topK` matches current experiment setting.

4. **Gemini QA prompt**
   - Strict system prompt exists (not empty).
   - Includes context-only + `ESCALATE` rule.

5. **Output wiring**
   - Telegram text uses fallback (`text || answer || ESCALATE`).
   - Logging branch does not mutate reply path.

---

## Decision tree

### A) Target chunk missing in raw Pinecone top-k

Root cause is retrieval-side.

Do:
- adjust `topK`,
- tune retrieval settings/rerank,
- add metadata filters (when available),
- revisit chunking/re-ingestion only if required.

### B) Target chunk present in raw top-k, but final answer overreaches

Root cause is QA compliance.

Do:
- tighten system prompt,
- reduce mixed-context exposure (`topK` experiment),
- enforce stricter answer format / traceability.

### C) Data shape issues (`undefined`, blank question logs)

Root cause is workflow wiring.

Do:
- preserve payload in logging code (`...item.json`),
- verify `question` capture fallbacks,
- keep logging as side-branch.

---

## Operational gates (do not skip)

Before changing retrieval settings:
- Complete prompt compliance run first.
- Compare against baseline (`ESCALATE` delta and forbidden-hit rate).

Before changing chunking/re-ingestion:
- Confirm retrieval-only audit still fails after prompt + retrieval tuning.

---

## Standard run labels

Use consistent labels in `rag_eval_logs`:

- `baseline_before_prompt_change`
- `after_prompt_strict_v1`
- `after_topk_5_v1`

This keeps SQL comparisons simple and audit-ready.

---

## Fast rollback

If quality worsens after a change:

1. Revert last workflow change in n8n UI/export.
2. Restore previous `topK`.
3. Re-run 3 smoke queries:
   - cotton distress (Box 4.3)
   - Box 2.1 economic systems
   - one out-of-context query (expect `ESCALATE`)
4. Log incident summary in tracker doc + Linear issue.

---

## Related docs

- `docs/RAG-FAITHFULNESS-TRACKER.md`
- `docs/P2-PINECONE-RETRIEVAL-AUDIT.md`
- `docs/CURSOR-LINEAR-INTEGRATION.md`
