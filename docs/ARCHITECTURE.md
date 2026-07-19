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
4. **Memory is first-class.** Today this means conversation-scoped memory — a LangGraph checkpointer
   that lets a review and its follow-up chat share state. A durable, per-user profile that persists
   across sessions is the intended design and the product's whole point (required by the challenge),
   but it is **not yet built** — see §6 and `Deliverables.md` §8.5.
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
*(Copy in [`diagrams/component-architecture.md`](diagrams/component-architecture.md).)*

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
    U["User input: pasted PGN / question"] --> FETCH[fetch_and_analyse]
    FETCH --> ROUTE{Router Agent}

    ROUTE -- "small talk (0 LLM calls)" --> DONE([Canned reply — ends turn])
    ROUTE -- "strategy only" --> STRAT[strategy_node]
    ROUTE -- "rules only" --> RULES[rules_node]
    ROUTE -- "both (parallel fan-out)" --> STRAT
    ROUTE -- "both (parallel fan-out)" --> RULES
    ROUTE -- "neither needed" --> SYNTH[synthesizer_node]

    STRAT --> SYNTH
    RULES --> SYNTH

    SYNTH --> GUARD{Grounding Guard}
    GUARD -- approved --> WEAK[Top weaknesses]
    GUARD -- rejected (retry < 3) --> SYNTH

    WEAK --> WRITE[Update learner memory]
    WRITE --> REPORT[Render report]
    REPORT --> FOLLOW[Follow-up in chat]
    FOLLOW -.-> ROUTE
```
*(Copy in [`diagrams/agent-workflow.md`](diagrams/agent-workflow.md).)*

**Multi-agent topology.** The single `narrator_agent` was replaced by a **router → specialist →
synthesizer** team: `router_agent_node` classifies intent and dispatches, `strategy_node` and
`rules_node` each own one domain and one corpus bucket, and `synthesizer_node` fuses their findings
into the one answer the user reads. The `should_delegate` conditional edge maps the router's
`dispatch_targets` onto the next node — or onto *both* specialist nodes at once, by returning a
list, which is how LangGraph fans out to parallel branches. Specialists edge straight to
`synthesizer_node`; nothing loops back to the router.

**One-shot dispatch.** `router_agent_node` is entered **exactly once per invocation** and decides
everything for that turn in a single visit. It reaches for the LLM only when genuine intent
classification is required:

| Turn | `dispatch_targets` | LLM call |
|---|---|---|
| Initial `/review` (no messages) | `["strategy"]` | none |
| Pure small talk ("hi", "thanks") | `["end"]` — canned reply, ends the turn | none |
| Chat, strategy question | `["strategy"]` | 1 |
| Chat, rules question | `["rules"]` | 1 |
| Chat, needs both | `["strategy", "rules"]` — parallel fan-out | 1 |
| Chat, neither specialist needed | `[]` — straight to synthesis | 1 |

Rules deliberately does not run on a plain review: there is no rules question to answer. Small talk
skips the synthesizer *and* the grounding guard, since a canned reply names no moves and so has
nothing to legality-check.

```mermaid
stateDiagram-v2
    [*] --> FetchAndAnalyse
    FetchAndAnalyse --> RouterAgent

    state RouterAgent {
        [*] --> CheckState
        CheckState --> NoMessages: initial /review
        CheckState --> SmallTalk: whole-message greeting/thanks match
        CheckState --> Classify: a real question

        NoMessages --> [*]: dispatch_targets = ["strategy"] (free)
        SmallTalk --> [*]: canned reply, ends turn (free)
        Classify --> [*]: calls chat() once (the only LLM cost)
    }

    RouterAgent --> [*]: small talk — no synthesis, no grounding
    RouterAgent --> StrategyNode: "strategy", or initial review
    RouterAgent --> RulesNode: "rules"
    RouterAgent --> SynthesizerNode: nothing needed

    state Both <<fork>>
    RouterAgent --> Both: classified "both"
    Both --> StrategyNode
    Both --> RulesNode

    StrategyNode --> SynthesizerNode
    RulesNode --> SynthesizerNode

    SynthesizerNode --> GroundingGuard
    GroundingGuard --> [*]: approved
    GroundingGuard --> SynthesizerNode: rejected, retry_count < 3

    note right of RouterAgent
        Entered once per turn. The
        "both" case fans out to two
        parallel branches in one
        superstep; both edge into
        SynthesizerNode, which runs
        once after both finish.
    end note
