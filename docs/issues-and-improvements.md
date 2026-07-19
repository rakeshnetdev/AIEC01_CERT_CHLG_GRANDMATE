# Open Issues and Planned Improvements

A single place to track what is known to be incomplete or unreliable, and what we plan to do about
it. Anything listed here is a deliberate, recorded gap — not an oversight.

The design itself is described in [ARCHITECTURE.md](./ARCHITECTURE.md); results and self-assessment
in [Deliverables.md](./Deliverables.md).

This document covers **things that are wrong or unmeasured** — defects, misleading behaviour, and
gaps in how we evaluate. New capabilities we would like to build are a separate topic, kept in
[Deliverables.md](./Deliverables.md) §7 and §8.

**Status key:** 🔴 affects correctness or a stated claim · 🟡 works, but wastes effort or misleads ·
🟢 improvement, nothing is broken

---

## 1. Design

### 1.1 The retriever setting no longer does anything 🟡

The API accepts a `retriever_type` field, and the Developer Insights panel displays it, but it no
longer changes how documents are retrieved. The specialists call the retriever without it, so the
global default is always used.

This never affected the coaching text — the setting only ever shaped a pre-fetch step whose output
was never sent to the model — but the interface still implies a choice that has no effect.

**Options:** pass the setting through to the specialists, or remove it from the API and the panel.
This is a product decision, not just a code fix.

### 1.2 The game is re-analysed on every chat message 🟡

Every chat turn re-runs the full engine analysis, including for messages answered from a template
such as "thanks". The result is discarded when it is identical to what is already held in session
state.

**Fix:** skip the analysis step when the session already holds an analysed game. This is the single
largest remaining latency saving.

### 1.3 The grounding retry counter is never reset 🔴

The counter that limits grounding retries to three attempts persists for the lifetime of a
conversation instead of resetting each turn. Today the visible effect is cosmetic — a later turn's
first attempt is labelled "Attempt 2".

The real risk is that once a conversation accumulates three rejections, the guard stops retrying for
every subsequent turn in that thread, silently weakening a safety check rather than failing loudly.

**Fix:** reset the counter at the start of each turn.

### 1.4 The configured primary model does not exist 🔴

Every language-model request currently fails once before succeeding. The configured primary model is
rejected by the provider with a "not found" error, and the request then falls back to the secondary
model, which answers normally.

The output is therefore correct, but every call pays a failed round trip first, and the logs fill
with errors that are easy to mistake for real failures. A recent evaluation run produced over fifty
such errors while still returning valid results.

Two contributing problems:

- The model name in the environment does not match the one recorded in the project configuration
  file, because a shell environment variable silently overrides the file.
- The documented primary model is itself reported as unavailable from the provider, so simply
  reverting to it would not help.

**Fix:** decide which model is actually the primary, set it in one place, and remove the override.
Then confirm with a single request that it answers without falling back.

### 1.5 Memory does not survive between visits 🟢

Memory today means conversation state held for the duration of a session. A returning user starts
from scratch: recurring weaknesses and previously covered ground are not carried across visits.

**Fix:** a durable learner profile, written after each review and read back at the start of the
next. Already scoped as future work.

---

## 2. Evaluation

### 2.1 The coaching-quality score mostly measures the wrong thing 🔴

| Metric | Result | Target |
|---|---|---|
| Coaching quality | 3.17 / 5 (n = 12) | ≥ 4.0 |

This is the one headline metric below target. Investigating it showed the score is mostly an
artefact of how the evaluation is set up, not a fair measure of the coaching.

**The evaluation feeds the coach a single move, not a game.** Each test case is built as a
one-move game from a starting position. The coach is designed to review a whole game — summarise
how it went, point out what the player did well, identify mistakes, and draw out a theme. Given one
move it can do almost none of that, and says so in its own output: *"the game was incomplete"* and
*"there are no specific strong moves to highlight"*. An entire section of the response is
structurally empty.

**The same judge scores a real game higher.** Using the identical prompt:

