# PLAN.md — Phased Implementation Plan (Grandmate · Certification Challenge)

Agent-buildable plan for **Grandmate** — *your grandmaster mate* — scoped to the Certification
Challenge (due **7pm ET, July 16**) and architected so Copilot/Claude (Antigravity) can implement it
phase-by-phase. Pairs with `CAPSTONE_BRIEF.md`/`SUBMISSION.md` (graded write-up) and `ARCHITECTURE.md`.

> **Drive it:** give the agent this file + `AGENTS.md`, then *"Implement Phase N. Obey the Golden
> Rules + Engineering Rules. Make the phase's acceptance tests pass, then stop."* Build in order.

## 🔑 Golden rules (never violate)
1. **The LLM never analyzes a position.** Facts come from Stockfish (eval/best/PV) + python-chess.
2. **Ground-check every generated move** — legal in the position AND in the engine PV, else drop it.
3. **Typed contracts at every seam** (`backend/src/coach/schemas/models.py`).
4. **Deterministic detection** (fixed engine depth); reproducible labels.
5. **Memory is required** — persist a per-user learner profile across sessions.
6. **Browser-deployable** — a React SPA on phone + laptop via a public URL.
7. **Secrets via env only**; cache engine + HTTP calls.
8. **TDD + frontend/backend separation + metrics-after-each-phase + docs-in-same-commit** — see
   `AGENTS.md` → **Engineering Rules**.
9. **Hybrid Retrieval (RRF):** Fuses dense vector search and BM25 sparse search via RRF rank aggregation.
10. **Developer Graph Inspector:** Toggable and dynamic real-time tracing of RAG, Stockfish, and prompt states.

## Challenge → implementation map
| Cert task | Delivered by |
|---|---|
| T1 Problem/audience/scope | `CAPSTONE_BRIEF.md` / `SUBMISSION.md` |
| T2 Solution + infra + agent diagrams | `CAPSTONE_BRIEF.md` + `ARCHITECTURE.md` |
| T3 Data (chunking, source, external API) | Phase 3 (RAG) + Phase 1 (tools) |
| T4 End-to-end prototype + deploy | Phases 1–5 + Phase 7 |
| T5 Evals | Phase 6 |
| T6 Advanced retriever + 2nd improvement | Phase 8 |
| T7 Next steps | `CAPSTONE_BRIEF.md` §7 |

## Target stack
**Frontend:** React + Vite + **TypeScript** + Tailwind CSS + shadcn/ui (npm).
**Backend:** Python 3.11 + **FastAPI** · **LangGraph** (orchestration + memory) · **LiteLLM** gateway
→ **Gemini 1.5 Flash** via your `GEMINI_API_KEY` (fallback: **OpenAI GPT-4o** via `OPENAI_API_KEY`) ·
**ChromaDB** (vectors; local) / **Qdrant Cloud** (deployed) · OpenAI embeddings · **Stockfish**
+ python-chess · **RAGAS** + pytest · **LangSmith** (tracing) · **Docker + Render** (backend) +
**Vercel** (frontend). SQLite for the learner profile.

> **LLM gateway = LiteLLM** (satisfies the cert "gateway" requirement) but calls providers **directly
> with your own keys** — no OpenRouter. Primary `gemini/gemini-1.5-flash`; fallback `gpt-4o`.
> **Tavily and the puzzle DB are not part of the active architecture** — they appear in the phase
> notes below as originally planned, but were moved to the backlog / "next steps" (see
> `docs/ARCHITECTURE.md` and `Deliverables.md` §8.4). Don't wire new work to them without checking
> current scope.

