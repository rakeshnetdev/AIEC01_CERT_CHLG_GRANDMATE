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

### 2.1 Coaching quality is below target 🔴

| Metric | Result | Target |
|---|---|---|
| Coaching quality | 3.33 / 5 | ≥ 4.0 |

This is the one headline metric currently failing. It measured the same before the latest round of
work, so it is a standing gap rather than a regression — but it has not yet been investigated, and
the sample is small enough that the score itself is uncertain (see 2.2).

**Next step:** re-measure at a larger sample first. Only then decide whether the gap is real and
what in the coaching prompt is responsible.

### 2.2 The judged sample is too small to draw conclusions from 🔴

The judged part of the evaluation defaults to three examples. Faithfulness has measured anywhere
between **0.75 and 1.00 across separate runs of essentially unchanged code**.

That spread is wider than most differences we would want to detect, so at this sample size the
judged scores cannot support a before/after claim. They are usable as a rough check that nothing is
badly wrong, and not much more.

**Fix:** raise the sample size for any run whose numbers will be quoted, and report a range rather
than a single figure.

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
| 2 | Raise the judged evaluation sample size | Every other quality conclusion depends on trustworthy numbers |
| 3 | Pin the engine to one thread and re-measure | Restores reproducibility, which the detection metrics assume |
| 4 | Skip re-analysis on chat turns | Largest remaining latency win, low risk |
| 5 | Investigate the coaching-quality gap | Only sensible once 2 and 3 make the measurement trustworthy |
| 6 | Decide the fate of the retriever setting | Product decision; currently misleading in the UI |
| 7 | Add a durable learner profile | Largest new capability, but depends on nothing above |

Ahead of all of these: **fix the primary model configuration (1.4)**. It is a small change, and
until it is done every run wastes a failed request and every log is noisy enough to hide real
faults.
