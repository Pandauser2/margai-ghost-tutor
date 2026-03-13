# Pinecone from zero (Step 3, no prior experience)

This app uses **Pinecone** as a “vector database”: it stores **embeddings** (numerical summaries) of your PDF text so the bot can quickly find relevant chunks when a student asks a question. You don’t need to understand vectors—you just need an account, an API key, and one index.

---

## 1. Create a Pinecone account and get an API key

1. Go to **[pinecone.io](https://www.pinecone.io)** and sign up (free tier is enough).
2. Log in and open the **Pinecone console** (dashboard).
3. In the left sidebar, open **API Keys** (or **Project** / **API Keys** depending on the UI).
4. Click **Create API Key** (or **+ Create key**). Give it a name (e.g. `margai-pilot`), then **Create**.
5. **Copy the key** and save it somewhere safe (you’ll paste it only into `.env`). It looks like:  
   `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`  
   This is your **PINECONE_API_KEY**. Put it in `margai-ghost-tutor-pilot/.env` as:
   ```env
   PINECONE_API_KEY=your-copied-key-here
   PINECONE_INDEX_NAME=margai-ghost-tutor
   ```

You’ll use this key in the app and (optionally) when creating the index with Python. You do **not** need to understand what an “embedding” or “vector” is to continue.

---

## 2. Create the index (two options)

You need **one index** named `margai-ghost-tutor` with:
- **Dimension:** 768  
- **Metric:** cosine  
- **Type:** serverless  

Choose **A** (dashboard) or **B** (Python). Dashboard is easier if you’re new.

---

### Option A: Create the index in the Pinecone dashboard (easiest)

1. In the Pinecone console, go to **Indexes** (left sidebar).
2. Click **Create Index** (or **+ Create index**).
3. Fill in:
   - **Index name:** `margai-ghost-tutor` (must match `PINECONE_INDEX_NAME` in `.env`).
   - **Dimensions:** `768`.
   - **Metric:** **Cosine**.
   - **Cloud / Region:** pick a serverless option (e.g. **AWS** and a region like **us-east-1**).  
     The UI might say “Serverless” or “Starter” plan—choose that so you don’t need to manage a server.
4. Click **Create** (or **Create index**).
5. Wait until the index status is **Ready** (may take a minute or two).

You’re done. Skip Option B. Your `.env` already has `PINECONE_INDEX_NAME=margai-ghost-tutor`; the app will use this index.

---

### Option B: Create the index with Python (after you have the API key)

Use this only if you prefer the command line or the dashboard didn’t work.

1. Install the Pinecone client (in the same environment you use for the pilot):
   ```bash
   pip install "pinecone>=5.0.0"
   ```
2. Put your API key in `.env` (see section 1), then from the **pilot folder** run:
   ```bash
   cd /path/to/Cursor_test_project/margai-ghost-tutor-pilot
   export $(grep -v '^#' .env | xargs)   # load .env (Linux/macOS)
   python3 -c "
   from pinecone import Pinecone, ServerlessSpec
   import os
   key = os.environ.get('PINECONE_API_KEY')
   if not key:
       print('PINECONE_API_KEY not set in .env')
       exit(1)
   pc = Pinecone(api_key=key)
   pc.create_index(
       name='margai-ghost-tutor',
       dimension=768,
       metric='cosine',
       spec=ServerlessSpec(cloud='aws', region='us-east-1'),
   )
   print('Index created. Wait 1–2 min until it shows Ready in the console.')
   "
   ```
3. In the Pinecone console, open **Indexes** and confirm `margai-ghost-tutor` appears and becomes **Ready**.

---

## 3. Why 768 and cosine?

- **Dimension 768:** The embedding model (Gemini) used by this app produces vectors of length 768. The index must use the same dimension.
- **Metric cosine:** The app finds “nearest” chunks by cosine similarity. The index must use the cosine metric to match.

You don’t need to change these unless you change the embedding model in the code.

---

## 4. Checklist before leaving Step 3

- [ ] Pinecone account created.
- [ ] API key created and copied.
- [ ] `PINECONE_API_KEY` and `PINECONE_INDEX_NAME=margai-ghost-tutor` set in `margai-ghost-tutor-pilot/.env`.
- [ ] Index `margai-ghost-tutor` created (dashboard or Python) with dimension **768**, metric **cosine**, serverless.
- [ ] Index status is **Ready** in the Pinecone console.

Then continue with **Step 4 (Telegram bot)** in [RUN.md](../RUN.md).
