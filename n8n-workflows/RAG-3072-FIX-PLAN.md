# RAG / Pinecone: 3072-dim alignment (reference)

## Current state (verified against this repo)

| Layer | Model / setting | Dimension |
|-------|-------------------|-----------|
| **Ingest** | `lib/embedding.py` — `models/gemini-embedding-001`, `output_dimensionality=3072` | **3072** |
| **Pinecone** | Index name default `margai-ghost-tutor-v2` (`lib/config.py`, `.env.example`); metric cosine | **3072** |
| **Namespace** | `str(institute_id)` on upsert + query | — |
| **n8n `telegram-webhook.json`** | Embed node: `gemini-embedding-001`, **`dimensions`: 3072** | **3072** |
| **n8n `v6.json`** | Embed node: `modelName` `models/gemini-embedding-001`, **`dimensions`: 3072** | Matches ingest + Pinecone. |
| **Retriever `topK`** | `v6.json`: **30**; `telegram-webhook.json`: **12** | Tune for faithfulness vs latency |

**Chain:** Merge → Embed query (Gemini) → Pinecone vector store → Vector Store Retriever → Question and Answer Chain ← Gemini Chat (`gemini-2.5-flash`).

---

## Operator checklist

1. Pinecone index dimension **3072**, name matches `PINECONE_INDEX_NAME` (e.g. `margai-ghost-tutor-v2`).
2. n8n **Embed query** output dimension **3072** (match `lib/embedding.py`).
3. Re-ingest PDFs after any embedding or index change (vectors must be in same space as queries).

---

## Historical note (768 → 3072)

Older setups used a **768**-dim index (`margai-ghost-tutor`) while some n8n embed nodes emitted **3072**, causing `Vector dimension … does not match index dimension …`. **Fix applied in repo:** new index **`margai-ghost-tutor-v2`** at **3072**, ingestion + workflows aligned. Do not point a 3072 query pipeline at a 768 index.

**Optional:** Community embed nodes (`COMMUNITY-NODES-EMBEDDING.md`) only if you must match a **non-3072** legacy index.
