# Grandmate: AI-Powered Chess Analysis and Personalized Helper

This document compiles the complete set of deliverables and self-assessment records for the Grandmate Chess Helping Agent, fulfilling the requirements for the AI Makerspace Certification Challenge.

## Table of Contents
1. [Problem Definition & Target Audience](#1-problem-definition--target-audience)
2. [Proposed Solution & Architecture](#2-proposed-solution--architecture)
3. [Data Strategy & Chunking](#3-data-strategy--chunking)
4. [Full-Stack Prototype & Deployment](#4-full-stack-prototype--deployment)
5. [Evaluation Framework & Results](#5-evaluation-framework--results)
6. [Advanced Retrieval & Iterative Improvements](#6-advanced-retrieval--iterative-improvements)
7. [Future Reflections](#7-future-reflections)
8. [Next Steps for Demo Day](#8-next-steps-for-demo-day)

---

## 1. Problem Definition & Target Audience

### 1.1 Problem Statement
> Current chess software tells players **that** their moves are bad using abstract mathematical scores, but fails to explain **why** they were errors in simple, human language, leaving players, parents, and coaches guessing at how to improve.

### 1.2 Target Audience & Users
* **Primary Audience (Amateur Players):** Online players rated roughly **800–1800** on Lichess or Chess.com who play regularly and want to improve, but get frustrated by raw engine numbers (`-2.60`) that offer no plan.
* **Secondary Audience (Parents of Juniors):** Parents who want to support their child's chess education but are completely locked out of the learning process because chess notations and statistics read like code.
* **Tertiary Audience (Chess Coaches & Academies):** Coaches who instruct dozens of students and need a simple dashboard to track their students' historical weaknesses and auto-generate drills.

### 1.3 Why This is a Problem
After a loss, the player wants to understand their mistakes and turn them into a concrete lesson. Today they open the platform's computer analysis, click through an evaluation bar, and see centipawn numbers (e.g. "−2.6") with no explanation. They may Google the opening, ask a Discord server, or guess.

A human coach could explain it — but coaches cost **$30–100/hour**, strong ones are scarce, and they review perhaps one game per session. So the player is left with raw numbers they cannot interpret, no personalization, no guidance on what learning topics to focus on, and no memory of the mistakes they keep repeating. Parents are locked out of supporting their children because chess statistics look like code, and coaches cannot manually track recurring weakness logs for dozens of students over months of play. Ultimately, the player is left guessing and plays the next game making the same errors.

### 1.4 Current Workflow & Bottlenecks
The diagram below illustrates how amateur chess players attempt to learn from their games today:

```mermaid
flowchart LR
    A[Finish an online game] --> B["Open Lichess/Chess.com computer analysis"]
    B --> C[Click through the evaluation bar move by move]
    C --> D{Understand WHY the move was bad?}
    D -- No --> E[See only centipawn numbers -2.6]
    E --> F["Google the opening / ask a Discord or a friend"]
    F --> G{Found a clear, personal lesson?}
    G -- Rarely --> H[Guess at what to fix]
    G -- No --> I[Give up and move on]
    D -- Sometimes --> H
    H --> J[Play the next game — repeat the same mistakes]
    I --> J
    classDef pain fill:#ffe0e0,stroke:#d33,color:#900;
    class C,E,F,H,I pain
```
*(Copy in [`diagrams/user-workflow-pain-points.md`](diagrams/user-workflow-pain-points.md).)*

---

## 2. Proposed Solution & Architecture

### 2.1 Solution Description & Naming Rationale
* **Proposed Solution:**
  > A browser-based agentic analysis helper that fetches your games, uses Stockfish to find every mistake, retrieves chess concepts to explain each in plain English (grounded so it never invents lines), remembers your recurring weaknesses across sessions, and recommends targeted drills.
* **Naming Choice (Grandmate / GameMate):**
  The project name **Grandmate** (originally conceived as **GameMate**) is a play on two central chess concepts: **Grandmaster** (the ultimate title of chess expertise) and **Checkmate** (the defining goal of the game). The suffix **"-mate"** also functions in its colloquial sense as a friendly companion or partner. Grandmate thus positions itself not merely as a cold, analytical software tool, but as an interactive, conversational companion helping amateur players learn to analyze their games with Grandmaster-level clarity.

### 2.2 System Infrastructure Architecture
The following infrastructure diagram outlines the decoupled full-stack architecture of the prototype:

```mermaid
flowchart LR
    subgraph Client["Browser - Phone and Laptop"]
      UI["React SPA (Vite + TS)"]
    end
    UI --> API["FastAPI backend"]
    API --> ORCH["LangGraph orchestrator + memory"]
    ORCH --> GW["LiteLLM LLM gateway"]
    GW --> LLM["Gemini 1.5 Flash / OpenAI GPT-4o fallback"]
    ORCH --> MEM[("Learner profile - SQLite")]
    subgraph TOOLS["Agent tools"]
      SF["Stockfish engine"]
      PC["python-chess legality"]
      LI["Lichess / Chess.com API"]
    end
    ORCH --> TOOLS
    subgraph RAGSYS["RAG"]
      EMB["OpenAI embeddings"] --> VDB[("ChromaDB")]
    end
    ORCH --> RAGSYS
    ORCH -. "traces" .-> MON["LangSmith"]
    API --- EVAL["pytest harness"]
    API --> DEP["Render + Docker + Vercel"]
```
*(Copy in [`diagrams/system-infrastructure.md`](diagrams/system-infrastructure.md).)*

### 2.3 Tooling Justifications
* **LLMs:** Gemini 1.5 Flash (primary, `LLM_MODEL=gemini/gemini-1.5-flash`) for reasoning over and narrating verified engine facts, with OpenAI GPT-4o configured via LiteLLM as an automated fallback to prevent service disruptions.
* **Orchestration:** LangGraph state graph with built-in conversational checkpointing to manage the memory-backed analysis loops, wired as a multi-agent router → specialist → synthesizer team.
* **Deterministic Tools:** Stockfish + python-chess to calculate centipawn loss and verify move legality, ensuring the LLM never invents moves or violates rules.
* **Retrieval (RAG):** ChromaDB local vector storage combined with OpenAI embeddings, over a dual-corpus bucketed index (`rules/` vs. `strategies/`) so each specialist agent retrieves only from its own library.
* **Deployment:** Docker + Render for backend hosting (bundling the Stockfish binary), and Vercel for the React Single Page Application (SPA).

### 2.4 Stateful Agent Workflow
The orchestrator routes the user's intent to review games, analyze specific positions, or ask rules/strategy questions:

```mermaid
flowchart TD
    U["User input: pasted PGN / question"] --> FETCH[fetch_and_analyse]
    FETCH --> ROUTE{Router Agent}

    ROUTE -- "small talk (0 LLM calls)" --> DONE([Canned reply — ends turn])
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
*(Copy in [`diagrams/agent-workflow.md`](diagrams/agent-workflow.md).)*

### 2.5 LangGraph State Graph & Node Execution
The multi-agent StateGraph coordinates sequential worker node execution and grounding:
![alt text](stategraph.png)

#### 2.5.1 Detailed State & Node Transitions
1. **`fetch_and_analyse` (Entry Node):**
   * *What it does:* Receives the user's uploaded PGN and runs the Stockfish engine to analyze each move, calculating centipawn loss and labeling mistakes (blunders, mistakes, inaccuracies).
   * *Output:* Populates `analyses` and `game` fields in the state.
2. **`router_agent`:**
   * *What it does:* Inspects conversation history and game state to determine whether rules questions or strategy questions need specialist delegation. Bypasses LLM routing deterministically if findings are already present.
   * *Small-talk short-circuit:* A message that is *purely* a greeting, thanks, or farewell ("hi", "thanks", "bye") is matched against a deterministic allowlist and answered from a template — 0 LLM calls, no specialist, and no grounding guard, since a canned reply names no moves. Matching is whole-message, so a real question that merely opens politely ("Hi, why was my move a blunder?") still reaches normal classification.
3. **`strategy_node`:**
   * *What it does:* Queries the `strategies` RAG database for tactical concepts and positional motifs, executing a specialized strategy coaching prompt.
4. **`rules_node`:**
   * *What it does:* Queries the `rules` RAG database for official rules, stalemate, and legality validations, including the FIDE Laws of Chess PDF ingested page-by-page.
5. **`synthesizer_node`:**
   * *What it does:* Consolidated responder that combines strategy and rules findings into a unified, user-friendly markdown narrative.
6. **`grounding_guard`:**
   * *What it does:* Inspects the narrative draft. The initial `/review` uses the LLM-as-a-Judge check; a chat follow-up (a prior AI turn already exists in state) always forces the fast deterministic python-chess legality check instead, regardless of whether the question was about rules or strategy.
   * *Flow logic:*
     * **Success:** Routes to `END` to deliver the final report to the user interface.
     * **Failure (Critique Loop):** Appends the critique feedback (e.g. *"Move Nf9 is invalid"*) to the state message list and routes the execution back to `synthesizer_node` to rewrite the paragraph (capped at 3 attempts).

---

## 3. Data Strategy & Chunking

### 3.1 Default Chunking Strategy
Grandmate uses structure-aware chunking to ensure that tactical motifs and openings are stored in atomic, context-rich segments:

| Corpus | Bucket | Chunk Unit | Rationale |
| :--- | :--- | :--- | :--- |
| **Openings Dictionary (TSV)** | `strategies` | One opening per chunk (ECO + name + line) | Each opening is a self-contained record; split lines degrade meaning. |
| **Concept Notes (Markdown)** | `strategies` / `rules` | One concept per chunk, header-delimited | Motifs (e.g. forks, back-rank mates) are atomic; headers preserve logical boundaries. |
| **FIDE Laws of Chess (PDF)** | `rules` | Page-by-page, then recursively split (1000 chars, 200 overlap) | Articles run across pages; recursive splitting with overlap keeps a law and its clauses in one chunk. |
| **User Games & Notes (PGN)** | — | One annotated move (comment + position FEN) | Keeps each personalized review tied directly to its exact board state. |

Every chunk is tagged at ingestion with a `bucket` metadata field (`rules` or `strategies`) matching
its parent directory under `backend/data/corpus/`. This is what lets each specialist agent retrieve
strictly from its own library, so rulebook language never bleeds into strategy advice and vice versa.

> **The FIDE Laws of Chess PDF is now ingested.** `pypdf` is declared in `backend/pyproject.toml`, so
> `load_pdf` parses the rulebook page-by-page into the `rules` bucket. The current index holds **339 chunks**
> (`rules`=175, `strategies`=164); rulebook-only queries such as "fifty move rule draw claim" now retrieve
> actual FIDE article text.

---

## 4. Full-Stack Prototype & Deployment

The Grandmate application is built as a completely decoupled architecture, communicating over a structured API contract.

### 4.1 Frontend Stack (Vite + React + TypeScript)
* **What it does:** Provides the premium, dark-mode user interface where players import games, view reports, and ask follow-up questions.
* **Key Features:**
  * **Interactive Conversational Chat Window (Primary):** A dedicated, real-time coaching interface allowing players to ask follow-up questions about the analyzed game (e.g., requesting drill suggestions, opening advice, or tactical explanations). It retains full conversational memory and session state across turns.
  * **Interactive Analysis Dashboard:** Displays the overall game outcome badge (Won/Lost/Draw) and mistake counters (e.g., `1 Blunder · 2 Mistakes`).
  * **Secondary UI Enhancements & Developer Tools:**
    * *Collapsible Developer Insights Panel (Graph Execution Inspector):* A six-tab inspector — **engine · rag · prompt · grounding · agents · logs** — allowing developers/evaluators to view raw Stockfish logs, RAG queries/contexts, the system prompt, the Grounding Guard loop history, the per-agent prompt/response trace (`agent_steps`, each rendered as flattened `[ROLE]: content` lines), and the plain-text `execution_log` trail of every node in execution order.
    * *Quick-Select Helper Dropdown:* Offers 10 pre-filled tactical helper questions. The sample-game (PGN) dropdown always renders — if no games load it appears disabled with a message distinguishing an unreachable backend from a backend that returned zero games.
    * *Inline Chess Move Highlighting:* Automatically formats move coordinates (e.g., `1.e4`, `Nf6`) into clean, dark-slate monospace pills.

### 4.2 Backend Stack (FastAPI + Python)
* **What it does:** Executes the heavy analytical logic, manages agent memory, retrieves context, and validates narration outputs.
* **Key Features:**
  * **LangGraph Multi-Agent Orchestration:** Coordinates the stateful workflow nodes (`fetch_and_analyse` → `router_agent` → `strategy_node` / `rules_node` → `synthesizer_node` → `grounding_guard`), with specialists looping back to the router so it can sequence them, and the router deciding without an LLM call wherever state already implies the next hop.
  * **Dual-Mode Grounding Guard:**
    * *Option A (Deterministic):* Scans narrative outputs using SAN regex and checks move validity on `python-chess.Board` structures. Always active for chat messages (~5ms execution).
    * *Option B (LLM-as-a-Judge):* Evaluates the strategic correctness of the output text (e.g., detecting if a pin is mislabeled as a fork) and outputs JSON feedback to trigger rewrite loops.
  * **Dual-Corpus Hybrid RAG Retriever:** Integrates semantic vector search (ChromaDB) with lexical keyword matching (BM25) fused via **Reciprocal Rank Fusion (RRF)** to retrieve exact opening lines and tactical motifs. The corpus is partitioned into `rules/` and `strategies/` (openings TSV + tactics notes); every chunk carries a `bucket` metadata tag, and the bucket filter is applied to *both* the dense query and the BM25 candidate set before fusion, so a specialist can only retrieve from its own library. (The `rules/` bucket carries the FIDE Laws of Chess PDF parsed page-by-page — see §3.1.)
  * **Optimized Stockfish Analyzer:** Runs multi-ply positional evaluations with a 100ms time cap, achieving a **5x analysis speedup** (~2.2 seconds for a full game analysis).
  * **LiteLLM Gateway:** Interfaces with the Gemini API (Gemini 1.5 Flash) with OpenAI GPT-4o as the secondary failover model, plus exponential backoff retry layers to handle 429 quota limits.

### 4.3 Deployment & Infrastructure
* **What it does:** Hosts the application publicly with HTTPS configuration.
* **Key Features:**
  * **Vercel (Frontend):** Builds and deploys the static React SPA globally with fast CDN routing.
  * **Render + Docker (Backend):** The FastAPI app is containerized via a Dockerfile that downloads and builds the Stockfish binary, exposing the server endpoints to Vercel via CORS.
  * **Local Persistent Storage:** Uses a SQLite database (`coach.db`) to persist the persistent user profiles and memory checkpoints across server restarts.
  * **Corpus Ships With the Image:** `backend/data/corpus/` (both buckets) and `backend/data/pgn/Carlsen.pgn` are tracked in git so the Render build contains them; only the generated vector store (`/data/chroma/`) is ignored. A bare `data/` ignore pattern matches at every directory level and had silently stripped the RAG corpus and sample games from the deploy while everything still worked locally — `git ls-files backend/data` is the guard against that regression.

---

## 5. Evaluation Framework & Results

### 5.1 Golden Evaluation Dataset
Seven scenarios spanning detection, theming, routing, and grounding — each traceable to a concrete
seed position, test, or report field rather than asserted narrative. (An earlier version of this
table included a returning-user memory-recall scenario and an Opening Explorer lookup. The Opening
Explorer row was removed because that tool isn't implemented — it's listed as future work in §8.4.
The memory-recall row was removed because there is no durable, cross-session learner profile in the
code today — only an in-process LangGraph checkpointer that doesn't survive a restart; §7.1's
"Persistent User Learner Profiles" claim describes the intended design, not the current state.)

| ID | User Intent / Input | Expected Agent Action / Narrative Focus | Grounded in |
| :---: | :--- | :--- | :--- |
| **1** | Pasted blunder game (1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7#) | Detects Scholar's Mate; explains f7 weakness; recommends checkmate defense. | Seed position in `evals/generate_synthetic.py` ("Scholar's mate threat on f7"); scored by the detection harness. |
| **2** | Paste game with an en passant option | Evaluates en passant legality; defines the motif; links to rule docs. | Seed position in `evals/generate_synthetic.py`; the `en_passant` slice reaches 100% agreement in the latest run. |
| **3** | Paste game with a pawn promoting on the 7th/8th rank | Detects promotion vs. underpromotion; explains why a queen (or an underpromotion) was correct. | Seed position in `evals/generate_synthetic.py`; the `promotion` slice is the harness's weakest at 71% agreement (§5.2 caveat 2). |
| **4** | Paste game with a tactical fork error | Flags the move attacking 2+ pieces via the deterministic `classify_theme` heuristic; retrieves fork-themed RAG content. | `backend/src/coach/analysis/themes.py::classify_theme` "Fork" branch — a rule, not an LLM guess. |
| **5** | "What is stalemate?" as a chat follow-up after an initial review | Router fast-paths (no reclassification LLM call once findings exist); `rules_node` retrieves from the FIDE PDF bucket; grounding guard is forced to deterministic mode for the chat turn. | `backend/tests/test_phase9.py::test_router_delegates_to_rules`. |
| **6** | Question resulting in hallucination risk | Grounding guard blocks any illegal/off-PV move before it reaches the user. | `evals/test_grounding.py`; `illegal_move_rate` in `evals/report.json`. |
| **7** | "How do I meet the Sicilian?" (strategy question) | `strategy_node` retrieves only from the `strategies` corpus bucket (openings + tactics), never `rules` — the bucket filter is applied before RRF fusion. | `backend/tests/test_phase9.py::test_router_delegates_to_strategy`. |

### 5.2 Evaluation Harness & Results
The test suite utilizes a three-tier evaluation setup aligned directly with the Session 5 systematic metrics-driven development guidelines:
1. **Deterministic Verification:** Runs local unit tests verifying centipawn blunder classifications and python-chess move validation.
2. **Grounding Verification:** Deploys a dual Grounding Guard (deterministic python-chess legality checks + an LLM-as-a-Judge semantic correctness check) to maintain 0% move hallucination rates.
3. **Semantic Quality Verification:** Prompts an LLM-as-judge to evaluate explanation faithfulness and tone clarity against the baseline chess library.

| Metric | Evaluation Source | Target | Measured | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Detection F1 (Blunders)** | Independent Stockfish depth-24 oracle | ≥ 0.90 | **0.9586** | ✅ Pass |
| **Severity Accuracy** | Independent depth-24 oracle | ≥ 0.85 | **0.8940** | ✅ Pass |
| **Hallucinated Move Rate** | python-chess + PV check | 0% | **0.0000%** | ✅ Pass |
| **RAGAS Faithfulness** | Grounded concepts + engine facts | ≥ 0.85 | **0.75** | ❌ Fail |
| **LLM-Judge Helping Quality** | Reference notes | ≥ 4 / 5 | **4.00 / 5** | ✅ Pass |

Measured from `evals/report.py`; raw output retained in `evals/report.json`. The evaluation harness was rebuilt after an audit found the previous version measured nothing; the design and the implementation outcome are recorded in [synthetic_data_and_eval_design.md](./synthetic_data_and_eval_design.md).

> **These are real, falsifiable measurements.** Detection is scored against an *independent* Stockfish depth-24 oracle, not against the function under test; the judged layer is measured against the position each sample actually came from. The qualifications below record how the harness was made honest and where the remaining limits are.

**1. The evaluated model is GPT-4o — confirmed, not assumed.** `gemini/gemini-1.5-flash` (the documented primary) now returns a hard `404 Not Found` from Google's API regardless of key/config: the model has been retired. Every LLM call falls through LiteLLM's fallback to `gpt-4o`, which serves all judged traffic. This isn't a local `.env` gap anymore — it's confirmed against the live API, forcing `LLM_MODEL=gemini/gemini-1.5-flash` explicitly and watching every primary attempt 404. Every LLM-dependent row above describes GPT-4o's behaviour; the "Gemini 1.5 Flash primary" framing elsewhere in this repo's docs no longer reflects what can actually run.

**2. Detection F1 `0.9586` and Severity Accuracy `0.8940` are real, and the harness can now fail.** The previous dataset was labelled by `calculate_cpl_and_label(...)` — the very function then graded against it — so any score was a tautological 1.0. The rebuilt `generate_synthetic.py` no longer imports the production classifier: ground truth comes from Stockfish at depth 24, and the production configuration (depth 16 + production classifier) is scored against it over **n = 151** rows. **Proof it measures something:** corrupting the thresholds so nothing can be classified as a mistake drops F1 from `0.9529` to **`0.1875`** and severity accuracy to `0.4238` — the old harness returned 1.0 under any mutation. This falsification test is the strongest single piece of evidence in the submission. The real error also localises: the `inaccuracy` class agrees only **70%** (the narrow 50–100cp band is hardest to resolve at depth 16), `promotion` **71%**, while `en_passant`, `forced_mate`, and `san_disambiguation` reach 100%; black 80% vs white 95%.

**3. RAGAS Faithfulness `0.75` now fails its `0.85` target.** The old harness's `0.30` and `1.0` readings were both harness artifacts — reconstructing each game as `pgn=f"1. {san_played} *"` discarded `fen_before` and judged mid-game samples against the wrong board, and an empty context silently defaulted the score to `1.0`. The rebuilt harness fixed both: it builds the position from `fen_before` and gives the judge the **engine facts** alongside the RAG context. With the primary model now confirmed as GPT-4o (see caveat 1) rather than Gemini, faithfulness measures **0.75** (n = 2) — below target. Alongside it, illegal-move rate is **0.0%** (n = 2 moves) and coaching quality **4.00/5** (n = 3); every run prints its not-measured accounting (`judge_failures=0, pipeline_failures=0, rows_without_rag_context=1`) instead of defaulting to a pass. At n = 2 this could be sampling noise rather than a real GPT-4o weakness — see caveat 5.

**4. Known caveat — engine non-determinism.** Three runs on the same dataset and depth have now produced F1 `0.9467` / `0.9529` / `0.9586` and severity `0.9073` / `0.8940` / `0.8940` — different labels each time. This is a genuine violation of the "same game + depth ⇒ same labels" rule, most likely Stockfish threading, and it was invisible before because a circular metric is perfectly reproducible. Until it is pinned (e.g. `Threads=1`), the detection figures should be read with a **±0.02 band**, not the tighter ±0.01 previously assumed.

**5. Small-sample caveat on the judged layer.** Faithfulness rests on n = 2, coaching quality and illegal-move rate on n = 3. The numbers are real, but the judged layer is thin — the faithfulness miss above should be treated as a signal to re-run at a larger sample, not as a confirmed regression, before drawing conclusions from it.

*Follow-ups:* decide on a real primary model now that `gemini-1.5-flash` is retired (see caveat 1 — this affects `ARCHITECTURE.md`, `PLAN.md`, and `config/settings.py`, not just this report); pin the engine to remove the non-determinism band; raise the judged-layer sample count, particularly to re-check the sub-target faithfulness score; and add coverage for the router intent/fast-path, guardrail refusals, and memory persistence, which are not yet evaluated.

---

## 6. Advanced Retrieval & Iterative Improvements

### 6.1 Advanced Retrieval: Hybrid RRF Fusion
* **The Problem:** Plain dense vector search often generalizes away exact terms — coordinates like
  `e4`/`f4`, or opening names like "Sicilian Defense" — and returns diluted results.
* **The Fix:** Hybrid Retrieval (BM25 + Dense), fused with Reciprocal Rank Fusion (RRF). BM25
  catches exact matches; dense search catches the meaning; RRF combines both into one ranked list.

### 6.2 RAG Benchmark Comparison
The table below compares the naive dense vector retriever against the Hybrid RRF retriever.

Measured by `evals/compare_retrievers.py` at K=3 over **135 queries derived from the corpus** (40 lexical + 46 extractive + 46 LLM-paraphrase + 3 negative), scored by chunk id, against the 339-chunk dual-corpus index (`rules`=175, `strategies`=164). All three strategies are exercised through the production `retrieve_context(..., retriever_type=, bucket=)`. Full report: [retriever_evaluation_report.md](./retriever_evaluation_report.md); design and outcome in [synthetic_data_and_eval_design.md](./synthetic_data_and_eval_design.md).

Bucketed (production path) — this is how the application actually retrieves, with a `bucket` filter applied to both retrieval halves before fusion:

| Metric | Baseline (Dense-Only) | Sparse-Only (BM25) | Advanced (Hybrid RRF) |
| :--- | :---: | :---: | :---: |
| **Hit Rate @ 3** | 87.1% | 80.3% | 85.6% |
| **Mean Reciprocal Rank (MRR)** | 0.795 | 0.755 | **0.817** |
| **Avg Latency (ms)** | 527ms | 178ms | 344ms |

* **Hybrid RRF wins.** It has the best ranking quality of the three (MRR **0.817**), ahead of dense-only (0.795) and BM25 (0.755). This is the retriever we ship.
* **An earlier "BM25 beats Hybrid" result was a flawed test, now fixed.** The old benchmark used literal lexical terms and verbatim corpus extracts — both easy wins for BM25's word-overlap matching. Once the query set includes genuinely **reworded** LLM paraphrases (closer to what a real user types), Hybrid RRF wins instead. Paraphrases are generated once and cached (`evals/paraphrase_cache.json`) so the test stays repeatable.
* **Bucket filtering helps every retriever.** Splitting the corpus into `rules` and `strategies` buckets, and filtering to the right one, raises Hybrid MRR from **0.710** (unbucketed) to **0.817** (bucketed) — the two corpora no longer bleed into each other. Unbucketed diagnostics: Dense 83.3%/0.684, BM25 78.8%/0.655, Hybrid 84.8%/0.710.
* **Known gap — no relevance floor.** On out-of-corpus questions (Go, football, backgammon), all three retrievers still return **3/3 false positives**. There's no score threshold yet, so RAG always hands back `k` chunks even when none of them are relevant. Not yet fixed.
* *Latency caveat:* Hit Rate and MRR are deterministic and reproduce exactly across runs. Latency is not — it's dominated by the remote embedding call and varies run to run, so read it as an order of magnitude, not a precise number.

---

## 7. Future Reflections

### 7.1 What to Keep
* **Stateful Graph Orchestration (LangGraph):** the conditional routing loops and state schema give
  a robust, clean, and highly debuggable conversation flow (visible via LangSmith tracing).
* **Deterministic Legality Verification (`python-chess`):** relying on a rules engine rather than an
  LLM to check move legality is the single most critical guardrail, guaranteeing a 0% move
  hallucination rate.
* **Personalized coaching as the core value proposition** — today that personalization works
  *within* a single conversation via the LangGraph checkpointer. A durable, cross-session learner
  profile (one that survives a server restart and recognizes a returning user days later) is the
  intended design and the product's whole point, but it is **not yet built** — there is no
  `learner_profile` table or persistence layer in the code today, only the in-process checkpointer.
  This is the most important open item from this reflection, not a shipped strength.

### 7.2 What to Change / Improve
* **Vector Store Migration:** transition from the local ChromaDB instance to a managed vector
  database (such as Qdrant or Pinecone) to ensure persistence, high concurrency, and low latency in
  production.
* **Granular Concept Sheet Chunking:** refine the chunking parser to extract smaller, highly
  specific sub-sections of chess tactics (e.g., separating "relative pin" from "absolute pin") to
  reduce RAG prompt overhead.
* **API Gateway Abstraction:** standardize the LLM routing through a unified LiteLLM middleware
  wrapper to simplify handling future model integrations and fallback policies — and, per §5's
  caveat, to make swapping a retired model a config change instead of a code change.
* **Build the durable learner profile** (carried over from §7.1): a SQLite table keyed by
  `username`, updated after each review with rolling weakness-theme counts, read back in on a
  return visit.

### 7.3 Commercial Vision & Product Opportunities
Grandmate shifts the chess tech market from a simple post-game engine report into a valuable
educational and competitive platform:
* **The "Magnus Translator" (Amateur / Spectator Value):** translates complex computer lines into
  plain-English strategic plans (e.g., *"White played a3 to stop Black's knight from occupying b4
  and taking control of the queenside"*), making raw engine evaluations comprehensible.
* **The Coaching & Platform Dashboard (B2B / Academy Value):** tracks player histories over months
  in a learner profile database to highlight weaknesses (e.g., *"Johnny plays openings well, but has
  a 45% blunder rate in King and Pawn endgames"*), helping coaches manage 20-30 students at scale —
  this depends on the durable learner profile in §7.1/§7.2 being built.
* **Opponent Scouting (Competitive Edge):** scans an opponent's recent games and suggests targeted
  prep plans (e.g., *"Your opponent struggles against the Winawer variation; open with 1.e4"*).

### 7.4 LLM Cost Economics & Hosting Strategy
To minimize execution costs while maintaining accuracy, the system was designed around specific
economic tiers:
* **Cloud APIs:** originally costed against Gemini 1.5 Flash pricing ($0.075 / million input tokens,
  $0.30 / million output tokens, ~$0.0004 USD per game review with zero idle costs). **That model has
  since been retired by Google** (see §5 caveat 1) — every LLM call now runs on the `gpt-4o`
  fallback, so this per-review cost figure needs re-costing against whatever model actually ends up
  primary, not against a model that can no longer be called.
* **Self-Hosted GPU (Llama 3 8B):** ~$0.50–$1.20/hour on GPU clouds. Break-even requires >1.5M
  reviews/month to beat hosted-API pricing.
* **Local Fine-Tuning Roadmap:** host smaller models (e.g., Llama 3.2 3B or Qwen 1.5B) on cheap CPU
  servers ($5–$10/month) after gathering the first 5,000 high-quality reviews as training data.

### 7.5 Active Tools vs. Scaling Architecture
The prototype isolates local tools (Stockfish, python-chess) to ensure speed and a 0% move
hallucination rate. Production scaling would incorporate external resources not active today:
* **Lichess Opening Explorer:** query move frequency and win/loss ratios to ground opening strategy
  advice in empirical database ratios. (Not implemented — see §5.1 row 7.)
* **Tavily Web Search:** resolve non-board queries (e.g., historical players, tournaments) using
  semantic web search to prevent factual hallucinations. (Not implemented.)

---

## 8. Next Steps for Demo Day

To elevate the application from prototype to a market-ready production demo, the following next
steps are planned.

**Suggested build order, and why:**

| Order | Item | Scope | Rationale |
| --- | --- | --- | --- |
| 1 | §8.5 Durable learner profile | Backend-only; ~half a day | The one piece the product's whole personalization pitch (§7.3) depends on. Smallest, most self-contained change of the five — a new SQLite table plus two integration points, no new UI. |
| 2 | §8.1 Interactive chessboard | Frontend-only, no backend changes | Highest visible payoff per unit of effort for a demo; doesn't touch the graph or any of the systems this review just fact-checked. |
| 3 | §8.2 Socratic tutor flow | New stateful LangGraph node + new specialist-style prompt | Meaningfully larger — needs its own place in the router→specialist→synthesizer topology (§4 of `ARCHITECTURE.md`), not just a UI addition. |
| 4 | §8.3 Opponent scouting | New ingestion path (bulk game history) + new aggregation logic | Similar size to §8.2, plus a new external-data dependency (crawling a user's full game history, not just one game). |
| 5 | §8.4 External search + cloud storage | Infrastructure migration (Qdrant) + two new external tool integrations (Tavily, Opening Explorer) | Broadens *breadth* of knowledge rather than deepening the core loop — lowest urgency for a demo, and the largest infrastructure lift of the five. |

