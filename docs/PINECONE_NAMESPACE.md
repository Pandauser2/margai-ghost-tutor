# Pinecone index and namespace convention

## Index

- Create a **serverless** index in Pinecone with dimension matching the embedding model (e.g. **768** for `text-embedding-004` or `gemini-embedding-001`).
- Metric: cosine (default for semantic search).

## Namespace convention

- **One namespace per institute.** Use `institute_id` (from Supabase `institutes.id`) as the namespace string.
- **Upsert:** When ingesting PDFs for an institute, always pass `namespace=str(institute_id)` (e.g. `"1"`) so all vectors for that institute live in that namespace.
- **Query:** When handling a Telegram message, resolve `institute_id` first (via chat→institute mapping), then query with `namespace=str(institute_id)` only. Institute A never sees Institute B's data.

## Example (Python)

```python
# Upsert after ingestion
index.upsert(vectors=vectors, namespace=str(institute_id))

# Query when replying to student
results = index.query(vector=query_embedding, top_k=10, namespace=str(institute_id))
```

## Creating the index (one-time)

Via Pinecone console, or API:

```python
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key="...")
pc.create_index(
    name="margai-ghost-tutor",
    dimension=768,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)
```

Replace dimension if using a different embedding model.