| What the judge was given | Score |
|---|---|
| A one-move fragment (what the evaluation sends) | 3 / 5 |
| A real 23-move game (what a user actually sends) | 4 / 5 |

On the real game the response named three specific good moves, one mistake with the better
alternative and the reason, and two improvement themes drawn from the game. That is the product
working as intended, and it meets the target.

**Two smaller problems compound it.**

- *The judge has no scoring guide.* It is asked for a score from 1 to 5 with no description of what
  each number means. Asked to explain itself, it produced generic suggestions rather than specific
  faults. Scores cluster tightly on 3, which is what an unanchored judge tends to return.
- *Some of what the judge rewards, the product deliberately refuses to do.* Asked what would earn a
  5, the judge suggested praising creative attempts and describing how unconventional moves can
  work out. Both require speculating beyond what the engine verified, which the grounding rules
  forbid. The coach is being marked down for following its own most important rule.

**Fix, in order:**

1. Evaluate on real multi-move games, so the coach is asked to do the job it was built for.
   Single-move cases can stay for mistake detection, which they suit, but should not feed the
   coaching score.
2. Give the judge an explicit scoring guide describing what each score means.
3. Align the judge's criteria with the grounding rules, so it stops rewarding speculation.

Until step 1 is done, **treat 3.17 as a measurement artefact rather than a product result.** The
honest summary is that coaching quality on realistic input is untested at scale, not that it is
poor.

### 2.2 The judged sample is too small to draw conclusions from 🔴

The judged part of the evaluation defaults to three examples. At that size, faithfulness measured
anywhere between **0.75 and 1.00 across separate runs of essentially unchanged code** — a spread
wider than most differences we would want to detect.

Re-running at twelve examples resolved both judged metrics, and changed the conclusions:

| Metric | At n = 3 | At n = 12 | What changed |
|---|---|---|---|
| Faithfulness | 0.75 – 1.00 | 0.8667 | The 1.00 was luck; the true value is a narrow pass |
| Coaching quality | 3.33 – 4.00 | 3.17 | Was ambiguous, now a confirmed miss |

**Status:** partly addressed. Twelve is enough to separate these two metrics from noise, but the
default is still three.

**Fix:** raise the default, or require an explicit sample size for any run whose numbers will be
quoted.

### 2.3 The engine does not produce identical results run to run 🔴

Repeated runs over the same positions at the same search depth have produced different move labels
each time. This breaks the assumption that the same game at the same depth yields the same
analysis, which the detection metrics rely on.

Detection figures should therefore be read with a tolerance band of roughly **±0.02**, not as exact
values.

**Likely cause:** engine threading. **Candidate fix:** pin the engine to a single thread and
re-measure.

### 2.4 Parts of the system have no evaluation coverage 🟡

Nothing currently measures:

- how the router dispatches — whether it picks the right specialist, and how often it needs both
- whether guardrails refuse the right requests, and only those
- whether conversation memory behaves correctly across turns

These are covered by unit tests but not by any quality measurement, so regressions would show up
only as user-visible symptoms.

---

## 3. Ranked next steps

| # | Change | Why it is ranked here |
|---|---|---|
| 1 | Reset the grounding retry counter each turn | Small fix; removes a silent weakening of a safety check |
| 2 | Raise the *default* judged sample size | Done ad hoc at n = 12; the default is still 3, so the next run silently reverts to untrustworthy numbers |
| 3 | Pin the engine to one thread and re-measure | Restores reproducibility, which the detection metrics assume |
| 4 | Skip re-analysis on chat turns | Largest remaining latency win, low risk |
| 5 | Evaluate coaching on real games, not one-move fragments | The current 3.17 mostly measures an input the product never receives |
| 6 | Decide the fate of the retriever setting | Product decision; currently misleading in the UI |
| 7 | Add a durable learner profile | Largest new capability, but depends on nothing above |

Ahead of all of these: **fix the primary model configuration (1.4)**. It is a small change, and
until it is done every run wastes a failed request and every log is noisy enough to hide real
faults.