## Repository structure  (frontend/backend separated — see AGENTS.md → Engineering Rules)
```
grandmate/
├── README.md ARCHITECTURE.md PLAN.md CAPSTONE_BRIEF.md SUBMISSION.md AGENTS.md GEMINI.md START_HERE.md
├── backend/                   # FastAPI + Python — ALL logic, engine, keys (uv)
│   ├── Dockerfile  pyproject.toml  .env.example
│   ├── app.py                 # FastAPI: POST /review, POST /chat, GET /health
│   ├── config/settings.py
│   ├── src/coach/
│   │   ├── schemas/models.py  # Pydantic contracts (build first)
│   │   ├── llm/gateway.py     # LiteLLM: Gemini primary → OpenAI fallback
│   │   ├── ingestion/{chesscom.py,lichess.py,pgn.py,puzzles.py}
│   │   ├── analysis/{engine.py,classify.py,themes.py,pipeline.py}
│   │   ├── rag/{corpus.py,index.py,retrieve.py}
│   │   ├── tools/{fetch_games.py,engine_eval.py,opening_explorer.py,tavily_search.py,legal_moves.py}
│   │   ├── agents/{explainer.py,weakness.py,drills.py}
│   │   ├── memory/profile.py  # SQLite learner profile
│   │   ├── graph.py           # LangGraph orchestrator
│   │   ├── report/{assemble.py,render.py}
│   │   └── guardrails.py
│   ├── data/corpus/           # openings.tsv + concept notes *.md
│   └── tests/                 # test_phaseN_*.py  (TDD — write first)
├── frontend/                  # React + Vite + TS + Tailwind + shadcn/ui — UI only (npm)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── components/        # Decomposed UI modules
│   │   │   ├── Header.tsx
│   │   │   ├── AnalysisForm.tsx
│   │   │   ├── CoachSummary.tsx
│   │   │   ├── MoveBreakdown.tsx
│   │   │   ├── DevInsights.tsx
│   │   │   └── ChatPanel.tsx
│   │   └── lib/api.ts         # Client endpoints (e.g. fetchCarlsenGames)
│   ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
│   └── .env.example           # VITE_BACKEND_URL
├── final_docs/                # per-phase learning log · metrics (vs rubric) · project_plan (updated each phase)
└── evals/{generate_synthetic.py,test_detection.py,test_grounding.py,test_rag.py,report.py}
```

## Dependencies
**Backend** (`backend/pyproject.toml`):
```
python-chess>=1.999  httpx>=0.27  pydantic>=2.6  pydantic-settings>=2.2
langgraph>=0.2  langchain-core>=0.3  litellm>=1.50            # gateway: Gemini + OpenAI (your keys)
openai>=1.40                                                  # embeddings + litellm openai provider
chromadb>=0.5  qdrant-client>=1.11  rank-bm25>=0.2
tavily-python>=0.5  fastapi>=0.115  uvicorn>=0.30  ragas>=0.1  langsmith>=0.1
zstandard>=0.22  pandas>=2.2  sqlmodel>=0.0.22
# dev: pytest, pytest-asyncio, ruff   |   SYSTEM: stockfish (via Docker)
```
**Frontend** (`frontend/package.json`): `react`, `react-dom`, `vite`, `typescript`,
`tailwindcss`, `@tanstack/react-query` (or fetch), shadcn/ui components (`npx shadcn@latest add …`).
Install: backend `uv venv && uv pip install -e ".[dev]"`; frontend `npm install`.

