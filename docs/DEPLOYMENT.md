# Deployment

Backend runs as a Docker container on **Render**. Frontend is a static build on **Vercel**.

Everything below has been verified against a real container build except where explicitly marked
*not verified*.

---

## 1. What the container does at startup

The vector store is **not** baked into the image. `backend/entrypoint.sh` builds it on first boot,
then starts the server.

This is deliberate. Building it during `docker build` would embed vectors produced by whichever
embedding backend was reachable at build time. If that differed from the one used to answer
queries later, retrieval would compare vectors from two different spaces and quietly return poor
matches. Ingesting at startup, with the runtime credentials, keeps both sides on the same model.

Ingestion is skipped when the store already holds documents, so a restart with a disk attached
costs nothing. If it fails, the service still starts but logs plainly that retrieval will return
nothing — rather than coming up "healthy" with its core feature dead.

Expected first-boot log:

```
[startup] vector store empty — ingesting corpus from data/corpus ...
[startup] ingestion complete: 339 chunks.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 2. Backend on Render

### 2.1 Deploy

1. Push this branch to GitHub.
2. Render dashboard → **New** → **Blueprint** → select the repository.
   Render reads [`render.yaml`](../render.yaml) at the repo root and creates the service.
3. Open the service → **Environment**, and set the three secrets. They are declared
   `sync: false` in the blueprint, which means Render creates them **empty** on purpose — the
   blueprint never contains secret values.

   | Variable | Required | Notes |
   |---|---|---|
   | `OPENAI_API_KEY` | **yes** | Used for both embeddings and the coach. Ingestion fails without it. |
   | `GEMINI_API_KEY` | no | Only if you switch `LLM_MODEL` to a Gemini model. |
   | `LANGSMITH_API_KEY` | no | Enables tracing. |

4. Deploy. First boot runs ingestion, so allow a few minutes before the health check passes —
   `start-period` in the Dockerfile healthcheck is set to 90s for this reason.

### 2.2 Settings that matter

Set as plain values in `render.yaml`, safe to change there:

| Variable | Value | Why |
|---|---|---|
| `LLM_MODEL` | `gpt-4o-mini` | Both the coach and, in evaluation, the judge. |
| `LLM_FALLBACK_MODEL` | `gpt-4o-mini` | Must be a real model id — a typo here means every fallback 404s. |
| `CHROMA_DB_PATH` | `/app/data/chroma` | Must match the disk `mountPath` below. |
| `USE_LLM_JUDGE` | `false` | Reviews use the deterministic move-legality check rather than the LLM reviewer. Set `true` to re-enable the semantic check. |

`PORT` is injected by Render. The Dockerfile and its healthcheck both read it rather than
assuming 8000 — do not hardcode a port.

### 2.3 The disk

```yaml
disk:
  name: chroma-data
  mountPath: /app/data/chroma
  sizeGB: 1
```

With a disk, the corpus is ingested once and survives restarts. Without one — Render's free tier
has no persistent disks and sleeps when idle — every cold start re-ingests, costing embedding
calls and delaying readiness. The blueprint therefore requests the `starter` plan.

---

## 2b. Backend on Fly.io (alternative to Render)

`backend/fly.toml` is the equivalent configuration. It sits in `backend/` because Fly uses the
directory containing `fly.toml` as the Docker build context, and the Dockerfile copies
`pyproject.toml`, `uv.lock` and `src/` from the backend root.

```bash
cd backend
fly launch --no-deploy                          # first time only, creates the app
fly volumes create chroma_data --size 1 --region ord
fly secrets set OPENAI_API_KEY=...              # never stored in fly.toml
fly deploy
```

Differences from Render worth knowing:

| | Render | Fly.io |
|---|---|---|
| Scale to zero | no (starter plan) | yes — `auto_stop_machines`, which is what keeps it near-free |
| Persistent disk | `disk:` block | `[[mounts]]` + `fly volumes create` |
| Secrets | dashboard | `fly secrets set` |

The volume matters more than it looks. Measured on a real container:

| Boot | Volume state | Result | Time to healthy |
|---|---|---|---|
| first | empty | ingested 339 chunks | ~90s |
| second | populated | ingestion skipped | **12s** |

Without a volume every cold start re-ingests the corpus — 339 chunks of embedding calls, and a
slow boot each time. That is the real cost of a free tier with no persistent storage, not compute.

### Other options

Any platform that runs a real container will work; Stockfish is a binary, so serverless function
runtimes are out. Cloud Run and Koyeb run the image but offer no persistent disk on their free
tiers, so both re-ingest on every cold start. Free-tier terms change often — verify current limits
rather than trusting this table.

---

## 3. Frontend on Vercel

1. Vercel → **New Project** → import the repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset is detected as Vite. `frontend/vercel.json` pins the build command, output
   directory, and the SPA rewrite that sends unknown paths to `index.html`.
4. Add one environment variable:

   ```
   VITE_BACKEND_URL = https://<your-service>.onrender.com
   ```

   No trailing slash. See `frontend/.env.example`.

> **Vite bakes `VITE_*` values into the bundle at build time.** Changing `VITE_BACKEND_URL` in
> Vercel requires a **redeploy**, not just a restart. If the frontend is calling `localhost` in
> production, it was built without the variable set.

---

## 4. Verified

Against a real `docker build` and a running container:

| Check | Result |
|---|---|
| Image builds | pass |
| No `.env` or key material in any layer | pass |
| `.venv`, `tests`, local `data/chroma` excluded | pass |
| Runs as non-root (uid 10001) | pass |
| Stockfish reachable at the configured path | pass |
| Corpus ingestion | 339 chunks |
| `GET /health` | `{"status":"ok"}` |
| `POST /review` (real Lichess game) | HTTP 200, 49 moves, RAG context populated |
| Backend test suite | 34 passed |

Image size is about **1.68 GB**, mostly `chromadb` and `onnxruntime`. Deploys are slow but work.

**Not verified:** the frontend build. `node`/`npm` were unavailable on the machine used, so
`npm run build` was never executed. `vercel.json` is valid JSON and `VITE_BACKEND_URL` matches
what `frontend/src/lib/api.ts` reads, but the build itself is unproven — check the first Vercel
build output rather than assuming.

---

## 5. Known issues before going public

- **CORS is wide open.** `backend/app.py` sets `allow_origins=["*"]` together with
  `allow_credentials=True`. That combination is invalid per the CORS specification and works only
  because the app sends no cookies. Restrict it to the Vercel domain before a public launch.
- **First request after a cold start is slow.** The engine cache and the lexical index are both
  empty, so the first review pays for building them. Measured at ~28s cold in the container.
- **Free tier sleeps.** A sleeping service loses its non-disk state, so it re-ingests on wake.

---

## 6. Troubleshooting

| Symptom | Cause |
|---|---|
| `[startup] INGESTION FAILED: RateLimitError ... insufficient_quota` | OpenAI billing exhausted. The key is valid; the account has no credit. |
| Analysis returns no moves | Stockfish not found. apt installs it to `/usr/games/stockfish`, which is **not on PATH**; the Dockerfile symlinks it to `/usr/local/bin/stockfish`, where `settings.py` looks. |
| Answers contain no retrieved context | Ingestion failed or the disk is mounted somewhere other than `CHROMA_DB_PATH`. Check the startup log for the chunk count. |
| Frontend calls `localhost` in production | Built without `VITE_BACKEND_URL`. Set it in Vercel and **redeploy**. |
| Every model call fails once before succeeding | `LLM_MODEL` names a model that does not exist. Check the exact id. |
