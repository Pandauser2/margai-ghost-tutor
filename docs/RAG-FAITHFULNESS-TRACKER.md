# RAG faithfulness tracker (Ghost Tutor)

**Purpose:** Track answers that mix retrieved context with unrelated sections/general knowledge.

**Status:** `in progress` — P2 completed, Task-1 baseline logged.

---

## Current status snapshot

- **P2 (retrieval-only):** ✅ completed
  - Query: `what caused distress among cotton farmers?`
  - Index / Namespace / topK: `margai-ghost-tutor-v2` / `1` / `10`
  - Outcome: top ranks include true Box 4.3 material, but ranks 5-6 include contaminating chunks (Anantpur/fertiliser-subsidy-type content).
  - Decision: retrieval is not fully missing target; mixed context is entering QA.

- **Task-1 baseline (before strict prompt):** ✅ logged
  - Total rows: `11`
  - Valid non-empty question rows: `9`
  - Blank-question rows (early logger bug): `2`
  - ESCALATE count: `0`
  - Forbidden hits seen: `fertiliser subsidy`, `quota`, `non-tariff barriers`.

---

## Task checklist (execution tracker)

- [x] **Task 1** — Baseline run before prompt change (10-question set) logged to Supabase
- [x] **Task 2** — Strict system prompt added to `v6.json` Gemini node
- [ ] **Task 3** — Re-run same question set with strict prompt (`run_label = after_prompt_strict_v1`)
- [ ] **Task 3 gate A** — T1/T2/T3 have zero forbidden phrases
- [ ] **Task 3 gate B** — ESCALATE increase is <= +2 vs baseline
- [ ] **Task 4** — Reduce `topK` from 10 -> 5 and re-test T1/T2/T3 only
- [ ] **Task 4 gate** — If forbidden phrases worsen, revert `topK` to 10 and pause
- [x] **Task 5** — P2 marked complete and linked to audit script/results

### Current baseline metrics (Task 1)

- Baseline rows: `11` (valid non-empty questions: `9`)
- Baseline ESCALATE: `0`
- Baseline forbidden hits seen: `fertiliser subsidy`, `quota`, `non-tariff barriers`

---

## Problem summary

Example: **Box 4.3 — Distress among cotton farmers**

Model answers often include correct core causes, but may add unsupported facts from adjacent sections.

Working causes:
1. Missing/weak system prompt in some workflow exports (`v6.json` has empty Gemini options).
2. Mixed retrieval context at current `topK`.
3. No chapter/box metadata filter in current index.

---

## Guardrails for strict document mode

Forbidden unless explicitly present in retrieved chunk:
- Anantpur district
- fertiliser subsidy
- quota / non-tariff barriers / NTB
- export-oriented farming narrative

---

## Fix plan (phased)

### Phase A — Prompt compliance
1. Add strict system prompt (context-only + `ESCALATE` fallback).
2. Require no place/policy names unless verbatim in retrieved context.

### Phase B — Retrieval tuning
3. Tune `topK` and rerank (if available).
4. Add metadata filters when available.

### Phase C — Ingestion (later)
5. Re-chunk/re-ingest only if A+B insufficient.

---

## Test plan

### Golden questions
- T1: causes of distress among cotton farmers (Box 4.3)
- T2: scholar-cited factors for suicides
- T3: short cotton distress question
- T4: Box 2.1 types of economic systems

### Negative checks
- N1: out-of-material question -> must `ESCALATE`

### Pipeline checks
| ID | Check | Status |
|----|-------|--------|
| P1 | query/model/index/namespace logged | 🟡 partial (logger bug fixed after initial rows) |
| P2 | raw top-k contains Box 4.3 content | ✅ completed |

---

## Related docs
- `docs/P2-PINECONE-RETRIEVAL-AUDIT.md`
- `scripts/pinecone_retrieval_audit.py`

---

## Change log

| Date | Change | Result |
|------|--------|--------|
| 2026-03-21 | Tracker created | Baseline plan established |
| 2026-03-21 | P2 completed and recorded | Retrieval shows relevant + contaminating chunks |
| 2026-03-21 | Task-1 baseline recorded | ESCALATE 0/11, 2 rows had blank question |
