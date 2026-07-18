# ♟️ Grandmate: AI-Powered Chess Analysis & Personalized Helper

> An intelligent, engine-grounded chess analysis agent and conversational coaching helper powered by **LangGraph** and **Agentic RAG**.
> 
> *Naming Note: The project name **Grandmate** (originally conceived as **GameMate**) is a play on two core chess terms—**Grandmaster** (expertise) and **Checkmate** (the game goal)—coupled with the colloquial sense of a friendly companion (**mate**).*

---

## 📚 Documentation Overview

| Document | Purpose | Location |
| :--- | :--- | :--- |
| 📋 **Full Deliverables** | Core challenge deliverables and self-assessment checklists | [docs/Deliverables.md](./docs/Deliverables.md) |
| 🏗️ **System Architecture** | Subsystem flowcharts, request-lifecycle sequences, and deployment topologies | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) |
| 🗺️ **Implementation Plan** | Chronological development phases and engineering logs | [docs/PLAN.md](./docs/PLAN.md) |
| 🖼️ **Diagrams** | Every mermaid diagram referenced above, as standalone files | [docs/diagrams/](./docs/diagrams/) |
| 📊 **Retriever Evaluation** | Hybrid RRF vs. dense vs. BM25 benchmark, bucketed and unbucketed | [docs/retriever_evaluation_report.md](./docs/retriever_evaluation_report.md) |
| 🧪 **Synthetic Data & Evals** | What test data the eval harness uses and how | [docs/synthetic_data_and_eval_design.md](./docs/synthetic_data_and_eval_design.md) |

---

## 🚀 Quick Start

### Prerequisites
* **Python 3.11+** (virtual environment managed by `uv`)
* **Node.js 18+** (for frontend UI)
* **Stockfish Engine** (macOS: `brew install stockfish` · Linux: `sudo apt-get install stockfish`)
* **API Keys:** `GEMINI_API_KEY`, `OPENAI_API_KEY` (fallback), `TAVILY_API_KEY` (optional, target scaling)

### 1. Installation & Environment Setup
Clone the repository and prepare the configurations:
```bash
git clone https://github.com/rakeshnetdev/AIEC01_CERT_CHLG_GRANDMATE.git
cd AIEC01_CERT_CHLG_GRANDMATE

# Create local environment config
cp backend/.env.example backend/.env
# Edit backend/.env and populate: GEMINI_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY (optional), STOCKFISH_PATH
```

### 2. Run Backend (FastAPI)
```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e .
uv run uvicorn app:app --reload --port 8000
# → API local server running at: http://localhost:8000
```

### 3. Run Frontend (React + Vite)
```bash
cd ../frontend
npm install
echo "VITE_BACKEND_URL=http://localhost:8000" > .env
npm run dev
# → UI development server running at: http://localhost:5173
```

