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

See: `docs/P2-PINECONE-RETRIEVAL-AUDIT.md` and `scripts/pinecone_retrieval_audit.py`.

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
- [x] Task 2 — Strict system prompt added to `v6.json` Gemini node
- [ ] Task 3 — Re-run same question set with strict prompt (`run_label = after_prompt_strict_v1`)
- [ ] Task 3 Gate A — T1/T2/T3 pass forbidden-term rule
- [ ] Task 3 Gate B — ESCALATE delta <= +2 vs baseline
- [ ] Task 4 — Reduce `topK` 10 -> 5 and rerun T1/T2/T3
- [ ] Task 4 Gate — Revert if results worsen
- [x] Task 5 — P2 marked complete and linked

---

## 9) Current Status

**Overall:** `in progress`

**Completed:** P2 + baseline + prompt update applied in exported workflow file.  
**Pending:** post-prompt measurement run (Task 3), then controlled topK experiment (Task 4).

---

## 10) Related References

- `docs/P2-PINECONE-RETRIEVAL-AUDIT.md`
- `scripts/pinecone_retrieval_audit.py`
- `v6.json`
- `margai-ghost-tutor-pilot/n8n-workflows/telegram-webhook.json`

---

## 11) Change Log

| Date | Change | Result |
|------|--------|--------|
| 2026-03-21 | Tracker created | Baseline plan established |
| 2026-03-21 | P2 diagnostic completed and recorded | Retrieval shows relevant + contaminating chunks |
| 2026-03-21 | Task-1 baseline recorded | ESCALATE 0/11, with 2 blank-question rows |
| 2026-03-21 | Structured rewrite | Context -> Goal -> Problem -> Plan -> Test -> Status format |
