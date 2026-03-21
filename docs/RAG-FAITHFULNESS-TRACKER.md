# RAG faithfulness tracker (Ghost Tutor)

**Purpose:** Track the issue where answers **mix retrieved context with other PDF sections or general knowledge**, and record fixes + test results over time.

**Status:** `open` — see [Change log](#change-log) at bottom.

---

## Problem summary

Example: **Box 4.3 — Distress among cotton farmers**

The model produced an answer that was **substantially aligned** with the box on core causes, but **added bullets not supported by that document** (e.g. Anantpur, fertiliser subsidies, export quotas/NTBs, export-oriented farming narrative, over-specific “infrastructure” list).

**Root causes (working hypothesis):**

1. **Weak / missing LLM system prompt** in latest workflow export (`v6.json`: Gemini Chat `options: {}`), so the model fills gaps from prior knowledge or other retrieved chunks.
2. **Retrieval breadth:** `topK` and mixed chunks from the same PDF bring in reform/trade/other-case material (e.g. groundnut / Anantpur passages).
3. **No metadata filtering** yet (chapter/box/source scoping) — deferred “step 4” in pilot roadmap.

---

## What the answer got right (supported by Box 4.3–style text)

Use this as **positive checklist** for regression tests:

| Claim | OK? |
|--------|-----|
| Shift to commercial crops without adequate technical support; withdrawal / weakness of state agricultural extension | ✅ |
| Decline in public investment in agriculture over ~two decades | ✅ |
| Low germination (large firms) + spurious seeds/pesticides (private agents) | ✅ |
| Crop failure, pest attacks, drought | ✅ |
| High-interest debt from private money lenders (36%–120%); borewell borrowing that fails | ✅ |
| Cheap imports → lower pricing and profits | ✅ |
| Global glut; subsidies (e.g. U.S.A. and others) depressing prices | ✅ |
| High production costs (only if **verbatim** in retrieved chunk — verify per ingest) | ✅ |

---

## Where answers must not go (strict document mode)

Treat as **forbidden unless the retrieved chunk contains the exact idea**:

| Issue | Example |
|--------|---------|
| Specificity not in text | Listing “irrigation, power, roads, market linkages” if the box only says “decline in public investment” generally |
| Wrong locality / other case study | “Anantpur district” when the box is cotton / AP–Maharashtra narrative |
| Other chapter content | “Removal of fertiliser subsidies” if not in the retrieved passage |
| Trade / reform essay not in box | India’s export quotas removal, NTBs in developed markets |
| Macro narrative not in box | Export-oriented farming vs food grains framing |

---

## Fix plan (phases)

### Phase A — n8n (no re-ingest)

1. Set **Gemini Chat** system message: context-only; no facts not in provided context; optional `ESCALATE` if insufficient.
2. Add instruction: **do not name places, policies, or reforms unless they appear in the provided context.**
3. Optional: require **per-bullet trace** (e.g. short quote or chunk id) in the answer format.

### Phase B — retrieval tuning

4. Adjust **topK** / **rerank** (if available) to reduce unrelated chunks.
5. Add **metadata filters** when metadata exists (`source_file`, future `chapter` / `box_id`).

### Phase C — ingestion (only if A+B insufficient)

6. Chunk boundaries / box grouping; **re-ingest** after chunking changes.
7. Richer metadata at upsert for filtering.

---

## Test plan

### Golden questions (faithfulness)

| ID | Query | Pass | Fail |
|----|--------|------|------|
| T1 | Paraphrase: causes of distress among cotton farmers (Box 4.3) | Bullets match box only | Anantpur, fertiliser subsidy, quota, NTBs, export-oriented farming |
| T2 | List scholar-cited factors for suicides in cotton-farmer distress (Box 4.3) | ~7 factors, aligned to text | Long unrelated trade essay |
| T3 | Short: “What caused distress among cotton farmers?” | Same as T1 | Same forbidden terms as T1 |
| T4 | Box 2.1 / types of economic systems | Content from that box | Unrelated GDP/poverty-only dump |

### Negative tests

| ID | Query | Pass |
|----|--------|------|
| N1 | Question not in material | ESCALATE or “not in material” — **no** invented facts |
| N2 | Vague question | Clarify or ESCALATE — not generic lecture |

### Pipeline checks

| ID | Check |
|----|--------|
| P1 | `QUERY_RAW` logged; `EMBED_MODEL = models/gemini-embedding-001`; INDEX / NAMESPACE / TOP_K match ingest |
| P2 | Raw top-k for T1 includes a chunk containing Box 4.3 / cotton distress before QA |

### Release bar (tune to your corpus size)

- Golden set T1–T4: target **≥90%** pass (adjust as you add rows).
- T1–T3: **zero** forbidden phrases unless they literally appear in **retrieved** text.
- N1: no fabricated stats/policies.

---

## P2 diagnostic (retrieval-only, no LLM)

- **Runbook:** [P2-PINECONE-RETRIEVAL-AUDIT.md](./P2-PINECONE-RETRIEVAL-AUDIT.md)
- **Script:** `scripts/pinecone_retrieval_audit.py` — embed + Pinecone top‑k, log scores + metadata + text preview.

## Related files

- `v6.json` — latest n8n workflow export (Gemini prompt currently empty in repo).
- `margai-ghost-tutor-pilot/n8n-workflows/telegram-webhook.json` — contains example `systemMessage`.
- `margai-ghost-tutor-pilot/scripts/ingest_pdf.py` — upsert metadata (`source_file`, `source_slug`, `chunk_id`).
- Linear: **AI-6** — n8n hardening (Supabase filter, prompt, explicit Supabase ops).

---

## Change log

| Date | Change | Result |
|------|--------|--------|
| _YYYY-MM-DD_ | Doc created | Baseline tracker |
| | | |

_Update this table whenever you change prompts, topK, metadata, or re-ingest._
