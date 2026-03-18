# Install community embedding node (fix dimension 3072 vs 768)

The built-in **Embed query (Gemini)** node can output 3072 dimensions (e.g. with `gemini-embedding-2-preview`), while our Pinecone index uses **768** dimensions, causing:  
`Vector dimension 3072 does not match the dimension of the index 768`.

A community node that supports **configurable output dimensions** fixes this.

---

## 1. Install in n8n (UI)

1. In n8n, open **Settings** (gear icon) → **Community Nodes**.
2. Click **Install a community node**.
3. Enter the package name (either):
   - **`n8n-nodes-gemini-embedding-plus`** (recommended: supports Dimensions 256–3072, including 768)
   - or **`n8n-nodes-google-gemini-embeddings-extended`** (if you prefer that package).
4. Click **Install** and wait until it shows as installed.
5. Restart n8n if prompted.

You can **screenshot** the Community Nodes page showing the installed package for your records.

---

## 2. Use the node in the workflow

1. In your workflow, **remove** or bypass the built-in **Embed query (Gemini)** node.
2. Add a new node: search for **Embeddings Google Gemini Plus** (for `n8n-nodes-gemini-embedding-plus`).
3. Configure:
   - **Credential**: same Google Gemini (PaLM) API account as before.
   - **Model**: e.g. `gemini-embedding-001` or `text-embedding-004` (or the model you use).
   - **Options** → **Add Option** → **Dimensions** → set **768** (to match the Pinecone index).
4. Connect this node in place of the old Embed node (same inputs: e.g. from Merge; same output to Pinecone / Vector Store).

You can **screenshot** the new node’s parameters (model + Dimensions 768) for your records.

---

## 3. Reference

- **n8n-nodes-gemini-embedding-plus**: [npm](https://www.npmjs.com/package/n8n-nodes-gemini-embedding-plus), [GitHub](https://github.com/ronniedee/n8n-nodes-gemini-embedding-plus).  
  Supports **Dimensions** 256, 512, **768**, 1024, 1536, 2048, 3072 and **Task Type** (e.g. Retrieval Query).
- n8n docs: [Community nodes installation](https://docs.n8n.io/integrations/community-nodes/installation/).

---

## 4. If you use the workflow JSON

The workflow file `telegram-webhook.json` references the built-in embedding node. After you install the community node and add **Embeddings Google Gemini Plus** in the editor, save the workflow from n8n so the JSON is updated to the new node type. Do not edit the JSON by hand unless you know the exact node type name the community package registers.