### 4. Interactive LangGraph Studio
```bash
cd ../backend
uv run langgraph dev --no-browser
# → API local server: http://127.0.0.1:2024
# → Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

---

## 🧩 Architecture Summary

This system follows a **5-layer agentic architecture**:

| Layer | Purpose | Key Modules |
| :--- | :--- | :--- |
| **1. Configuration** | Handles settings, API gateways, and environment overrides. | `backend/config/settings.py` |
| **2. Storage** | Vector documents plus an engine/HTTP results cache. Conversation memory is in-process (LangGraph checkpointer), not in this database yet — see caveat below. | `backend/coach.db`, `backend/data/corpus/` |
| **3. Analytical Tools** | Computes engine analytics and parses position legalities. | Stockfish, `python-chess` |
| **4. Retrieval (RAG)** | Fetches context using dense vectors + sparse BM25 fused via RRF, filtered per corpus bucket (`rules` / `strategies`). | `backend/src/coach/rag/` |
| **5. Orchestration** | Runs the multi-agent graph (router → strategy/rules specialists → synthesizer) and the Grounding Guard loop. | `backend/src/coach/agent/graph.py` |

**Multi-agent graph.** A **router** classifies intent and delegates; the **strategy** and **rules**
specialists each answer from their own corpus bucket; a **synthesizer** fuses their findings into the
single answer the user reads; the **grounding guard** re-checks every move named and loops back with a
critique if anything is unverified. The router is deliberately cheap — it decides deterministically
wherever the state already implies the next hop, and calls the LLM only for genuine intent
classification: **0 LLM calls on `/review`, 1 on `/chat`** (before/after diagrams and the full
end-to-end request sequence: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) §4/§4a).

> **Memory caveat.** "Memory" today means conversation-scoped state (a LangGraph checkpointer) that
> lets a review and its follow-up chat share context within one session — it does not survive a
> server restart, and a new session has no link to a user's previous ones. A durable, cross-session
> learner profile is the intended design and a planned next step, not something shipped today. See
> [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) §6 and [docs/Deliverables.md](./docs/Deliverables.md) §8.5.

---

## 📂 Repository Structure

The project is structured as a monorepo split into decoupled frontend and backend service contexts:

```
├── backend/                  # FastAPI service (all business logic, engine calls, & vector db storage)
│   ├── app.py                # REST API endpoints (/review, /chat, /health)
│   ├── pyproject.toml        # Backend dependencies & build configurations
│   ├── config/               # Settings & system environment declarations
│   ├── data/corpus/          # Dual-corpus RAG library: rules/ (FIDE Laws PDF) + strategies/ (openings, tactics)
│   └── src/coach/            # Core logical packages
│       ├── agent/            # LangGraph multi-agent workflow (router, specialists, synthesizer) & prompts
│       ├── analysis/         # Stockfish engine evaluation and NAG mistake classification
│       ├── rag/              # ChromaDB vector collection and bucketed BM25 RRF retriever
│       └── schemas/          # Pydantic models & request-response schemas
│
├── frontend/                 # React SPA UI (Vite + TS calling backend endpoint via VITE_BACKEND_URL)
│   ├── src/                  # App components, styled hooks, and API client
│   └── package.json          # Node dependencies & scripts
│
├── docs/                     # Final root-level deliverables, system architecture, & project plans
│   ├── Deliverables.md       # Full project deliverables & self-assessment evidence
│   ├── ARCHITECTURE.md       # High-level component & infrastructure designs
│   ├── PLAN.md               # Chronological project milestones
│   ├── retriever_evaluation_report.md      # Hybrid RRF vs. dense vs. BM25 benchmark
│   ├── synthetic_data_and_eval_design.md   # What eval data exists & how it's used
│   └── diagrams/              # Every mermaid diagram, as standalone files
│
└── final_docs/               # Submodule (own git history) — per-phase learning log, metrics vs.
                               # rubric, grading-rubric.md, and the graded write-up
