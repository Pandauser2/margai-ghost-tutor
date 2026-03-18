# RAG dimension fix: 3072 alignment (STEP 1 + STEP 2)

## STEP 1: Current setup

### Nodes involved

| Node | Type | Role | Embedding model | Expected vector dimension |
|------|------|------|-----------------|---------------------------|
| **Embed query (Gemini)** | `@n8n/n8n-nodes-langchain.embeddingsGoogleGemini` | Produces query embedding for retrieval | `gemini-embedding-2-preview` | **3072** (model default; `dimensions: 768` in JSON is not honored by API for this model) |
| **Pinecone query** | `@n8n/n8n-nodes-langchain.vectorStorePinecone` | Vector store for retriever; mode = retrieve | N/A (uses embedding from above) | Must match index = **768** currently → **3072** after fix |
| **Vector Store Retriever** | `@n8n/n8n-nodes-langchain.retrieverVectorStore` | Connects Pinecone to QA chain; topK = 8 | N/A | N/A |
| **Question and Answer Chain** | `@n8n/n8n-nodes-langchain.chainRetrievalQa` | RAG: takes `query_text`, retrieves context, calls LLM | N/A | N/A |

**Other connections:**  
- **Merge for embed** → **IF query_text present** → **Question and Answer Chain** (main input).  
- **Embed query (Gemini)** → **Pinecone query** (ai_embedding).  
- **Pinecone query** → **Vector Store Retriever** (ai_vectorStore).  
- **Vector Store Retriever** → **Question and Answer Chain** (ai_retriever).  
- **Gemini Chat (gemini-2.5-flash)** → **Question and Answer Chain** (ai_languageModel).

**Insert (upsert) pipeline (outside n8n):**  
- **scripts/ingest_pdf.py** uses **lib/embedding.py** → **lib/pinecone_client.upsert_vectors**.  
- **lib/embedding.py:** model = `models/gemini-embedding-001`, **output_dimensionality = 768**.  
- So **ingestion currently produces 768-dim vectors** and upserts to the same Pinecone index.

### Current Pinecone index

- **Name:** From env `PINECONE_INDEX_NAME` (default **`margai-ghost-tutor`** in `lib/config.py` and `.env.example`).
- **Dimension:** **768** (documented in RUN.md, PINECONE_FROM_ZERO.md, PINECONE_NAMESPACE.md).
- **Metric:** cosine (docs and create-index snippets).

### Root cause of the error

- **n8n** Embed node uses `gemini-embedding-2-preview`, which outputs **3072** dimensions (the `dimensions: 768` parameter is not supported for this model in practice).
- **Pinecone index** is **768**.
- **Ingestion** produces **768** with `gemini-embedding-001`.
- At query time, n8n sends **3072-dim** vectors → **"Vector dimension 3072 does not match index dimension 768"**.

---

## STEP 2: Minimal-change plan

### 1. Recreate Pinecone index (manual)

- **Dimension:** **3072**
- **Metric:** **cosine**
- **Name:** Use a **NEW** index name (e.g. **`margai-ghost-tutor-v2`**). Do **NOT** reuse the old index name.
- **Re-indexing:** All existing vectors must be re-generated (3072-dim) and re-upserted. The old 768-dim index cannot be reused.

### 2. Use one embedding model everywhere

- **Choice:** **`models/gemini-embedding-001`** with **3072** dimensions for both ingestion and n8n retrieval.
- **Reason:** Same embedding space for insert and query; no dependency on community nodes; `gemini-embedding-001` supports 3072 via `output_dimensionality`.

### 3. Nodes to modify

| Where | What changes | Why |
|-------|----------------|-----|
| **n8n – Embed query (Gemini)** | Ensure **embedding model** = `gemini-embedding-001` (dimension auto = 3072). | So retrieval produces 3072-dim vectors that match the new index. Same model as ingestion. |
| **lib/embedding.py** | Set **EMBEDDING_DIMENSION** to **3072**. Keep **EMBEDDING_MODEL** = `models/gemini-embedding-001`. | So ingestion produces 3072-dim vectors for the new index. |
| **Docs** (RUN.md, PINECONE_FROM_ZERO.md, PINECONE_NAMESPACE.md, README-telegram-webhook.md) | Replace index dimension **768** with **3072** and note that re-indexing is required. | So future setup and ops use the correct dimension. |

### 4. What does not change

- **Pinecone node:** No code change; still `indexName: ={{ $env.PINECONE_INDEX_NAME }}`, `options.pineconeNamespace: ={{ String($json.institute_id) }}`. Namespace remains dynamic.
- **Vector Store Retriever / Question and Answer Chain:** No config change; no architecture change.
- **Query input:** Still `{{ $json.query_text || '' }}` in the chain.
- **Output:** Still normalized to `{{ $json.response?.text ?? $json.text ?? 'ESCALATE' }}` in Set node; downstream uses `$json.text`.

### 5. Re-indexing strategy

1. User creates **new** Pinecone index: dimension **3072**, metric **cosine**, name **`margai-ghost-tutor-v2`** (do not reuse the old index name). Set `PINECONE_INDEX_NAME=margai-ghost-tutor-v2` in env.
2. Run ingestion again for all institutes/PDFs: `python3 scripts/ingest_pdf.py <pdf> <institute_slug>` (after the code change to 3072). Namespaces will be populated with 3072-dim vectors in the new index.
3. Old 768-dim index (`margai-ghost-tutor`) can be deleted after cutover to avoid confusion.

---

## Validation (after implementation)

- **Confirm Pinecone returns matches (length > 0):** Run a query that should hit ingested content; check that the retriever/Pinecone step returns at least one match.
- **Confirm matches contain `metadata.text`:** Inspect retriever output (or chain context); each match should have `metadata.text` with chunk content.
- **Confirm QA chain returns non-empty answer:** For a question covered by the ingested PDF, the chain output should be non-empty (and not only "ESCALATE" when context is present).
- **Confirm no dimension mismatch errors:** No "Vector dimension X does not match index dimension Y" in n8n or ingestion logs.
