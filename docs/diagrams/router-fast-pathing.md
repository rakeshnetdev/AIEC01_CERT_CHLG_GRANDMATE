# Router fast-pathing — before/after

Referenced from [`ARCHITECTURE.md` §4](../ARCHITECTURE.md#4-agent-workflow-control-flow) and
[`Deliverables.md` §6.3](../Deliverables.md#63-iterative-improvements--engineering-optimizations).

## Before: Router always calls the LLM

Every visit to `router_agent` — whether it's the first pass on an initial review, or a
loop-back after a specialist finishes — invokes the classification LLM call, even when
the next step is already deterministic given current state.

```mermaid
stateDiagram-v2
    [*] --> FetchAndAnalyse
    FetchAndAnalyse --> RetrieveRagContext
    RetrieveRagContext --> RouterAgent

    state RouterAgent {
        [*] --> LLMClassify: always calls chat()
        LLMClassify --> [*]
    }

    RouterAgent --> StrategyNode: LLM picks "strategy"
    RouterAgent --> RulesNode: LLM picks "rules"
    RouterAgent --> SynthesizerNode: both findings already present

    StrategyNode --> RouterAgent: loop back (LLM call again)
    RulesNode --> RouterAgent: loop back (LLM call again)

    SynthesizerNode --> GroundingGuard
    GroundingGuard --> [*]: approved
    GroundingGuard --> SynthesizerNode: rejected, retry_count < 3

    note right of RouterAgent
        Every entry costs 1 LLM call,
        regardless of whether the next
        hop is already implied by state
        (e.g. only one specialist has
        run so far).
    end note
```

## After: Router short-circuits on known state

`router_agent_node` now inspects `strategy_findings` / `rules_findings` /
whether any `HumanMessage` exists *before* calling the LLM. Three of its four branches
return deterministically with zero LLM cost; only the "user asked something new, no
findings yet" branch reaches the `chat()` call.

```mermaid
stateDiagram-v2
    [*] --> FetchAndAnalyse
    FetchAndAnalyse --> RetrieveRagContext
    RetrieveRagContext --> RouterAgent

    state RouterAgent {
        [*] --> CheckState
        CheckState --> BothGathered: strategy_findings and rules_findings set
        CheckState --> OnlyStrategyDone: strategy set, rules unset
        CheckState --> OnlyRulesDone: rules set, strategy unset
        CheckState --> NoHumanMessage: no HumanMessage in state
        CheckState --> NeedsClassification: HumanMessage present, no findings yet

        BothGathered --> [*]: skip (deterministic)
        OnlyStrategyDone --> [*]: skip, fast-route to rules
        OnlyRulesDone --> [*]: skip, fast-route to strategy
        NoHumanMessage --> [*]: skip, default to strategy
        NeedsClassification --> [*]: calls chat() (only LLM cost)
    }

    RouterAgent --> StrategyNode: NoHumanMessage / OnlyRulesDone / classified "strategy"
    RouterAgent --> RulesNode: OnlyStrategyDone / classified "rules"
    RouterAgent --> SynthesizerNode: BothGathered

    StrategyNode --> RouterAgent: loop back (usually free)
    RulesNode --> RouterAgent: loop back (usually free)

    SynthesizerNode --> GroundingGuard
    GroundingGuard --> [*]: approved
    GroundingGuard --> SynthesizerNode: rejected, retry_count < 3

    note right of RouterAgent
        Only "NeedsClassification"
        (a genuine user follow-up with
        no specialist findings gathered
        yet) costs an LLM call. All other
        branches are free — the outcome
        is already implied by state.
    end note
```

## Net effect

- **Initial review** (`/review`, no `HumanMessage`): both specialists (strategy + rules) now run for
  full coverage, yet the router itself never costs an LLM call — the decisions that used to require
  one classification call are now made for free from state.
- **Chat follow-up** (`/chat`): the first router visit still needs the LLM (real intent
  classification), but the loop-back after the first specialist completes is now a free,
  deterministic hop to the other specialist instead of a second classification call.
- Total LLM calls per turn drop by 1 in both flows, with no loss of specialist coverage.
