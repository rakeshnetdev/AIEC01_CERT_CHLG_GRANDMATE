# Agent workflow (control flow)

Referenced from [`ARCHITECTURE.md` §4](../ARCHITECTURE.md#4-agent-workflow-control-flow) and
[`Deliverables.md` §2.4](../Deliverables.md#24-stateful-agent-workflow).

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