```

**Parallel writes need reducers.** Because both specialists can run in the same superstep, every
state key either of them writes must be `Annotated` with a reducer — otherwise LangGraph raises
`InvalidUpdateError: can receive only one value per step`. `execution_logs` and `agent_steps`
already appended; `rag_context` required a `merge_rag_context` reducer. `strategy_findings` and
`rules_findings` are distinct keys and never collide.

**Findings persist.** `synthesizer_node` no longer clears `strategy_findings` / `rules_findings`,
so a review's specialist work stays available as background context for later chat turns in the
same thread. This is safe only because dispatch is one-shot — under the earlier design, which
inspected those fields to decide the next hop, persisted findings would have mis-routed every
subsequent turn.

> **Superseded:** phase 9 used a five-branch fast-path table and looped specialists back through
> the router to sequence them. That design is recorded in
> [`final_docs/implementation/phase9.md`](../final_docs/implementation/phase9.md); phase 10 replaced
> it with the one-shot dispatch above. See
> [`final_docs/implementation/phase10.md`](../final_docs/implementation/phase10.md) for the
> rationale, including the routing defect that made the specialist layer inert on reviews.

**Net effect.** An initial `/review` costs **0 router LLM calls** — dispatch is implied by state.
A `/chat` follow-up costs exactly **one** classification call, whether it dispatches to one
specialist, both, or neither; the "both" case runs the two specialists concurrently rather than
chaining them. Pure small talk costs **nothing at all** and skips synthesis and grounding entirely.
*(Copy in [`diagrams/router-dispatch.md`](diagrams/router-dispatch.md).)*

## 4a. Request lifecycle (end-to-end sequence)
Traces a click in the browser all the way through the FastAPI route, the LangGraph
router/specialist/synthesizer team, Stockfish/RAG, and the LiteLLM gateway, back to the UI — for
both entry points the frontend calls. *(Copy in [`diagrams/request-lifecycle.md`](diagrams/request-lifecycle.md).)*

**Flow A: `POST /review` (initial game analysis).** Router LLM cost: **0 calls** — every routing
decision is implied by state (see the fast-pathing table above); only the specialist/synthesis/guard
nodes call the gateway.

```mermaid
sequenceDiagram
    participant UI as App.tsx [React]
    participant Client as api.ts [Client]
    participant API as app.py::review_game [FastAPI]
    participant Graph as graph.py [LangGraph]
    participant Eng as engine.py [Stockfish]
    participant RAG as rag/pipeline.py [Hybrid RRF]
    participant GW as gateway.py [LiteLLM]

    UI->>Client: handleAnalyze() (AnalysisForm onSubmit) -> reviewGame(payload)
    Client->>API: HTTP POST /review {username|pgn, source}
    API->>API: validate_request() (guardrail)
    API->>Graph: coach_graph.invoke(inputs, config={thread_id})
    Note over Graph: fetch_and_analyse_node
    Graph->>Eng: analyze_game() -> per-move centipawn loss + severity
    Note over Graph: router_agent_node (no HumanMessage yet -> fast-path, 0 LLM calls)
    Graph->>RAG: strategy_node: retrieve_context(bucket="strategies")
    Graph->>GW: strategy_node: chat() -> strategy findings
    Note over Graph: router_agent_node (strategy done -> fast-path to rules, 0 calls)
    Graph->>RAG: rules_node: retrieve_context(bucket="rules")
    Graph->>GW: rules_node: chat() -> rules findings
    Note over Graph: router_agent_node (both gathered -> fast-path to synthesizer, 0 calls)
    Graph->>GW: synthesizer_node: chat() -> fused narrative
    Graph->>GW: grounding_guard_node: chat() (LLM-as-a-Judge, initial review)
    alt rejected, retry_count < 3
        Graph->>GW: synthesizer_node: chat() again (with critique feedback)
    end
    Graph->>API: returns final_state
    API->>API: is_safe_output() (guardrail) + assemble CoachReport
    API->>Client: CoachReport JSON
    Client->>UI: setReport(data) -> dashboard re-renders
