# Handoff: Şevval's Claude Code session, 10 Oct 2026

For Rana's coding agent. What this session did, what it decided and why, and what is still open. PLAN.md stays
the single source of truth for status and rules; this file is the history behind it. **Do not redo anything listed
under "Done": read the result instead.** If something here contradicts PLAN.md, PLAN.md wins; fix this file.

## Done (merged to `main`, PRs #1, #2, #6–#9)

| What | Where | Result |
|---|---|---|
| Kit v3 downloaded from freyavoice.ai/hackathon into the repo | `kit/` (PR #1) | unmodified |
| `.env` names aligned with the kit (`FREYA_BANK_TEAM_KEY`, `FREYA_API_URL`) | `.env.example` (PR #1) | |
| Claude via the Claude Code login, no API key | `builder/llm.py` (PR #2) | text and schema-enforced JSON tested |
| Create/update a workflow **by name** in the shared workspace | `builder/deploy.py` (PR #2) | list route shape verified |
| Builder v1: spec → workflow → dry run → deploy → chat smoke test → practice cases → export | `builder/*.py` (PR #6) | see results |
| Date/account engine as a Freya code step | `builder/phone_code.py` | correct on all 13 practice cases |
| Rana's three hook findings fixed | `builder/tools.py` | `test_tools` all pass |
| Offline workflow checks (no Freya, no credit) | `builder/test_generate.py` (PR #7) | A+B, raw-a, rules-c pass |
| Rana's `test_spec` run on this machine | `tests/out/` (gitignored) | **raw-a PASS, rules-c PASS** |
| Credit rules, balance endpoint | PLAN.md (PR #8, #9) | |

## Results measured on Freya (practice cases)

- Kit example agent: **0/10** on Brief A. Failures were missing tools (no callback, no transfer), missing outcome
  values in the `close_call` enum (`paid`), no date math, no retry. All of these are what our builder now covers.
- Builder v1, spec from Brief A only: **9/10** on A. Only PUB-10 failed, and its ledger was right: the judge read
  "this call is recorded" in the mandatory opening as "said recorded before the promise succeeded".
- Builder v1, full pipeline on A+B: **2/3** on B, build time **222 s**. PUB-12: one extra persuasion attempt on an
  early-band product (ledger right). The per-product attempt wording was tightened afterwards; **not re-measured**.
- A 13 × 2 run after that is **invalid**: Freya's Python sandbox (snekbox) was down (see Lessons).
- Test A cases with an agent built from Brief A only. An A+B agent applies Brief B's `add_note` rule to A cases.

## Decisions and why (do not reopen without new evidence)

- **Fixed call shape + spec, not an LLM writing the whole workflow.** The hidden briefs are "same kind of call,
  different rules", and the agent model is weak, so structure and arithmetic live in code; the brief fills in
  values and instructions. The kit's example builder (Claude writes the JSON) was not run as a baseline.
- **Spec = two parallel Claude calls**: values for code (schema-enforced) + every rule rewritten per call stage.
  Then code checks it against the tool API and asks once for a fix. raw-a (amending memo) and rules-c (other bank)
  pass, so a separate "normalise raw material" step is **not needed for now**.
- **`close_call` is an end-of-call lifecycle tool** (like the kit example), with a pre-hook that overrides the
  outcome where the call's records decide it (promise recorded, transfer done, identity failed, callback booked).
  Other outcomes are chosen by the model from the outcome table in the tool description.
- **Call ending** uses the kit example's `end_call` trigger phrase `"Have a good day."`.
- **Self-tests on hidden briefs are limited**: the mock bank creates practice sessions only for the 13 public case
  ids. The builder therefore validates (dry run) and runs one chat turn; practice cases only with `--test A|B`.
- **No Anthropic API key exists or will exist.** Everything goes through the Claude Code login.

## Lessons (already solved; see PLAN.md "Gotchas")

- **Snekbox outage (10 Oct ~14:38 UTC):** every code step and every tool with a hook failed
  (`Failed to reach snekbox`). A hook failure fails the whole tool call. Reported to the organisers. Check
  transcripts for `snekbox` before believing a bad score.
- **Credits are credits, not dollars**: 1 credit = $0.50. ~0.10 credit per simulated call. 196.5 credits left after
  the top-up. Earlier messages said "$5.98 used"; it was 5.98 credits (≈ $3).
- A chat call baked `test_variables.customer_id` into tool bodies → the bank said `unknown customer_id`. Fixed:
  no `customer_id` in `test_variables`.
- Windows TLS to the mock bank, `.env` parsing by `uv`, `python3` shim, `fk_` vs `fak_` keys: see PLAN.md.

## Not done yet (proposed, ordered by expected score gain)

1. **Pre-hook guard on `create_promise`** (owner: Şevval): before the bank call, check date (business day, not a
   holiday, not after the product's deadline) and amount (floor ≤ amount ≤ past due) against the code-step facts;
   if wrong, do not record and tell the agent what to offer. Open question to verify with one chat turn: can a
   pre-hook stop the request (the docs only say it can rewrite it)?
2. **Pre-hook guard on `verify_identity`** (owner: Şevval): do not send an answer that is not in the expected
   format (e.g. 3 digits of a 4-digit number said in two pieces); a wrong answer cannot be taken back.
3. **Re-measure** PUB-12 and the latest fixes with targeted cases only (ask the human first; ~0.3 credit).
4. **Speech styles**: one targeted run each for `pieces` and `in_words` on 2–3 cases.
5. **Outage resilience**: decide whether critical tools should work without hooks.
6. **Off-topic questions** (raised by Şevval, parked): a one-line system-prompt rule ("only this bank matter;
   brief rules for robot/scam questions win") is preferred over a global node, which adds a routing call per turn
   and could misfire on questions the brief wants answered. Do not implement until the team decides.
7. Final rehearsal before the Sun 15:00 UTC freeze: `--reps 3` on all cases once, then a dry run of the final
   command with `--name submission-<brief>`, and a check that the trace has everything the organisers ask for.

## Estimate (no measurement yet)

Practice cases pass 80–90 % in a single run. With hidden briefs, people-like customers and the 3-runs rule,
**50–70 %** is a realistic range. The biggest remaining risks are model judgement (persuasion counting, rule
priority, exact sentences) and numbers said in pieces. Items 1–2 above move the riskiest rules into code.

## How the two of us work

- Rana owns `builder/spec.py` and its tests; Şevval owns `generate.py`, `tools.py`, `phone_code.py`, `deploy.py`,
  `build.py`. Small PRs to `main`; run the offline tests before every PR.
- One shared Freya workspace and key: one simulation at a time, announced in chat. Coding agents ask the human
  before any simulation (cases + estimated credits).
- Commits by Şevval use the GitHub account `sevvaldegirmenci` (noreply email). Never use a work email.
