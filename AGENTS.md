# Freya "Build the Builder" — agent rules

Read by both Claude Code (via CLAUDE.md) and Codex (AGENTS.md). Keep this file the single source of truth.

## What we are building
A **builder**: `python3 builder/build.py <brief.md> <openapi.json>` reads a bank brief and creates/updates a
**phone agent** (a Freya workflow: steps, prompts, tools, conditional routes, code nodes) via `freya.py`.
Only the phone agent is scored. The builder must run alone: one command, no manual edits afterwards.

## Hard rules (breaking these disqualifies us)
1. **Never hardcode brief content.** No rule, holiday date, outcome name, queue name, threshold, or phrase
   from any brief may appear in builder code or prompts. Everything comes from parsing the brief + openapi
   file at runtime. Treat brief-a / brief-b as test inputs only — the hidden briefs will differ
   (other identity questions, limits, outcome table, calendar, tool field values; the 7 tool names stay).
2. Hidden briefs may be **raw material** (mail, policy extract, memo that overrides it, code list).
   The parser must handle that, including later documents amending earlier ones.
3. Do not change the phone-agent model set in `freya.py`.
4. The phone agent may call **only** the kit's tool API.
5. Workflow limit per workspace (200): **update in place**, never create one per run. Each developer uses their own workflow name
   (`dev-<name>`); the final build uses `submission-<brief>`.
6. Never commit keys. Secrets live in `.env` (gitignored). Strip keys from traces.
7. Builder run time ≤ 30 min per brief, including self-tests.

## Design principles
- Deterministic logic (business days, holidays, deadlines per days-late band, minimum amounts, retry counts)
  goes into **code nodes**, not into the model's head. The `now` variable drives all date rules.
- Identity check before any debt disclosure; nothing to third parties; never say "recorded" before a tool
  call succeeds; retry failed tool calls once without duplicating records.
- The builder should: parse brief → structured spec (JSON) → generate workflow → run practice cases →
  fix → re-deploy, within the time budget.

## Trace (required for submission)
Every builder run logs: start/end time, every model call (model + one-line purpose), what was created on
Freya (workflow id, agent id, #steps, #tools), and every self-test with its result. Write to stdout;
we `tee` it to `traces/<brief>.log`.

## Testing
- `python3 tools/run_cases.py <agent_id> --brief A|B [--reps 3]`
- **Only one simulation at a time per workspace** — announce in chat before running; don't run in parallel.
- Trust a fix only after `--reps 3`.

## Workflow for us (two people)
- `main` is always runnable. Work on branches `feat/<thing>`, small PRs, rebase often.
- Before editing a shared module, check the other person isn't mid-change on it.
