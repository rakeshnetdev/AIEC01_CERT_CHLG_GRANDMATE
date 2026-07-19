# Request lifecycle — end-to-end sequence

Copy of the diagrams inlined in [`ARCHITECTURE.md` §4a](../ARCHITECTURE.md#4a-request-lifecycle-end-to-end-sequence).

Traces a click in the browser all the way through the FastAPI route, the LangGraph
router/specialist/synthesizer team, Stockfish/RAG, and the LiteLLM gateway, back to the UI —
for both entry points the frontend calls. Node and file names match the current graph
(`backend/src/coach/agent/graph.py`), not the pre-Phase-9 single-agent version.

## Flow A: `POST /review` (initial game analysis)

Router LLM cost: **0 calls** — every routing decision is implied by state; only the
specialist/synthesis/guard nodes call the gateway.

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
    Note over Graph: router_agent_node (no messages yet, dispatches to strategy, 0 LLM calls)
    Graph->>RAG: strategy_node: retrieve_context(bucket="strategies")
    Graph->>GW: strategy_node: chat() -> strategy findings
    Note over Graph: rules_node does not run on a plain review (no rules question)
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

## Flow B: `POST /chat` (follow-up question)

Router LLM cost: **1 call** — the router is entered once and classifies intent in that single
visit, then dispatches to one specialist, both in parallel, or neither. Pure small talk is matched
deterministically and costs **0 calls**, skipping synthesis and the grounding guard entirely.

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
    API->>API: validate_request() (guardrail, off-topic short-circuits)
    API->>Graph: coach_graph.get_state(config={thread_id})
    alt no game loaded in this thread
        API->>Client: {"reply": "Please load and analyze a game first"} (no graph invoke)
    else game loaded
        API->>Graph: coach_graph.invoke({messages:[HumanMessage]}, config)
        Note over Graph: router_agent_node, entered once (1 LLM call to classify)
        alt pure small talk
            Note over Graph: matched deterministically, canned reply, 0 LLM calls
            Note over Graph: skips synthesis and the grounding guard entirely
        else a real question
            Graph->>GW: router_agent_node: chat() -> strategy, rules, both, or neither
            Graph->>RAG: dispatched specialists: retrieve_context(bucket=...)
            Note over Graph: the both case runs strategy_node and rules_node in parallel
            Graph->>GW: dispatched specialists: chat() -> findings
            Graph->>GW: synthesizer_node: chat() -> fused reply
        end
        Note over Graph: grounding_guard_node forced to deterministic mode (chat follow-up)
        Graph->>API: returns final_state
        API->>API: extract last AIMessage as reply + rebuild DeveloperInsight
        API->>Client: {"reply": ..., "developer_insight": {...}}
    end
    Client->>UI: append reply to conversation
```