## Data contracts (build in Phase 0)
```python
# backend/src/coach/schemas/models.py
from pydantic import BaseModel
from typing import Literal, Optional
Severity = Literal["ok","inaccuracy","mistake","blunder"]
Source   = Literal["lichess","chesscom","upload"]

class Game(BaseModel):
    game_id: str; source: Source; pgn: str
    white: str; black: str
    white_rating: Optional[int]=None; black_rating: Optional[int]=None
    result: str; time_control: Optional[str]=None
    user_color: Literal["white","black"]; opening_name: Optional[str]=None

class EngineEval(BaseModel):
    best_uci: str; pv_uci: list[str]; score_cp: int   # side-to-move POV, mate clamped ±10000

class MoveAnalysis(BaseModel):
    ply: int; fen_before: str
    played_uci: str; played_san: str; best_uci: str; best_san: str
    eval_before_cp: int; eval_after_cp: int; centipawn_loss: int
    label: Severity; theme: Optional[str]=None; pv_san: list[str]=[]

class Chunk(BaseModel): id: str; text: str; source: str; theme: Optional[str]=None
class Explanation(BaseModel):
    ply: int; label: Severity; why: str; correct_plan: str
    sources: list[str]=[]; grounded: bool=False
class Weakness(BaseModel): theme: str; count: int; example_plies: list[int]
class Drill(BaseModel): puzzle_id: str; theme: str; rating: int; url: str
class CoachReport(BaseModel):
    username: str; games_reviewed: int; summary: str
    findings: list[Explanation]; top_weaknesses: list[Weakness]; drills: list[Drill]
    latency_s: float=0.0; cost_usd: float=0.0
    game_status: Optional[str]=None; game_result: Optional[str]=None
```

---

# Phase 0 — Backend scaffold, contracts, engine, LiteLLM gateway
**Goal:** runnable backend skeleton; contracts, Stockfish, and the LiteLLM gateway wired.
**Files:** `backend/pyproject.toml`, `.env.example`, `config/settings.py`, `schemas/models.py`,
`analysis/engine.py`, `llm/gateway.py`, `tests/test_phase0.py`.
**Interfaces:**
```python
class Settings(BaseSettings):           # config/settings.py
    stockfish_path: str; engine_depth: int = 16
    inaccuracy_cp: int = 50; mistake_cp: int = 100; blunder_cp: int = 300
    gemini_api_key: str                             # primary (Google Gemini)
    openai_api_key: Optional[str] = None            # fallback (OpenAI)
    llm_model: str = "gemini/gemini-1.5-flash"          # LiteLLM model id (primary)
    llm_fallback_model: str = "gpt-4o"              # LiteLLM model id (fallback)
    embed_model: str = "text-embedding-3-small"
    qdrant_url: Optional[str] = None; tavily_api_key: Optional[str] = None
    db_path: str = "coach.db"

class Engine:                           # analysis/engine.py
    @classmethod
    def from_settings(cls, s) -> "Engine": ...
    def __enter__(self)->"Engine": ...;  def __exit__(self,*e): ...
    def analyse_fen(self, fen: str, depth: int|None=None) -> EngineEval: ...

# llm/gateway.py — LiteLLM; providers called DIRECTLY with your keys (no OpenRouter).
# Reads GEMINI_API_KEY / OPENAI_API_KEY from env. Primary = settings.llm_model (Gemini);
# on error, LiteLLM falls back to settings.llm_fallback_model (OpenAI).
#   from litellm import completion
#   completion(model=s.llm_model, messages=msgs, fallbacks=[s.llm_fallback_model])
def chat(messages: list[dict], model: str|None=None, **kw) -> str: ...
```
**Acceptance:** ✓ `analyse_fen(startpos)` returns a best move and |cp|<100 · ✓ `chat([...])` returns
text via Gemini (and via OpenAI when Gemini is forced to fail) · ✓ schemas validate · ✓ pytest green.
**Agent prompt:** *"Implement Phase 0: backend scaffold, Settings, Pydantic contracts, the Stockfish
`Engine`, and the LiteLLM `chat()` gateway (Gemini primary via GEMINI_API_KEY, OpenAI fallback via
OPENAI_API_KEY — no OpenRouter). Make tests/test_phase0.py pass. No later phases."*

---

