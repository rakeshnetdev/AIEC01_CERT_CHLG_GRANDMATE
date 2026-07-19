# Request lifecycle — end-to-end sequence

Copy of the diagrams inlined in [`ARCHITECTURE.md` §4a](../ARCHITECTURE.md#4a-request-lifecycle-end-to-end-sequence).

Traces a click in the browser through the FastAPI route, the LangGraph
router/specialist/synthesizer team, Stockfish and retrieval, and the LiteLLM gateway, back to the
UI. Both entry points the frontend calls run the same graph, so they are shown as one sequence.
Node and file names match `backend/src/coach/agent/graph.py`.

**Both entry points run the same graph.** `/review` starts a thread and `/chat` continues it; the
difference is what the router finds in state, not a different pipeline. Router LLM cost is **0
calls** on a review (dispatch is implied by state), **1 call** on a real question, and **0** for
pure small talk.

```mermaid
sequenceDiagram
    participant UI as App.tsx [React]
    participant Client as api.ts [Client]
    participant API as app.py [FastAPI]
    participant Graph as graph.py [LangGraph]
    participant Eng as engine.py [Stockfish]
    participant RAG as rag/pipeline.py [Hybrid RRF]
    participant GW as gateway.py [LiteLLM]

    alt POST /review (initial analysis)
        UI->>Client: handleAnalyze() (AnalysisForm onSubmit)
        Client->>API: POST /review {username|pgn, source}
        API->>API: validate_request() (guardrail)
    else POST /chat (follow-up question)
        UI->>Client: handleSendChat() (ChatPanel onSubmit)
        Client->>API: POST /chat {message, session_id}
        API->>API: validate_request() (guardrail, off-topic short-circuits)
        API->>API: replies immediately if no game is loaded in this thread
    end

    API->>Graph: coach_graph.invoke(inputs, config={thread_id})

    Note over Graph: fetch_and_analyse_node
    alt first call for this thread
        Graph->>Eng: analyze_game() -> per-move centipawn loss + severity
    else game already analysed
        Note over Graph: returns immediately, no engine work repeated
    end

    Note over Graph: router_agent_node, entered exactly once
    alt initial review (no messages yet)
        Note over Graph: dispatches to strategy, 0 LLM calls
    else pure small talk
        Note over Graph: canned reply, 0 LLM calls
        Note over Graph: returns without synthesis or grounding
    else a real question
        Graph->>GW: chat() -> strategy, rules, both, or neither
    end

    opt one or both specialists dispatched
        Graph->>RAG: retrieve_context(bucket="strategies" and/or "rules")
        Graph->>GW: specialist chat() -> findings
        Note over Graph: the both case runs the two specialists in parallel
    end

    Graph->>GW: synthesizer_node: chat() -> answer
    Graph->>GW: grounding_guard_node (LLM judge on a review, deterministic on chat)
    opt rejected and retry_count < 3
        Graph->>GW: synthesizer_node: chat() again with the critique
    end

    Graph->>API: returns final_state
    API->>API: is_safe_output() (guardrail)
    alt /review
        API->>Client: CoachReport JSON
        Client->>UI: setReport(data) -> dashboard re-renders
    else /chat
        API->>Client: {reply, developer_insight}
        Client->>UI: appends to the chat feed
    end
```