```

**Flow B: `POST /chat` (follow-up question).** Router LLM cost: **1 call** — the router is entered
once and classifies intent in that single visit, then dispatches to one specialist, both in
parallel, or neither. Pure small talk is matched deterministically and costs **0 calls**, skipping
synthesis and the grounding guard entirely.

```mermaid
sequenceDiagram
    participant UI as App.tsx [React]
    participant Client as api.ts [Client]
    participant API as app.py::chat_message [FastAPI]
    participant Graph as graph.py [LangGraph]
    participant RAG as rag/pipeline.py [Hybrid RRF]
    participant GW as gateway.py [LiteLLM]

    UI->>Client: handleSendChat() (ChatPanel onSubmit) -> chatMessage(payload)
    Client->>API: HTTP POST /chat {message, session_id}
    API->>API: validate_request() (guardrail; off-topic -> short-circuit reply)
    API->>Graph: coach_graph.get_state(config={thread_id})
    alt no game loaded in this thread
        API->>Client: {"reply": "Please load and analyze a game first"} (no graph invoke)
    else game loaded
        API->>Graph: coach_graph.invoke({messages:[HumanMessage]}, config)
        Note over Graph: router_agent_node (HumanMessage, no findings yet -> 1 LLM call)
        Graph->>GW: router_agent_node: chat() -> classify "strategy" or "rules"
        Graph->>RAG: delegated specialist: retrieve_context(bucket=...)
        Graph->>GW: delegated specialist: chat() -> findings
        Note over Graph: router_agent_node (one specialist done -> fast-path to the other, 0 calls)
        Graph->>GW: second specialist: chat() -> findings
        Graph->>GW: synthesizer_node: chat() -> fused reply
        Note over Graph: grounding_guard_node forced to deterministic mode (chat follow-up)
        Graph->>API: returns final_state
        API->>API: extract last AIMessage as reply + rebuild DeveloperInsight
        API->>Client: {"reply": ..., "developer_insight": {...}}
    end
    Client->>UI: append reply to conversation
```

## 5. Data flow & contracts
Ingestion → Analysis → RAG/Explain → Weakness → Drills → Report, each a typed boundary:

```
Game[]  ──►  MoveAnalysis[]  ──►  Explanation[]  ──►  Weakness[] + Drill[]  ──►  CoachReport
(fetch)      (Stockfish)         (RAG + guard)        (aggregate themes)        (render)
```
Full Pydantic definitions live in `PLAN.md` / `src/coach/schemas/models.py`. The key rule: an
`Explanation` is only emitted with `grounded = true` after the legality + PV check.

## 6. Memory design (required component)
One tier shipped, one tier still open:
- **Conversation memory (built).** `src/coach/agent/memory.py` wraps a LangGraph `MemorySaver()` —
  an in-process, in-RAM checkpointer keyed by `thread_id` (`review_{username}` or `session_id`). It
  lets a review and its follow-up chat share state within one session, and `/chat` checks
  `coach_graph.get_state()` before invoking the graph, so a message sent to an empty or expired
  thread (e.g. right after a server restart) gets a friendly "please load and analyze a game first"
  reply instead of a 500. **Limitation:** it's a dict in memory, not a database — a server restart
  wipes every thread's state, and a new `thread_id` (a new session, a different day) has no link to
  a user's previous ones.
- **Learner profile (durable, not yet built).** The intended design — a SQLite table keyed by
  `username`, updated with rolling weakness-theme counts after each review and read back in on a
  return visit ("last time back-rank tactics were your weak spot — let's see if it improved") — is
  what would close the learning loop this product is built around. No `learner_profile` table or
  `LearnerProfile` class exists in the code today. Effort estimate and implementation plan tracked
  as `Deliverables.md` §8.5.

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
*(Copy in [`diagrams/grounding-guard-sequence.md`](diagrams/grounding-guard-sequence.md).)*

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
*(Copy in [`diagrams/deployment-topology.md`](diagrams/deployment-topology.md).)*

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
