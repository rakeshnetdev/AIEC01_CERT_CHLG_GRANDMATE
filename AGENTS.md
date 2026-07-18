# AGENTS.md — Grandmate

> **Grandmate — *your grandmaster mate.*** Project constitution for AI coding agents (Antigravity,
> Cursor, Claude Code). Shared, cross-tool rules live here. Tool-specific behavior lives in its own
> file and defers to this one for anything cross-cutting: `CLAUDE.md` (Claude Code),
> `final_docs/GEMINI.md` (Antigravity). The phase-by-phase build spec is in **`docs/PLAN.md`**.

## What we are building
Grandmate: give it a Lichess/Chess.com username (or paste a game); it uses **Stockfish** to find
blunders/mistakes/inaccuracies, explains each in plain English (grounded via RAG), remembers the
player's recurring weaknesses across sessions, and recommends targeted drills. **Frontend:** React +
Vite + TypeScript + Tailwind CSS. **Backend:** FastAPI (Python). Scope = one end-to-end loop.
See `docs/ARCHITECTURE.md` for design, `docs/PLAN.md` for the phased build, `docs/Deliverables.md`
for the graded self-assessment.

## ⚙️ Workflow protocol (enforce strictly)
1. **One phase at a time**, in `docs/PLAN.md` order. Do not start phase N+1 until N is done.
2. **Plan before code.** For each phase, produce a short plan and **wait for approval** before
   touching files.
3. **"Done" = acceptance tests pass.** Run the phase's tests with **`uv run pytest`** (from
   `backend/`) and confirm green output. No green, no advance.
4. **Stop at each phase boundary**, show the diff, and commit as `phase N: <summary>`.
5. **Tests alongside code** — every new module gets tests in the same phase.
6. **Comment for humans** — docstrings/JSDoc on public functions; explain non-obvious logic inline.
7. **Never expand scope.** If a change isn't in `docs/PLAN.md`, ask first. Missing detail → pick the
   simplest option consistent with the Golden Rules, leave a `# NOTE:`, and move on.
8. **Secrets via `.env` only** — never commit keys.
9. **Branching & Pull Requests (critical):** work on a feature branch. Do not commit or push directly
   to `main`. Push only to the feature branch and let the user merge via PR.

## 🧪 Engineering rules
- **TDD (red → green → refactor):** write the failing test first, then the minimal code to pass, then
  refactor. No implementation lands without a test that exercises it.
- **Frontend/backend separation:** `frontend/` (React + Vite + TypeScript + Tailwind) and `backend/`
  (FastAPI + Python) are separate folders. ALL domain logic, the engine, and API keys live in
  `backend/`. The frontend only renders and calls the backend over the documented HTTP API — no
  chess logic or secrets in the frontend.
- **Explicit API contract:** the backend exposes typed request/response models; the frontend has a
  typed API client (`frontend/src/lib/api.ts`) that mirrors them. Changing the contract updates both
  sides plus a test.
- **Docs are part of done:** update the relevant doc in the same commit as the code. Code and docs
  never drift. `final_docs/` (a git submodule) holds the phase-by-phase learning log, metrics vs.
  rubric, and the graded write-up — update it per the process already established there for any
  phase work that lands in it.

## 🔑 Golden rules (non-negotiable)
1. **The LLM never analyzes a position.** All move facts come from tools: **Stockfish** (eval, best
   move, PV) and **python-chess** (legality). The LLM only *narrates* verified facts.
2. **Ground-check every generated move.** Any move named in output must be legal AND in the engine PV;
   else drop/regenerate it. Set `Explanation.grounded` accordingly.
3. **Typed contracts at every seam** (`backend/src/coach/schemas/models.py`).
4. **Determinism first.** Fixed engine depth from settings; same game + depth ⇒ same labels.
5. **No runtime network installs.** Pin deps. Stockfish path comes from `.env`.
6. **Cache** engine evals (key FEN+depth) and HTTP (key URL) — analysis is the latency bottleneck.
7. **Fail loud, degrade gracefully.** One un-analyzable ply logs + skips; it never crashes a report.
8. **Memory is required.** Persist a per-user learner profile across sessions.
9. **Hybrid Retrieval (RRF):** RAG context comes from hybrid dense vector search combined with BM25
   sparse lexical search fused via Reciprocal Rank Fusion, over a **dual-corpus bucketed** index
   (`rules/` vs `strategies/` in `backend/data/corpus/`, tagged by metadata `bucket`).