# Phase 1 — Ingestion + tools
**Goal:** fetch/normalize games (Lichess, Chess.com, pasted PGN upload); expose agent tools.
**Files:** `ingestion/{lichess.py,chesscom.py,pgn.py}`,
`tools/{fetch_games.py,legal_moves.py,engine_eval.py}`, `tests/test_phase1.py`.
**Interfaces:**
```python
def fetch_lichess_games(username, max_games=10, token=None) -> list[Game]: ...
def fetch_chesscom_games(username, months=1, max_games=10) -> list[Game]: ...
def parse_pgn(pgn: str, source: Source, username: str) -> Game: ...     # supports pasted upload
def iter_positions(game: Game):  ...                                     # yields (ply, board, move)
def fetch_games(username, source, max_games) -> list[dict]:  ...         # tool
def legal_moves(fen: str) -> list[str]:  ...                             # tool
def engine_eval(fen: str, depth: int) -> dict:  ...                      # tool
```
**Tasks:** serialize Chess.com calls (429 backoff); Lichess NDJSON export; PGN paste path; cache HTTP.
**Acceptance:** ✓ username → N normalized `Game`s with correct `user_color` · ✓ pasted PGN parses ·
✓ `legal_moves` accepts `e2e4`, rejects `e2e5`.

---

# Phase 2 — Analysis engine (deterministic core)
**Goal:** per-move centipawn loss, severity, theme.
**Files:** `analysis/{classify.py,themes.py,pipeline.py}`, `tools/engine_eval.py`, `tests/test_phase2.py`.
**Centipawn-loss method (exact):** `S_best = analyse(fen_before).score_cp` (mover POV); push played
move; `S_played = -analyse(fen_after).score_cp`; `cpl = max(0, S_best - S_played)` (clamp mates).
Analyze **only the user's moves**.
**Acceptance:** ✓ played==best ⇒ cpl 0, label ok · ✓ a Lichess game with `??` NAGs → those plies
flagged `blunder` · ✓ every result ply is the user's color.

---

# Phase 3 — RAG (Agentic RAG data layer)
**Goal:** concept corpus + uploaded data indexed; theme-aware retrieval; agentic public search (Tavily).
**Files:** `rag/{corpus.py,index.py,retrieve.py}`, `tools/{opening_explorer.py,tavily_search.py}`,
`data/corpus/*`, `tests/test_phase3.py`.
**Chunking (cert T3):** openings TSV = 1 opening/chunk; concept notes = 1 concept/chunk (~300 tok,
15% overlap); uploaded games = 1 annotated move/chunk. Metadata: `theme`, `source`, `eco`.
**Acceptance:** ✓ retrieval returns theme-relevant chunks · ✓ `tavily_search` returns results ·
✓ uploaded PGN contributes chunks.

---

# Phase 4 — Agents + memory + LangGraph orchestrator
**Goal:** grounded explainer, weakness/drills, the required memory component, and the orchestrator.
**Files:** `agents/{explainer.py,weakness.py,drills.py}`, `ingestion/puzzles.py`,
`memory/profile.py`, `graph.py`, `report/{assemble.py,render.py}`, `tests/test_phase4.py`.
**Interfaces:**
```python
def explain(ma, retrieved, searched, s) -> Explanation: ...
def ground_check(text: str, ma: MoveAnalysis) -> bool: ...          # legal + in PV
def summarize_weaknesses(a: list[MoveAnalysis], top_n=3) -> list[Weakness]: ...
class PuzzleIndex:  # load(csv_zst) ; query(themes, rating, count) -> list[Drill]
class LearnerProfile:  # SQLite: get(username) -> dict|None ; update(username, weaknesses, rating, summary)
def build_graph(deps) -> "CompiledGraph": ...   # route→fetch→analyze→explain→weakness→drills→memory→report
def review(username, source, max_games=10) -> CoachReport: ...
```
**Memory (required):** each review reads `LearnerProfile.get` to personalize, then `update(...)`
rolling theme counts + a session summary. LangGraph checkpointer holds conversation state.
**Acceptance:** ✓ end-to-end `review()` → `CoachReport` · ✓ `ground_check` rejects illegal/off-PV ·
✓ second review reflects remembered weaknesses · ✓ drills within rating ±150.

