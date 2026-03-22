# RAG Faithfulness Tracker (Ghost Tutor)

## 1) Context

This pilot runs an n8n RAG flow:

`Telegram -> Pinecone retrieval -> Gemini 2.5 Flash QA -> Telegram reply`

The target behavior is strict document-grounded answering: use retrieved context only, and avoid adding facts from outside the retrieved chunks.

---

## 2) Goal

Ensure user answers are faithful to source context, specifically for textbook-box style questions (for example, `Box 4.3: Distress Among Cotton Farmers`), while keeping escalation rates acceptable.

Success means:
- No unsupported facts added from adjacent sections or model prior knowledge.
- Valid in-context questions answered correctly.
- Out-of-context questions escalate.

---

## 3) Problem Statement

Observed behavior: answers sometimes combine correct points with unrelated facts (for example, Anantpur/fertiliser-subsidy/NTB style content) when retrieval returns mixed-topic chunks.

Initial hypotheses:
1. Missing/weak system prompt in live workflow export (`v6.json` previously had empty Gemini options).
2. Retrieval contamination at current `topK`.
3. No chapter/box metadata filters in current index.

---

## 4) What Was Verified (Evidence)

### P2 Retrieval-Only Diagnostic (Completed)

- Query: `what caused distress among cotton farmers?`
- Index / namespace / topK: `margai-ghost-tutor-v2` / `1` / `10`
- Result: top ranks include genuine Box 4.3 material, but lower ranks include contaminating adjacent-section chunks.
- Decision: retrieval is not fully missing target content; QA compliance on mixed context is a major failure mode.

See: `docs/PINECONE_NAMESPACE.md` § **P2 diagnostic** and `scripts/pinecone_retrieval_audit.py`.

### Multi-PDF isolation (Hist vs NCERT) — smoke check

- Query (example): Zulfiqar Khan / finances of Bengal.
- `pinecone_retrieval_audit.py` over top-15: all chunks from `Hist-part-1.pdf` (no `NCERT-Class-11-Economics-sample.pdf` in top-k).
- Telegram end-to-end answer confirmed correct for this case.

### Task-1 Baseline (Before Strict Prompt)

- Total rows logged: `11`
- Valid non-empty question rows: `9`
- Blank-question rows (early logger bug): `2`
- ESCALATE count: `0`
- Forbidden hits observed: `fertiliser subsidy`, `quota`, `non-tariff barriers`

Interpretation: baseline is permissive (no escalation) and allows overreach.

---

## 5) Guardrails (Document-Only Mode)

Treat these as forbidden unless explicitly present in retrieved chunks:
- `Anantpur district`
- `fertiliser subsidy`
- `quota`
- `non-tariff barriers` / `NTB`
- `export-oriented farming` narrative

---

## 6) Solution Plan (Phased)

### Phase A — Prompt Compliance (Current Focus)
1. Apply strict system prompt in Gemini QA node.
2. Enforce: no place/policy names unless verbatim in retrieved context.
3. Keep retrieval/chunking unchanged during this phase for clean attribution.

### Phase B — Retrieval Tuning (After Prompt Validation)
4. Tune `topK` (10 -> 5 experiment) and evaluate contamination tradeoff.
5. Consider reranking if supported and stable.
6. Add metadata filters when metadata becomes available.

### Phase C — Ingestion/Chunking (Deferred)
7. Re-chunk/re-ingest only if A+B cannot meet faithfulness targets.

---

## 7) Test Plan

### A. Golden Questions
- T1: causes of distress among cotton farmers (Box 4.3)
- T2: scholar-cited factors for suicides
- T3: short cotton distress question
- T4: Box 2.1 types of economic systems

### B. Negative Check
- N1: out-of-material question must return `ESCALATE`.

### C. Pipeline Checks

| ID | Check | Status |
|----|-------|--------|
| P1 | Query/model/index/namespace logging is correct | 🟡 partial (fixed after initial logger bug) |
| P2 | Raw top-k contains Box 4.3 material before QA | ✅ completed |

### D. Acceptance Gates

- For T1/T2/T3: zero forbidden phrases in final answers.
- ESCALATE increase after strict prompt must be <= +2 versus baseline.
- If ESCALATE increase > +2: pause and review prompt aggressiveness.
- After topK 10 -> 5 test: if contamination worsens or answer quality drops, revert to 10 and pause.

---

## 8) Task Checklist (Execution Tracker)

- [x] Task 1 — Baseline run logged in Supabase
- [ ] Task 2 — Strict system prompt in Gemini (deferred: n8n UI has no system message field; optional JSON/API path later)
- [~] Task 3 — **Smoke:** Telegram OK (Hist query + multi-PDF retrieval check). **Formal:** if/when Task 2 applied, log with `run_label = after_prompt_strict_v1` and close Gates A/B below.
- [ ] Task 3 Gate A — T1/T2/T3 pass forbidden-term rule (from formal log)
- [ ] Task 3 Gate B — ESCALATE delta <= +2 vs baseline (from formal log)
- [ ] Task 4 — Reduce `topK` 10 -> 5 and rerun T1/T2/T3
- [ ] Task 4 Gate — Revert if results worsen
- [x] Task 5 — P2 marked complete and linked

