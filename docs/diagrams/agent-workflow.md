# Agent workflow (control flow)

Referenced from [`ARCHITECTURE.md` §4](../ARCHITECTURE.md#4-agent-workflow-control-flow) and
[`Deliverables.md` §2.4](../Deliverables.md#24-stateful-agent-workflow).

```mermaid
flowchart TD
    U["User input: pasted PGN / question"] --> FETCH[fetch_and_analyse]
    FETCH --> ROUTE{Router Agent}

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
