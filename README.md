# ♟️ Grandmate: AI-Powered Chess Analysis & Personalized Helper

> An intelligent, engine-grounded chess analysis agent and conversational coaching helper powered by **LangGraph** and **Agentic RAG**.
> 
> *Naming Note: The project name **Grandmate** (originally conceived as **GameMate**) is a play on two core chess terms—**Grandmaster** (expertise) and **Checkmate** (the game goal)—coupled with the colloquial sense of a friendly companion (**mate**).*

---

## 📚 Documentation Overview

| Document | Purpose | Location |
| :--- | :--- | :--- |
| 📋 **Full Deliverables** | Core challenge deliverables and self-assessment checklists | [docs/Deliverables.md](./docs/Deliverables.md) |
| 🏗️ **System Architecture** | Subsystem flowcharts and deployment topologies | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) |
| 🗺️ **Implementation Plan** | Chronological development phases and engineering logs | [docs/PLAN.md](./docs/PLAN.md) |

---

## 🚀 Quick Start

### Prerequisites
* **Python 3.11+** (virtual environment managed by `uv`)
* **Node.js 18+** (for frontend UI)
* **Stockfish Engine** (macOS: `brew install stockfish` · Linux: `sudo apt-get install stockfish`)
* **API Keys:** `GEMINI_API_KEY`, `OPENAI_API_KEY` (fallback), `TAVILY_API_KEY`

### 1. Installation & Environment Setup
Clone the repository and prepare the configurations:
```bash
git clone https://github.com/rakeshnetdev/AIEC01_CERT_CHLG_GRANDMATE.git
cd AIEC01_CERT_CHLG_GRANDMATE

# Create local environment config
cp backend/.env.example backend/.env
# Edit backend/.env and populate: GEMINI_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY, STOCKFISH_PATH
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
| **2. Storage** | Manages vector documents, learner memory, and session state. | `backend/coach.db`, `backend/data/corpus/` |
| **3. Analytical Tools** | Computes engine analytics and parses position legalities. | Stockfish, `python-chess` |
| **4. Retrieval (RAG)** | Fetches tactical context using dense vectors + sparse BM25. | `backend/src/coach/rag/` |
| **5. Orchestration** | Manages LangGraph state transitions and Grounding Guard loops. | `backend/src/coach/agent/graph.py` |

---

## 📂 Repository Structure

The project is structured as a monorepo split into decoupled frontend and backend service contexts:

```
├── backend/                  # FastAPI service (all business logic, engine calls, & vector db storage)
│   ├── app.py                # REST API endpoints (/review, /chat, /health)
│   ├── pyproject.toml        # Backend dependencies & build configurations
│   ├── config/               # Settings & system environment declarations
│   └── src/coach/            # Core logical packages
│       ├── agent/            # LangGraph state machine workflow & node orchestration
│       ├── analysis/         # Stockfish engine evaluation and NAG mistake classification
│       ├── rag/              # ChromaDB vector collection and BM25 RRF retriever
│       └── schemas/          # Pydantic models & request-response schemas
│
├── frontend/                 # React SPA UI (Vite + TS calling backend endpoint via VITE_BACKEND_URL)
│   ├── src/                  # App components, styled hooks, and API client
│   └── package.json          # Node dependencies & scripts
│
├── docs/                     # Final root-level deliverables, system architecture, & project plans
│   ├── Deliverables.md       # Full project deliverables & self-assessment evidence
│   ├── ARCHITECTURE.md       # High-level component & infrastructure designs
│   └── PLAN.md               # Chronological project milestones
│
└── final_docs/               # Submodule directory maintaining official documentation sources
```

---

## ⚙️ Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **LLM Gateway** | LiteLLM → Gemini 1.5 Flash | Narrates verified chess analytics (GPT-4o fallback) |
| **Orchestration** | LangGraph 0.2+ | Manages multi-turn memory & validation retry loops |
| **Local Memory** | SQLite + python-chess | Checkpoints user profiles & validates board move legality |
| **Vector DB** | ChromaDB + BM25 | Hybrid RRF RAG for tactical motif articles |
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

### Evaluation Targets vs. Achieved
* **Detection F1 (Blunders):** Target `≥ 0.90` | **Achieved: 1.0 (100%)**
* **Severity Accuracy:** Target `≥ 0.85` | **Achieved: 1.0 (100%)**
* **Hallucinated Move Rate:** Target `0%` | **Achieved: 0.0%**
* **RAGAS Faithfulness:** Target `≥ 0.85` | **Achieved: 1.0 (100%)**
* **LLM-Judge Helping Quality:** Target `≥ 4/5` | **Achieved: 4.0 / 5**