---

## 9) Current Status

**Overall:** `in progress`

**Completed:** P2 + baseline + Hist/NCERT retrieval smoke + Telegram smoke.  
**Pending:** **Task 2** strict prompting (skipped in export for now), optional **Task 3 formal** run after that, then **Task 4** `topK` experiment (`v6.json` retriever **topK 30**).

---

## 10) Related References

- `docs/PINECONE_NAMESPACE.md` (setup + P2 retrieval audit)
- `scripts/pinecone_retrieval_audit.py`
- `n8n-workflows/v6.json` (primary export)
- `n8n-workflows/telegram-webhook.json` (slimmer reference)
- § **12) Incident playbook** (below)

---

## 11) Change Log

| Date | Change | Result |
|------|--------|--------|
| 2026-03-21 | Tracker created | Baseline plan established |
| 2026-03-21 | P2 diagnostic completed and recorded | Retrieval shows relevant + contaminating chunks |
| 2026-03-21 | Task-1 baseline recorded | ESCALATE 0/11, with 2 blank-question rows |
| 2026-03-21 | Structured rewrite | Context -> Goal -> Problem -> Plan -> Test -> Status format |
| 2026-02-27 | Hist vs NCERT retrieval + Telegram smoke OK | Multi-PDF isolation verified for sample query |
| 2026-02-27 | `v6.json` topK experiment rolled back | Restored Vector Store Retriever `topK` to **30** (keep export as-is) |
| 2026-03-22 | Gemini `systemMessage` removed from exports | Align with n8n UI; strict prompt deferred (see Task 2) |
| 2026-03-23 | Incident playbook merged into this doc | Removed standalone `RAG-INCIDENT-PLAYBOOK.md` |

---

## 12) Incident playbook (production triage)

*Merged from former `RAG-INCIDENT-PLAYBOOK.md`.*

### When to use

- Answer includes facts not in source chunks.
- Bot says context missing for content that exists in material.
- Sudden rise in `ESCALATE`.
- Telegram replies `undefined`/empty.

### 5-command diagnostic loop

From `margai-ghost-tutor-pilot/` with `.venv` and `.env`:

```bash
# 1) Embedding + index alignment
python - <<'PY'
from lib.config import get_settings
from lib.embedding import EMBEDDING_MODEL, EMBEDDING_DIMENSION
s=get_settings()
print("EMBED_MODEL", EMBEDDING_MODEL)
print("EMBED_DIM", EMBEDDING_DIMENSION)
print("INDEX", s.pinecone_index_name)
PY

# 2) Namespace stats
python - <<'PY'
from lib.config import get_settings
from pinecone import Pinecone
s=get_settings()
pc=Pinecone(api_key=s.pinecone_api_key)
idx=pc.Index(s.pinecone_index_name)
print(idx.describe_index_stats())
PY

# 3–4) Retrieval-only audit (see PINECONE_NAMESPACE.md § P2)
python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10

python scripts/pinecone_retrieval_audit.py \
  --query "what caused distress among cotton farmers?" \
  --namespace 1 \
  --top-k 10 \
  --json > /tmp/rag_audit.json

# 5) Optional: Supabase eval logs
# select created_at, question, escalate, forbidden_hits from public.rag_eval_logs order by created_at desc limit 20;
```

### 5 n8n checks

1. **Input:** `query_text` populated; same text reaches QA branch.
2. **Embed:** `models/gemini-embedding-001`, dimension **3072**, valid credential.
3. **Pinecone:** index `margai-ghost-tutor-v2`; `namespace = String(institute_id)`; `topK` as intended.
4. **Gemini QA:** n8n LangChain Gemini Chat **has no system-message field in UI** (Task 2). Target strict context-only + `ESCALATE` via future HTTP Gemini / custom prompt. Verify chain output and normalization.
5. **Out:** Telegram uses `text || answer`; logging does not strip reply.

### Decision tree

| Symptom | Likely layer | Action |
|---------|----------------|--------|
| Target chunk **missing** in raw top-k | Retrieval | `topK`, filters, chunking/re-ingest last |
| Chunk **present**, answer overreaches | QA | Prompt / `topK` / format |
| `undefined`, blank logs | Wiring | Payload + Set node fallbacks |

### Gates

- Before retrieval-only experiments: prompt/compliance baseline where applicable.
- Before re-ingest: confirm P2 audit still fails after prompt + retrieval tuning.

### Run labels (eval logs)

`baseline_before_prompt_change`, `after_prompt_strict_v1`, `after_topk_5_v1`

### Rollback

1. Revert workflow export / n8n.
2. Restore prior `topK`.
3. Smoke: Box 4.3 cotton; Box 2.1; one OOD → `ESCALATE`.
4. Note in this doc + Linear.

### Other

- [CURSOR-LINEAR-INTEGRATION.md](CURSOR-LINEAR-INTEGRATION.md) for issue tracking.
