#!/usr/bin/env python3
"""
P2 diagnostic: Pinecone retrieval ONLY (no Gemini chat / no QA chain).

Uses the SAME stack as ingestion:
- Embedding: lib.embedding (models/gemini-embedding-001, 3072 dims)
- Pinecone: lib.config env + lib.pinecone_client.query_index

Usage (from repo root, venv + .env):
  cd margai-ghost-tutor-pilot && source .venv/bin/activate
  set -a && source .env && set +a
  python scripts/pinecone_retrieval_audit.py \\
    --query "what caused distress among cotton farmers?" \\
    --namespace 1 \\
    --top-k 10

Optional: --json for machine-readable output.
Does not modify prompts, chunking, or n8n workflows.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Pilot on path
_PILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PILOT))

from lib.config import get_settings
from lib.embedding import EMBEDDING_MODEL, get_embedding
from lib.pinecone_client import get_pinecone_index, query_index


def main() -> int:
    parser = argparse.ArgumentParser(description="P2: Pinecone retrieval audit (no LLM)")
    parser.add_argument(
        "--query",
        type=str,
        default="what caused distress among cotton farmers?",
        help="Query string to embed and search",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Pinecone namespace (default: INSTITUTE_ID env or '1')",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Number of matches (default 10)")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    settings = get_settings()
    ns = args.namespace
    if ns is None:
        import os

        ns = os.environ.get("INSTITUTE_ID", "1")

    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY not set (needed for query embedding only)", file=sys.stderr)
        return 1
    if not settings.pinecone_api_key:
        print("ERROR: PINECONE_API_KEY not set", file=sys.stderr)
        return 1

    index_name = settings.pinecone_index_name

    vector = get_embedding(args.query, api_key=settings.gemini_api_key, model=EMBEDDING_MODEL)
    index = get_pinecone_index(settings.pinecone_api_key, index_name)
    res = query_index(index, vector, namespace=str(ns), top_k=args.top_k, include_metadata=True)

    matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", []) or []

    rows = []
    for rank, m in enumerate(matches, 1):
        mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
        score = m.get("score") if isinstance(m, dict) else getattr(m, "score", None)
        md = (m.get("metadata") if isinstance(m, dict) else getattr(m, "metadata", {})) or {}
        text = md.get("text") or md.get("pageContent") or ""
        rows.append(
            {
                "rank": rank,
                "id": mid,
                "score": float(score) if score is not None else None,
                "metadata": {k: v for k, v in md.items() if k != "text"},
                "text": text,
                "text_preview_400": (text[:400] + "…") if len(text) > 400 else text,
            }
        )

    payload = {
        "diagnostic": "P2_Pinecone_only",
        "query": args.query,
        "embed_model": EMBEDDING_MODEL,
        "index": index_name,
        "namespace": str(ns),
        "top_k": args.top_k,
        "match_count": len(rows),
        "matches": rows,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("=== P2 Pinecone retrieval audit (no Gemini QA) ===")
    print(f"QUERY_RAW     = {args.query!r}")
    print(f"EMBED_MODEL   = {EMBEDDING_MODEL}")
    print(f"INDEX         = {index_name}")
    print(f"NAMESPACE     = {ns}")
    print(f"TOP_K         = {args.top_k}")
    print(f"MATCHES       = {len(rows)}")
    print()

    needle = "box 4.3"
    found_box = False
    for r in rows:
        tlow = (r.get("text") or "").lower()
        if needle in tlow:
            found_box = True
        print(f"--- RANK={r['rank']} SCORE={r['score']} ID={r['id']} ---")
        meta = r.get("metadata") or {}
        for k in sorted(meta.keys()):
            v = meta[k]
            if isinstance(v, str) and len(v) > 120:
                v = v[:120] + "…"
            print(f"  metadata.{k} = {v!r}")
        print(f"  TEXT_PREVIEW_400 = {r['text_preview_400']!r}")
        print()

    print("=== Manual check ===")
    print("Search previews above for: Box 4.3, cotton farmers, seven factors, 36%–120%, etc.")
    print(f"HINT_BOX_4_3_STRING_IN_ANY_CHUNK = {found_box}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