---

# Phase 5 — Backend API + React frontend (browser, phone + laptop)
**Goal:** expose the loop as a FastAPI HTTP API; build a **separate React (Vite+TS) frontend** that
calls it; guardrails on.
**Files:** `backend/app.py`, `backend/src/coach/guardrails.py`, `backend/tests/test_phase5.py`;
`frontend/` (Vite + React + TS + Tailwind + shadcn/ui) — `src/lib/api.ts`, `src/pages/`, `src/components/`.
**Interfaces:**
```python
# backend/app.py (FastAPI)
POST /review  {username, source, max_games} -> CoachReport (JSON)
POST /chat    {message, session_id}         -> {reply, report?}
GET  /health                                 -> {status:"ok"}
def validate_request(text: str) -> None      # non-chess refusal, input checks (backend)
def is_safe_output(text: str) -> bool         # kid-appropriate content (backend)
```
```ts
// frontend/src/lib/api.ts — typed client mirroring the backend contract
export async function review(username: string, source: string, maxGames: number): Promise<CoachReport>
```
**Separation rule:** the frontend holds NO chess logic and NO API keys — only `VITE_BACKEND_URL`.
Build UI with shadcn/ui components (chat input, report cards, weakness list, drill links).
**Acceptance:** ✓ `POST /review` returns a valid CoachReport (pytest, no frontend) · ✓ the React app
renders a report in a laptop + phone browser · ✓ non-chess prompt refused by the backend · ✓ frontend
has no engine/LLM keys · ✓ `tsc` type-checks clean.
**Agent prompt:** *"Implement Phase 5: a FastAPI backend (/review, /chat, /health) with guardrails
(all logic in backend), and a separate React + Vite + TypeScript + Tailwind + shadcn/ui frontend with
a typed API client calling VITE_BACKEND_URL. TDD. Keep the frontend logic-free. Pass tests."*

---

# Phase 6 — Evals (cert Task 5)
**Goal:** synthetic + assembled test sets; two-layer harness; baseline conclusions.
**Files:** `evals/{generate_synthetic.py,test_detection.py,test_grounding.py,test_rag.py,report.py}`.
**Metrics/targets:** detection F1 ≥ 0.90 · severity acc ≥ 0.85 · illegal/off-PV rate 0% · RAGAS
faithfulness ≥ 0.85 · LLM-judge coaching ≥ 4/5.
**Acceptance:** ✓ detection F1 ≥ target · ✓ 0 grounding violations · ✓ RAGAS ≥ target (xfail if
provider offline) · ✓ `run_all()` writes `evals/report.json`.

---

# Phase 7 — Deploy backend + frontend to public endpoints (cert Task 4)
**Goal:** a public backend API and a public React frontend, reachable on phone + laptop.
**Files:** `backend/Dockerfile`, frontend Vercel config, deploy notes in `README.md`.
**Tasks:** (1) **Backend:** Docker base + `apt-get install stockfish`, install deps with **`uv`**
(`pip install uv && uv pip install --system -e .`), `CMD uvicorn app:app --host 0.0.0.0 --port $PORT`;
set env (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, Qdrant); deploy to Render; note its URL.
(2) **Frontend:** `npm run build` → deploy the Vite app to **Vercel** with `VITE_BACKEND_URL` = the
backend URL. Verify end-to-end from a phone.
**Acceptance:** ✓ backend `/health` + `/review` respond over HTTPS · ✓ the Vercel frontend loads on
phone + laptop and talks to the backend · ✓ keys live only in the backend service.

---

# Phase 8 — Advanced retriever + 2nd improvement (cert Task 6)
**Goal:** measurable retrieval upgrade with before/after evidence.
**Tasks:** (1) hybrid BM25+dense with cross-encoder rerank + theme-metadata filter; (2) a second
improvement (structure-aware chunking, citation-forcing explainer prompt, or theme query expansion) —
each proven with the harness.
**Acceptance:** ✓ comparison table (baseline vs advanced) on RAGAS context precision/recall · ✓ the
2nd change shows a meaningful, harness-backed gain.