```

---

## ⚙️ Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **LLM Gateway** | LiteLLM → Gemini 1.5 Flash | Narrates verified chess analytics (GPT-4o fallback) |
| **Orchestration** | LangGraph 0.2+ | Multi-agent router → specialist → synthesizer team; manages multi-turn memory & validation retry loops |
| **Conversation Memory** | LangGraph `MemorySaver` + python-chess | In-process, session-scoped checkpointing (not yet durable — see caveat above) & board move legality validation |
| **Vector DB** | ChromaDB + BM25 | Hybrid RRF RAG over a dual-corpus bucketed index (`rules` vs. `strategies`) |
| **Frontend UI** | React + Vite + TS | High-fidelity dark mode analysis dashboard |
| **Evals** | pytest + Ragas | Systematic metrics-driven blunder and RAG test harness |
| **Observability** | LangSmith | Live graph trace monitoring and debugging |

---

## 🧪 Evaluation & Benchmarks

Run the test suite to execute evaluations for blunder classification, move legality, and RAG faithfulness:
```bash
cd backend
uv run python evals/generate_synthetic.py   # Generate labeled dataset FENs
uv run pytest tests/                        # Run unit, integration, and guardrail tests
```

### Evaluation Targets vs. Measured

Last measured from `evals/report.py` against a rebuilt, independent-oracle harness (results on disk in `evals/report.json`; overview in [docs/synthetic_data_and_eval_design.md](./docs/synthetic_data_and_eval_design.md)).

| Metric | Target | Measured | Status |
| :--- | :--- | :--- | :--- |
| Detection F1 (Blunders) | `≥ 0.90` | **0.9586** | ✅ Real — scored against an independent depth-24 Stockfish oracle (n=151) |
| Severity Accuracy | `≥ 0.85` | **0.8940** | ✅ Real (n=151) |
| Illegal / Hallucinated Move Rate | `0%` | **0.0000%** | ✅ Real (n=2 moves checked) |
| RAGAS Faithfulness | `≥ 0.85` | **0.75** | ⚠️ Below target (n=2 — thin sample, see caveat) |
| LLM-Judge Coaching Quality | `≥ 4.0 / 5` | **4.00 / 5** | ✅ Real (n=3) |

> **These numbers replace an earlier scorecard that looked identical (F1/severity `1.0`, faithfulness `1.0`) but measured nothing** — the dataset's ground truth was produced by the same function the harness then graded, and faithfulness defaulted to a passing score whenever no context was retrieved. The eval suite was rebuilt around an independent oracle; see the falsification test below for proof it can now actually fail.

* **Detection F1 and Severity Accuracy are now measured against an independent oracle, not the classifier under test.** `evals/generate_synthetic.py` no longer imports `calculate_cpl_and_label`; ground truth comes from Stockfish at **depth 24** plus a reference CPL/severity rule implemented from the spec. `evals/report.py` re-analyses all **151** positions with the *production* engine at depth 16 and production classifier, and scores the result against the oracle's labels. The dataset covers all four severity classes, both colours (56 black-to-move rows — the old harness silently dropped every one), and six edge cases (promotion, castling, en passant, forced mate, stalemate trap, SAN disambiguation).

* **Proof the metric can now fail:** deliberately corrupting the severity thresholds (`INACCURACY_CP=10000 MISTAKE_CP=20000 BLUNDER_CP=30000`, so nothing can be classified a mistake) collapses Detection F1 from `0.9529` to **`0.1875`** and Severity Accuracy from `0.8940` to **`0.4238`**. The old harness reported `1.0` under any mutation, because it compared a deterministic function to itself.

* **Known caveat — engine non-determinism.** Three runs of the same dataset at the same depth have now produced different labels each time (F1 `0.9467` / `0.9529` / `0.9586`; severity `0.9073` / `0.8940` / `0.8940`). This is a real violation of the "same game + depth ⇒ same labels" rule, most likely Stockfish threading, and was invisible under the old circular metric because a function compared to itself is always perfectly reproducible. Read detection figures with a **±0.02 band** (widened from an earlier ±0.01) until this is pinned (candidate fix: `Threads=1`).

* **RAGAS Faithfulness `0.75` is a genuine measurement, now below its own `≥0.85` target — the earlier `1.0` and `0.30` were both harness artifacts.** The eval `Game` is rebuilt from `fen_before` via `[SetUp]`/`[FEN]` PGN headers (so black-to-move positions parse and mid-game context is retrieved for the right board), and the judge is given the coach's **engine facts alongside the RAG context** — the old prompt penalised the coach for correctly narrating Stockfish-derived facts that by definition aren't in the corpus. At n=2 this could be sampling noise rather than a confirmed regression; every run prints an explicit not-measured accounting (`judge_failures`, `pipeline_failures`, `rows_without_rag_context`) instead of silently defaulting to a pass.

* **Illegal / Hallucinated Move Rate and Coaching Quality are now measured without silent defaults.** A failed judge call reports `null` ("not measured"), never a fabricated `4`.

**Retriever comparison** (`evals/compare_retrievers.py`; full report in [docs/retriever_evaluation_report.md](./docs/retriever_evaluation_report.md)) — rewritten to score all three strategies through the production `retrieve_context(..., bucket=)` against **135 queries derived from the corpus itself**, including LLM-paraphrased queries that reword rather than quote the source text:

| Retriever | Hit Rate @3 | MRR | Avg Latency |
| :--- | :--- | :--- | :--- |
| Dense Vector | 87.1% | 0.795 | 527ms |
| BM25 Lexical | 80.3% | 0.755 | 178ms |
| **Hybrid RRF** | 85.6% | **0.817** (best) | 344ms |

**Hybrid RRF has the best ranking quality, confirming Golden Rule 9** — a reversal from an earlier reading that had it losing to plain BM25. That earlier result came from a query set of exact lexical names and verbatim corpus extracts, which BM25 matches by pure word overlap; only genuinely reworded queries settle the comparison honestly. Bucket filtering independently improves every retriever (Hybrid MRR rises from `0.710` unbucketed to `0.817` bucketed).

**Known gaps / follow-ups:**
* **No relevance floor.** All three retrievers return `k` results even for out-of-corpus queries (tested against Go, football, backgammon) — 3/3 false positives each. Retrieval never abstains.
* Router intent/fast-path, guardrail refusals, and memory persistence have no eval coverage yet.
* Raise the judged-layer sample size above the current `--sample 3` default; cheap to do, costs money to run — would also confirm whether the sub-target faithfulness score (`0.75`) holds up or was n=2 noise.