10. **Grounding Guard is dual-mode:** a deterministic python-chess legality scan (chat default, low
    latency) and an LLM-as-judge semantic check (initial review), with automatic fallback to the
    deterministic mode if the judge call fails. Every attempt is logged as a `GroundingEvent`.
11. **Developer Graph Inspector:** the frontend exposes a collapsible, real-time panel tracing
    Stockfish metrics, RAG queries/contexts, and active LLM system prompts (Graph Execution
    Inspector, incl. the 🛡️ Grounding tab).

## Tech stack
**Frontend:** React + Vite + **TypeScript** + Tailwind CSS (npm).
**Backend:** Python 3.11+ · **FastAPI** · **LangGraph** (orchestration + memory) · **LiteLLM** gateway
→ **Gemini 1.5 Flash** primary (`LLM_MODEL=gemini/gemini-1.5-flash`), **OpenAI GPT-4o** fallback ·
**ChromaDB** (local dev) / **Qdrant Cloud** (deployed) vectors · OpenAI embeddings
(`text-embedding-3-small`) · **Stockfish** + python-chess · **RAGAS** + pytest (uv).
**Deploy:** Vercel (frontend) + Render/Docker (backend, ships the Stockfish binary). SQLite for the
learner profile.
> Tavily and a puzzle DB exist in `backend/pyproject.toml`/`.env.example` from an earlier iteration
> but are **not** part of the active architecture — see `docs/ARCHITECTURE.md` and the commit that
> moved them to the backlog. Don't wire new features to them without checking current scope first.

## Repository map
```
grandmate/
├── AGENTS.md CLAUDE.md README.md      # this file, Claude Code notes, project overview
├── docs/                        # live architecture, plan, deliverables (source of truth)
│   ├── ARCHITECTURE.md  PLAN.md  Deliverables.md  synthetic_data_and_eval_design.md
│   ├── retriever_evaluation_report.md  diagrams/
├── backend/                     # FastAPI + Python — ALL logic, engine, keys (uv)
│   ├── app.py                   # FastAPI: POST /review, POST /chat, GET /health
│   ├── config/settings.py       # pydantic-settings (engine path, models, thresholds, keys)
│   ├── src/coach/                # schemas, llm/gateway, ingestion, analysis, rag, tools, agent, guardrails
│   ├── data/corpus/              # rules/ + strategies/ bucketed RAG corpus
│   ├── tests/                    # test_phaseN_*.py  (TDD — write first)
│   ├── pyproject.toml  .env.example  Dockerfile
├── frontend/                    # React + Vite + TS + Tailwind — UI only (npm)
│   ├── src/                     # components/, lib/api.ts (typed client → BACKEND_URL)
│   ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
│   └── .env.example             # VITE_BACKEND_URL
├── final_docs/                  # git submodule: per-phase learning log, metrics, graded write-up,
│                                 #   plus Antigravity's GEMINI.md
└── evals/                       # shared eval harness + metrics report
```

## Conventions
- **Backend:** full type hints, Pydantic v2, pure functions (pass `Engine`/`Settings`/index in
  explicitly); raise typed exceptions; `logging` (no `print` outside `app.py`/`render.py`); `pytest`.
- **Frontend:** TypeScript **strict**; React function components + hooks; Tailwind utilities;
  a single typed API client (`lib/api.ts`) mirroring the backend contract; no business logic.
- **Package managers:** backend **uv**; frontend **npm** (Vite). Fall back to pip only if uv absent.
- **Tools (MCP-style):** JSON-serializable in/out; validate inputs; side-effect-free except
  reads/caching.

## Commands
```bash
# backend
cd backend && uv venv && uv pip install -e ".[dev]"
uv run uvicorn app:app --reload            # API → http://localhost:8000
uv run pytest tests/ -q                    # full suite (or tests/test_phaseN_*.py for one phase)
# frontend
cd frontend && npm install
npm run dev                                # UI → http://localhost:5173
```

## Definition of done (per phase)
Acceptance tests green · new code has tests + docs · committed as `phase N: …` · no scope beyond
`docs/PLAN.md` · Golden Rules upheld · frontend holds no logic/keys.