---

# Phase 9 — Multi-agent refactor + dual-corpus RAG + deploy readiness
**Goal:** break the monolithic `narrator_agent` into a specialist team, split the corpus by domain,
make the coordinator cheap, and fix what only broke in the deployed build.
**Tasks:** (1) rewire the graph to **router → specialist → synthesizer** (`router_agent_node`,
`strategy_node`, `rules_node`, `synthesizer_node`, `should_delegate`), specialists looping back to the
router, guard retries targeting the synthesizer; (2) **router fast-pathing** — decide deterministically
whenever state implies the outcome, calling the LLM only for a genuine `HumanMessage` follow-up with no
findings yet; (3) **dual-corpus bucketed RAG** — `data/corpus/rules/` (incl. `FIDE - LawsOfChess.pdf`)
vs. `data/corpus/strategies/`, `bucket` metadata on every chunk, filter applied to both dense and BM25
halves before RRF; (4) **agent tracing** — `AgentStep` + `execution_log` on `DeveloperInsight`, surfaced
as the **agents** and **logs** tabs of the Graph Execution Inspector; (5) **deploy fixes** — narrow the
corpus-eating `data/` ignore rule to `/data/chroma/`, drop the hardcoded developer path in
`/carlsen-games`, and keep the PGN dropdown rendered-but-disabled when no games load.
**Acceptance:** ✓ `tests/test_phase9.py` green (bucketed retrieval per specialist + `should_delegate`)
· ✓ router costs 0 LLM calls on `/review` and 1 on a `/chat` turn (see `ARCHITECTURE.md` §4 and
`diagrams/router-fast-pathing.md`)
· ✓ `git ls-files backend/data` lists both corpus buckets and `Carlsen.pgn`.

---

## ⏱️ Cert-Challenge sprint (now → 7pm ET, July 16)
| When | Do | Cert coverage |
|---|---|---|
| Day 1 AM | Phase 0 + Phase 1 | T4 start |
| Day 1 PM | Phase 2 + Phase 3 | T3 |
| Day 1 late | Phase 4 (explainer + memory + graph) | T2/T4 |
| Day 2 AM | Phase 5 (backend API + React frontend) + Phase 7 (deploy) | T4 deploy |
| Day 2 PM | Phase 6 (evals) + Phase 8 (advanced retriever) | T5, T6 |
| Day 2 late | Fill `SUBMISSION.md` numbers; record **Loom**; push repo | T1–T7 + submission |

**Minimum viable cut if time is tight:** Lichess-only ingest, Chroma instead of Qdrant, 3 games/review,
Tavily as the one external agent tool, a minimal React UI (single page), hybrid retriever as the only
Task-6 improvement. Everything still satisfies every cert deliverable.

## Demo Day extension (after the challenge)
- Richer React UI (board visualizations, eval graphs) + multi-turn **conversational tutor** on the
  grounded core (teach → quiz → adapt via memory).
- Opponent scouting (multi-agent deep research); broader concept corpus; optional **RLVR** annotation
  model with engine-verified rewards; voice.

## Definition of Done (challenge)
- [ ] Public React frontend runs a full review on phone + laptop, talking to the FastAPI backend
- [ ] Uploaded personal data (PGN) + Tavily agentic search both used (Agentic RAG)
- [ ] Memory personalizes a returning user
- [ ] 0% illegal/hallucinated moves; detection F1 ≥ target in the harness
- [ ] Advanced retriever before/after table produced
- [ ] `AGENTS.md`, `ARCHITECTURE.md`, `PLAN.md`, `README.md`, `SUBMISSION.md`, code, and Loom in the repo
