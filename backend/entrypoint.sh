#!/usr/bin/env bash
# Container entrypoint.
#
# The vector store is deliberately NOT baked into the image. It is excluded by
# .dockerignore, and building it during `docker build` would embed vectors produced by
# whichever embedding backend was reachable at build time. If that differed from the one
# used to answer queries at runtime, retrieval would compare vectors from two different
# spaces and quietly return poor matches. Ingesting here, with the runtime credentials,
# keeps both sides on the same embedding model.
#
# Ingestion is skipped when the store already holds documents, so a container restart with
# a persistent disk attached costs nothing.
set -euo pipefail

python - <<'PYEOF'
import sys
from config.settings import get_settings
from coach.rag.vector_db import get_collection
from coach.rag.pipeline import ingest_corpus

settings = get_settings()
corpus = "data/corpus"

try:
    count = get_collection(settings.chroma_db_path).count()
except Exception as exc:
    print(f"[startup] could not read vector store ({type(exc).__name__}); will ingest.", flush=True)
    count = 0

if count > 0:
    print(f"[startup] vector store already holds {count} chunks; skipping ingestion.", flush=True)
    sys.exit(0)

print(f"[startup] vector store empty — ingesting corpus from {corpus} ...", flush=True)
try:
    ingest_corpus(corpus, settings.chroma_db_path)
    print(f"[startup] ingestion complete: {get_collection(settings.chroma_db_path).count()} chunks.", flush=True)
except Exception as exc:
    # A failure here means retrieval will return nothing. Say so loudly rather than
    # letting the service come up looking healthy while its core feature is dead.
    print(f"[startup] INGESTION FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("[startup] the service will start, but RAG retrieval will return no results.", flush=True)
PYEOF

exec uvicorn app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
