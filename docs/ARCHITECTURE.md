# Architecture — Grandmate

Deep architecture reference for the Certification Challenge build. Pairs with `CAPSTONE_BRIEF.md`
(the graded write-up) and `PLAN.md` (the phased build). Diagrams are GitHub-native Mermaid.

---

## 1. Design principles (the invariants)
1. **Tool-grounded correctness.** The LLM never analyzes a position. Move facts come only from
   Stockfish (evaluation, best move, PV) and python-chess (legality). The LLM *narrates* verified
   facts. A grounding guard re-checks every move the LLM names.
2. **Deterministic core, generative shell.** Detection/classification are deterministic and
   reproducible; only the explanation prose is generative.
3. **Typed contracts at every seam.** Modules exchange Pydantic models, never loose dicts.
4. **Memory is first-class.** A per-user learner profile persists across sessions (required by the
   challenge and the product's whole point).
5. **Browser-first, phone + laptop.** The interface is a hosted responsive web chat.

---

## 2. Component architecture
```mermaid
flowchart TB
    subgraph Client["Client - Phone and Laptop Browser"]
      UI["React SPA (Vite + TS)"]
    end

    subgraph Edge["Deployment - Render (Docker)"]
      API["FastAPI app"]
      ORCH["LangGraph orchestrator"]
      MEM[("SQLite learner profile")]
      CACHE[("Cache - Engine + HTTP")]
    end

    subgraph AI["AI layer"]
      GW["LiteLLM gateway"]
      LLM["Gemini 1.5 Flash + OpenAI GPT-4o fallback"]
      EMB["OpenAI embeddings"]
      VDB[("ChromaDB vector store")]
    end

    subgraph Tools["Agent tools (MCP-style)"]
      SF["Stockfish"]
      PC["python-chess"]
      LI["Lichess / Chess.com API"]
    end

    UI --> API --> ORCH
    ORCH --> GW --> LLM
    ORCH --> MEM
    ORCH --> CACHE
    ORCH --> Tools
    ORCH --> EMB --> VDB
    ORCH -. "traces" .-> MON["LangSmith"]
```

## 3. Component rationale & tradeoffs

| Component | Choice | Why | Tradeoff / alternative |
|---|---|---|---|
| LLM gateway | LiteLLM | One endpoint, many models, hot-swap for eval | LiteLLM proxy (self-host) if cost/routing control needed |
| LLM | Gemini 1.5 Flash (primary, `LLM_MODEL=gemini/gemini-1.5-flash`) | Strong reasoning; native to the Antigravity workflow | OpenAI GPT-4o fallback on error |
| Orchestration | LangGraph | Stateful graph + checkpointer = built-in memory | Plain sequential orchestrator (simpler, less flexible) |
| Vector DB | ChromaDB | Embedded local storage, supports BM25 index & vector retrieval | Qdrant hosted alternative |
| Embeddings | `text-embedding-3-small` | Cheap, strong recall | `bge-small` OSS to remove a vendor dependency |
| Engine | Stockfish (Docker) | Free, deterministic ground truth | Lichess Cloud Eval as a fast-path cache |
| Frontend | React + Vite + TS + Tailwind + shadcn/ui | Modern typed SPA; clean FE/BE boundary | Next.js if SSR needed |
| Deploy | Render + Docker + Vercel | Ships the Stockfish binary on Render backend; Vercel hosts frontend React SPA | Fly.io / Railway |
| Monitoring | LangSmith | Native LangGraph tracing + cost metrics | Custom logging |
| Evals | A custom pytest harness + LLM-as-judge | Semantic + deterministic layers | promptfoo / Tau2 for agent-level sims |

## 4. Agent workflow (control flow)
```mermaid
flowchart TD
    U[User input] --> FETCH[fetch_and_analyse]
    FETCH --> RAG_C[retrieve_rag_context]
    RAG_C --> ROUTE{Router Agent}
    
    ROUTE -- "delegate (strategy)" --> STRAT[strategy_node]
    ROUTE -- "delegate (rules)" --> RULES[rules_node]
    ROUTE -- "done / direct" --> SYNTH[synthesizer_node]
    
    STRAT --> ROUTE
    RULES --> ROUTE
    
    SYNTH --> GUARD{Grounding Guard}
    GUARD -- approved --> WEAK[Top weaknesses]
    GUARD -- rejected (retry < 3) --> SYNTH
    
    WEAK --> WRITE[Update learner memory]
    WRITE --> REPORT[Render report]
    REPORT --> FOLLOW[Follow-up in chat]
    FOLLOW -.-> ROUTE
```

**Multi-agent topology.** The single `narrator_agent` was replaced by a **router → specialist →
synthesizer** team: `router_agent_node` classifies intent and delegates, `strategy_node` and
`rules_node` each own one domain and one corpus bucket, and `synthesizer_node` fuses their findings
into the one answer the user reads. Specialists loop back to the router so it can sequence them; the
`should_delegate` conditional edge maps `delegated_specialist` onto the next node.

**Router fast-pathing.** `router_agent_node` decides *deterministically* wherever the outcome is
already implied by state, and only calls the LLM for genuine intent classification:

| Router state | Decision | LLM call |
|---|---|---|
| `strategy_findings` **and** `rules_findings` set | → `synthesizer_node` | none |
| only `strategy_findings` set | → `rules_node` (sequential chaining) | none |
| only `rules_findings` set | → `strategy_node` (sequential chaining) | none |
| no `HumanMessage` in state (initial `/review`) | → `strategy_node` (default) | none |
| `HumanMessage` present, no findings yet (chat follow-up) | classify intent | **1 call** |

This removes one LLM call per turn on both `/review` and `/chat` without reducing specialist
coverage. Before/after diagrams and the full call accounting live in `final_docs/change_document.md`.

## 5. Data flow & contracts
Ingestion → Analysis → RAG/Explain → Weakness → Drills → Report, each a typed boundary:

```
Game[]  ──►  MoveAnalysis[]  ──►  Explanation[]  ──►  Weakness[] + Drill[]  ──►  CoachReport
(fetch)      (Stockfish)         (RAG + guard)        (aggregate themes)        (render)
```
Full Pydantic definitions live in `PLAN.md` / `src/coach/schemas/models.py`. The key rule: an
`Explanation` is only emitted with `grounded = true` after the legality + PV check.

## 6. Memory design (required component)
Two tiers:
- **Conversation memory** — LangGraph checkpointer keyed by session/thread; enables multi-turn
  follow-ups within a review.
- **Learner profile (durable)** — a SQLite table keyed by `username`:
  ```
  learner_profile(username PK, rating, games_reviewed,
                  weakness_themes JSON,   # rolling counts by theme
                  last_reviewed_at, history JSON)
  ```
  On each review the agent updates rolling theme counts and stores the session summary. On a return
  visit it reads the profile so the coach can say "last time back-rank tactics were your weak spot —
  let's see if it improved." This closes the learning loop the current-state workflow lacks.

## 7. RAG subsystem (Dual-Corpus Bucketed Retriever)
- **Partitioned Corpus**: The corpus is organized into two distinct directories under `backend/data/corpus`:
  * **`rules/`**: Official tournament rules and arbiter regulations, including `FIDE - LawsOfChess.pdf` parsed page-by-page. `pypdf` is declared in `backend/pyproject.toml`, so `load_pdf` ingests the rulebook alongside the markdown notes (175 of the index's 339 chunks).
  * **`strategies/`**: Openings database and general tactical motifs (TSVs row-by-row, markdown by headers).
- **Index**: Embedded locally using ChromaDB with metadata-tagging `{"bucket": "rules"}` or `{"bucket": "strategies"}` for every chunk.
- **Bucketed Retriever**: Updates retrieval functions to accept an optional `bucket` filter. Dense queries apply metadata `where={"bucket": bucket}`. Sparse BM25 queries filter candidate documents prior to scoring, and hybrid RRF fuses results from the filtered subsets to prevent concept bleed.

## 8. Grounding guard (anti-hallucination & semantic validation)

The application employs a dual-mode **Grounding Guard** integrated as a conditional node in LangGraph to ensure 0% move hallucinations and strategic correctness:

```mermaid
sequenceDiagram
    participant E as Explainer LLM
    participant G as Grounding Guard (LangGraph Node)
    participant J as LLM-as-a-Judge
    participant C as python-chess (Deterministic)
    
    E->>G: Draft explanation narrative
    alt Mode: LLM-as-a-Judge (Active for Initial Review)
        G->>J: Grade draft for strategic concept accuracy & move validity
        J-->>G: JSON feedback (explanation_approved: true/false, critique)
    else Mode: Deterministic Fallback / Chat Follow-up
        G->>C: Scan text for SAN moves & verify legality in game FENs
        C-->>G: Validation results (approved: true/false)
    end
    
    alt Approved
        G-->>E: Finalize report and exit graph
    else Rejected (up to 3 retries)
        G-->>E: Loop back with critique feedback to regenerate explanation
    end
```

### Validation Modes
1. **Option A: Deterministic Legality Guard (Active / Chat Default)**
   * **Mechanism:** Scans the text using algebraic notation regex: `\b[KQRBN]?[a-h1-8]?x?[a-h][1-8][+#]?\b|O-O(?:-O)?`.
   * **Verification:** Loads each FEN state into a `python-chess.Board` to verify move legality dynamically (~5ms execution latency).
   * **Chat Opt-in:** Enforced on all chat messages to keep response times low while ensuring move legality.
2. **Option B: Semantic Correctness Guard (LLM-as-a-Judge)**
   * **Mechanism:** Queries a secondary LLM node with game context, engine data, and the draft narrative text.
   * **Verification:** The judge LLM verifies the correctness of strategic advice (e.g. ensuring a move is not mislabeled as a "fork" when it's a "pin") and returns a structured JSON approval status.
   * **Fallback:** If the judge API call fails or outputs invalid formatting, the guard automatically falls back to deterministic check to ensure resilience.

### Graph Routing & Debugging
* **LangGraph Feedback Edge:** If validation fails, the graph state incrementing `retry_count` routes the state back to the `synthesizer_node` with the critique feedback. If it fails 3 times, it continues to prevent infinite loops.
* **Developer Insights Tracing:** Every grounding attempt is recorded as a `GroundingEvent` in the state's `grounding_log` and rendered in the frontend's **Graph Execution Inspector** under the **🛡️ Grounding** tab.

## 8a. Developer Insights tracing (agent-level observability)
Every node records what it was asked and what it answered, so the whole multi-agent run is
inspectable from the browser without a LangSmith account:
- **`AgentStep`** (`agent_name`, `prompt`, `response`) — appended by each node to the state's
  `agent_steps` list. The `prompt` is the flattened LLM conversation rendered as
  `[ROLE]: content` lines; fast-pathed router visits record a `(Fast-path — …)` /
  `(Skipped — …)` marker instead, which makes the saved LLM call visible on screen.
- **`execution_log`** — a plain-text trail of what each node did (documents retrieved, specialist
  selected, grounding verdict), in execution order.
- Both are carried on the `DeveloperInsight` payload returned by `/review` and `/chat`, and surfaced
  in the frontend **Graph Execution Inspector** (`DevInsights.tsx`), which exposes six tabs:
  **engine · rag · prompt · grounding · agents · logs**.

## 9. Deployment topology (frontend & backend are separate services)
```mermaid
flowchart LR
    Dev[Local dev] --> Repo[GitHub]
    Repo --> BE[Backend: FastAPI + Stockfish - Render web service]
    Repo --> FE[Frontend: React SPA - Vite/TS - Vercel]
    BE --> Qdrant[(Qdrant Cloud)]
    BE --> GW[LiteLLM -> Gemini / OpenAI]
    FE -- HTTP VITE_BACKEND_URL --> BE
```
- **MVP:** two deployables — a **backend** (Dockerized FastAPI + Stockfish; holds all logic, keys,
  Qdrant, LiteLLM→Gemini/OpenAI) on **Render**, and a **frontend** (React SPA built with Vite) on
  **Vercel** that calls the backend via `VITE_BACKEND_URL`. Both are public HTTPS on phone + laptop.
- **Later:** enrich the React frontend (board visualizations, eval graphs) — the backend is unchanged.
- **The image must ship the data.** `backend/data/corpus/` (both buckets) and
  `backend/data/pgn/Carlsen.pgn` are tracked in git and therefore present in the Render build; only
  the generated vector store (`/data/chroma/`) is ignored. A bare `data/` ignore pattern matches at
  every directory level and silently drops the corpus and sample games from the deploy — the backend
  then starts cleanly with no knowledge base at all. `git ls-files backend/data` is the check.

## 10. Non-functional concerns
- **Latency:** engine analysis dominates → cap depth, cache by FEN+depth, bound games per review,
  analyze plies concurrently within limits.
- **Cost:** gateway + monitoring track $/report; small model for routing/summaries.
- **Guardrails:** input validation, non-chess refusal, kid-appropriate content filter.
- **Reliability:** one un-analyzable ply is logged and skipped, never crashes a report.
- **Secrets:** API keys via environment variables only; never committed.
