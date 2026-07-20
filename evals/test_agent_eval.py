"""Agent-level evaluation with Ragas, following Session 6's approach.

`report.py` measures the *output* of a review (move detection, faithfulness of the
narrative). Nothing measured the *agent behaviour* around it -- whether the router
dispatches to the right specialist, whether guardrails hold, whether a turn actually
achieves what it set out to do. That gap is issue 2.4 in the tracker; this closes it.

Two deliberate departures from the notebook, both because Grandmate is not a ReAct agent:

1. Grandmate's LLM never emits tool calls. Stockfish and retrieval are invoked
   deterministically by graph nodes. The decision the agent actually makes is the
   router's dispatch, so each dispatch is represented as a Ragas ToolCall and scored
   with ToolCallAccuracy. This measures the real decision, not a synthetic one.
2. Off-topic requests are refused by `validate_request()` before the graph runs, so a
   refusal produces no graph trace. Topic adherence is therefore scored over the
   API-level exchange rather than an internal message list.

Run:  cd backend && uv run python ../evals/test_agent_eval.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path

# ragas 0.4.3 imports langchain_community.chat_models.vertexai, removed in
# langchain-community 0.4.2. The symbol is only used in an isinstance list for
# multi-completion support, so a stub is inert -- it simply never matches.
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    class ChatVertexAI:  # noqa: D401 - placeholder, never instantiated
        pass
    _stub.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

import instructor
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.messages import AIMessage as RAIMessage, HumanMessage as RHumanMessage, ToolCall
from ragas.metrics.collections import (
    AgentGoalAccuracyWithReference,
    ToolCallAccuracy,
    TopicAdherence,
)

from langchain_core.messages import HumanMessage
from coach.agent.graph import compile_coach_graph
from coach.guardrails import validate_request
from config.settings import get_settings

JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o")
GOAL_RUNS = int(os.environ.get("EVAL_GOAL_RUNS", "5"))


def build_judge():
    """Synchronous judge client, bridged at the Ragas coroutine boundary (per Session 6)."""
    judge = llm_factory(
        JUDGE_MODEL,
        provider="openai",
        client=OpenAI(api_key=get_settings().openai_api_key),
        mode=instructor.Mode.TOOLS,
        max_tokens=1024,
    )
    judge.model_args = {"max_tokens": 1024, "max_retries": 3}

    # Ragas metrics call agenerate(); this client is synchronous. Bridge only at the
    # coroutine boundary so every actual request stays sync (Session 6 does the same).
    async def agenerate_from_sync(prompt, response_model):
        return await asyncio.to_thread(judge.generate, prompt=prompt, response_model=response_model)

    judge.agenerate = agenerate_from_sync
    return judge


def run_async(coro_fn, *a):
    return asyncio.run(coro_fn(*a))


# ---------------------------------------------------------------- fixtures
GAME_PGN = (ROOT / "backend" / "data" / "pgn" / "Carlsen.pgn").read_text().split("\n\n[Event")[0]


def seeded_graph(thread: str):
    """A graph with one analysed game already in state, as a chat turn would find it."""
    app = compile_coach_graph()
    cfg = {"configurable": {"thread_id": thread}}
    app.invoke({"pgn": GAME_PGN, "username": "Carlsen", "source": "upload", "messages": [],
                "game": None, "analyses": [], "rag_context": "", "output": ""}, cfg)
    return app, cfg


def ask(app, cfg, question: str):
    """Runs one chat turn, returning (dispatch_targets, reply)."""
    st = app.invoke({"messages": [HumanMessage(content=question)]}, cfg)
    return list(st.get("dispatch_targets") or []), st.get("output", "")


# ------------------------------------------------- 1. router dispatch accuracy
# The router's dispatch is the one decision the agent makes for itself, so it is the
# real analogue of a tool call. Reference = the specialist(s) the question needs.
DISPATCH_CASES = [
    ("Why was that move a blunder?",                         ["strategy"]),
    ("Is castling still legal after the king has moved?",    ["rules"]),
    ("Was castling there legal, and was it a good idea?",    ["strategy", "rules"]),
]


def eval_dispatch():
    print("\n" + "=" * 72)
    print("1. ROUTER DISPATCH ACCURACY  (Ragas ToolCallAccuracy)")
    print("=" * 72)
    rows = []
    for question, expected in DISPATCH_CASES:
        app, cfg = seeded_graph(f"disp-{abs(hash(question))}")
        actual, _ = ask(app, cfg, question)
        trace = [
            RHumanMessage(content=question),
            RAIMessage(content="", tool_calls=[ToolCall(name=t, args={}) for t in actual] or None),
        ]
        ref = [ToolCall(name=t, args={}) for t in expected]

        async def score():
            # strict_order=False: the "both" fan-out is parallel, so order is not meaningful
            return await ToolCallAccuracy(strict_order=False).ascore(
                user_input=trace, reference_tool_calls=ref)
        try:
            v = run_async(score).value
        except Exception as e:
            v = float(sorted(actual) == sorted(expected))  # metric needs >=1 call; fall back
            print(f"   (metric unavailable for this row: {type(e).__name__}; used exact match)")
        rows.append(v)
        mark = "OK " if v == 1.0 else "MISS"
        print(f"  [{mark}] {v:.2f}  expected {expected} -> got {actual or ['<none>']}")
        print(f"          {question}")
    print(f"\n  MEAN dispatch accuracy: {sum(rows)/len(rows):.2f}  (n={len(rows)})")
    return sum(rows) / len(rows)


# ------------------------------------------------------- 2. topic adherence
# Off-topic requests are refused by validate_request() before the graph is invoked,
# so the exchange is scored at the API boundary rather than from a graph trace.
TOPIC_CASES = [
    ("Why was that move a blunder?",                 True),   # in scope
    ("Who won the FIFA world cup?",                  False),  # out of scope
    ("Write me a python script to reverse a string.", False),
]

# Chess questions that must NOT be refused. Each uses ordinary chess vocabulary; a refusal here
# is a false positive in the keyword allowlist, and it silently corrupts topic adherence too,
# because the in-scope turn never produces an answer to score.
GUARDRAIL_FALSE_POSITIVE_CASES = [
    "Why did I lose material in the middlegame?",
    "How should I play this endgame?",
    "Was my pawn structure a problem?",
    "What went wrong in the middlegame?",
]
ALLOWED_TOPICS = [
    "chess game analysis and move quality",
    "chess strategy, tactics and openings",
    "the rules and legality of chess",
]


def eval_guardrail_false_positives():
    """Chess questions the guardrail should let through. Deterministic - no LLM, no cost."""
    print("\n" + "=" * 72)
    print("2a. GUARDRAIL FALSE POSITIVES  (deterministic)")
    print("=" * 72)
    refused = []
    for q in GUARDRAIL_FALSE_POSITIVE_CASES:
        try:
            validate_request(q)
            print(f"  [OK      ] {q}")
        except ValueError:
            refused.append(q)
            print(f"  [REFUSED ] {q}")
    print(f"\n  {len(GUARDRAIL_FALSE_POSITIVE_CASES) - len(refused)}/"
          f"{len(GUARDRAIL_FALSE_POSITIVE_CASES)} legitimate chess questions accepted")
    return len(refused), len(GUARDRAIL_FALSE_POSITIVE_CASES)


def eval_topic_adherence():
    print("\n" + "=" * 72)
    print("2. TOPIC ADHERENCE  (Ragas TopicAdherence, precision)")
    print("=" * 72)
    app, cfg = seeded_graph("topic-thread")
    trace, refused = [], 0
    for question, in_scope in TOPIC_CASES:
        trace.append(RHumanMessage(content=question))
        try:
            validate_request(question)
            _, reply = ask(app, cfg, question)
        except ValueError:
            refused += 1
            reply = "I can only help with chess-related questions. Let's focus on chess!"
        trace.append(RAIMessage(content=reply))
        print(f"  {'in-scope ' if in_scope else 'off-topic'} | "
              f"{'REFUSED' if reply.startswith('I can only') else 'answered'} | {question[:46]}")

    async def score():
        return await TopicAdherence(llm=build_judge(), mode="precision").ascore(
            user_input=trace, reference_topics=ALLOWED_TOPICS)
    v = run_async(score).value
    expected_refusals = sum(1 for _, s in TOPIC_CASES if not s)
    print(f"\n  Topic adherence (precision): {v:.2f}")
    print(f"  Guardrail refusals: {refused}/{expected_refusals} expected")
    return v, refused, expected_refusals


# --------------------------------------------------- 3. agent goal accuracy
def eval_goal_accuracy():
    print("\n" + "=" * 72)
    print("3. AGENT GOAL ACCURACY  (Ragas AgentGoalAccuracyWithReference)")
    print("=" * 72)
    app = compile_coach_graph()
    cfg = {"configurable": {"thread_id": "goal-thread"}}
    st = app.invoke({"pgn": GAME_PGN, "username": "Carlsen", "source": "upload", "messages": [],
                     "game": None, "analyses": [], "rag_context": "", "output": ""}, cfg)
    trace = [
        RHumanMessage(content="Review this game and tell me how I played."),
        RAIMessage(content=st.get("output", "")),
    ]
    # AgentGoalAccuracy infers an end_state from the trace, then does a *binary* same/different
    # comparison against the reference. Two consequences, both verified against the metric's
    # internals rather than assumed:
    #   - the reference must be phrased as an outcome at the same granularity as an inferred
    #     end_state; an instruction-style reference scores 0 even when the goal was plainly met.
    #   - the binary verdict is not stable. The same trace and reference have produced 1.0 and 0.0
    #     on consecutive runs, so a single value is not reportable. Run it several times.
    reference = (
        "The player received a review of their game covering how it went, the moves they played "
        "well, their mistakes with better alternatives, and what to improve."
    )

    async def score():
        return await AgentGoalAccuracyWithReference(llm=build_judge()).ascore(
            user_input=trace, reference=reference)

    runs = [run_async(score).value for _ in range(GOAL_RUNS)]
    v = sum(runs) / len(runs)
    print(f"  runs: {runs}")
    print(f"  Goal accuracy: {v:.2f} over {GOAL_RUNS} runs" + ("   [UNSTABLE - verdict flips on identical input]" if 0 < v < 1 else ""))
    print(f"  (review length {len(st.get('output',''))} chars)")
    return v


if __name__ == "__main__":
    print(f"Judge model: {JUDGE_MODEL}   App model: {get_settings().llm_model}")
    d = eval_dispatch()
    fp, fp_total = eval_guardrail_false_positives()
    t, refused, expected = eval_topic_adherence()
    g = eval_goal_accuracy()
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  Router dispatch accuracy : {d:.2f}   (target 1.00)")
    print(f"  Guardrail false positives: {fp}/{fp_total} chess questions wrongly refused"
          + ("   <-- BUG" if fp else ""))
    print(f"  Topic adherence          : {t:.2f}   (target >= 0.90)")
    print(f"  Guardrail refusals       : {refused}/{expected}")
    print(f"  Agent goal accuracy      : {g:.2f}   (mean of {GOAL_RUNS} runs; metric verdict is binary and unstable)")
