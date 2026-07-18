# CLAUDE.md — Claude Code behavior for Grandmate

> Claude Code reads this at session start. Shared rules for all coding agents (Antigravity, Cursor,
> Claude Code) live in **`AGENTS.md`** — read that first. This file only adds behavior specific to
> working in this repo *with Claude Code*. This project was originally built with Google's
> Antigravity (see `final_docs/GEMINI.md` for its Antigravity-specific rules); treat `AGENTS.md` as
> the tool-agnostic source of truth both files defer to.

## Models — two separate things (do not conflate)
**Development model (this coding agent):** whatever model Claude Code is running as. It only
writes/edits code — it never runs inside the deployed app.

**Application runtime model (what the deployed coach calls):** **Gemini 1.5 Flash** primary
(`LLM_MODEL=gemini/gemini-1.5-flash`), **OpenAI GPT-4o** fallback, via the LiteLLM gateway. Do **not**
swap these to a Claude model in `.env`, `config/settings.py`, or `llm/gateway.py` — that's a product
decision, not a dev-tooling one.

## Planning & execution
- Treat `docs/PLAN.md`'s phases as the unit of work: one phase at a time, plan first, wait for
  approval before editing files for non-trivial phase work (use Plan Mode).
- Use `TaskCreate`/`TaskUpdate` to track multi-step work within a phase or a larger fix.
- **"Done" = tests pass.** Run `uv run pytest` from `backend/` and confirm green before calling a
  phase or fix complete — don't rely on the diff "looking right."
- Stop at phase boundaries and show the diff before committing, per `AGENTS.md`'s workflow protocol.

## Tooling notes
- For UI/frontend changes, use the `run` skill (or `npm run dev` + a real browser check) to verify
  the feature actually works before reporting it done — typechecking isn't enough.
- Use `/code-review` (or the `verify` skill) on nontrivial diffs before considering them ready to
  commit.
- Secrets come from `backend/.env` only (schema in `backend/.env.example`); never commit keys.
- `final_docs/` is a **git submodule** (branch `refactoring`) holding the per-phase learning log,
  metrics vs. rubric, and the graded write-up, plus Antigravity's `GEMINI.md`. It has its own commit
  history — don't casually rewrite its content; follow the phase-reporting process already
  established there when a phase's work needs to be recorded in it.

## Scope & safety
- If a needed change isn't in `docs/PLAN.md`, stop and ask before doing it.
- The Golden Rules in `AGENTS.md` are non-negotiable (the LLM never analyzes a chess position, every
  named move is ground-checked against the engine PV, typed contracts at every seam, etc.).
- Never push to `main` directly — feature branch + PR, per `AGENTS.md`.

## Where the detail lives
- Cross-tool rules & conventions → `AGENTS.md`
- Phase-by-phase build spec → `docs/PLAN.md`
- Architecture & diagrams → `docs/ARCHITECTURE.md`
- Deliverables / self-assessment → `docs/Deliverables.md`
- Antigravity-specific rules (only relevant inside the Antigravity IDE) → `final_docs/GEMINI.md`
