# PLAN — single source of truth for the team (Şevval, Rana) and our coding agents

**Coding agents: read this file and AGENTS.md before you plan, research or write code** (history and decisions:
`docs/HANDOFF-*.md`). Most research is done;
the findings are below. Do not redo it. If you learn something that contradicts this file, fix this file in the
same PR. Keep it short.

## Event facts (verified)

- Hidden briefs: **Sun 11 Oct 17:00 UTC** (20:00 TR). Submission closes **20:00 UTC** (23:00 TR). The 3 hours are
  for running the builder and fixing crashes, not tuning. Nothing from a hidden brief may go into our code.
- Final: 2 hidden briefs (one clean spec, one **raw material**: mail + policy extract + memo that changes it +
  code list), 30 customers each, 1–3 products, several calendar days, customers talk like people
  (`--style pieces|corrects|talkative|asks_back|in_words`). Each case runs **3×; passes only if all 3 pass**.
- Score = passed / 60. Tie-breaks: total promised amount on passed cases, then shorter build time (from trace),
  then earlier submission. Builder ≤ 30 min per brief. Top 10 get rerun by the organisers from our commit.
- Submit: `freya.export_workflow` files, repo + commit, run command, one trace per hidden brief.
- Sources: kit v3 in `kit/` (README, docs/, briefs, tools). Hackathon page https://www.freyavoice.ai/hackathon
  (the kit zip is linked there). Public docs at docs.freyavoice.ai add little beyond `kit/docs/`; the only extra
  useful bits: `POST /api/v2/chat/message` (one turn, no queue) and chat fork (`fromMessageId`).

## Accounts and budget

- Freya staging workspace: "Şevval Değirmenci's Workspace" on https://staging-app.freyavoice.ai. **One key per
  team** — both of us use the same `fak_` key and the same `FREYA_BANK_TEAM_KEY` (share privately, never commit).
- **Freya credit (topped up, 10 Oct ~15:30 UTC): 196.5 credits left ≈ $98** (1 credit = $0.50). Simulations are
  allowed again. Costs are in **credits**: ~0.10 credit (≈ $0.05) per simulated call, so a 13-case `--reps 3`
  run ≈ 4 credits. 5.98 credits used before the top-up (2.6 of them on the sandbox outage).
  **Credit rules (simulations are allowed, wasting them is not):**
  1. Offline first: `test_phone_code`, `test_tools`, `test_generate` (and `test_spec` for spec changes) must pass
     before any Freya call. Many bugs need no simulation at all.
  2. Run only the cases the change affects (`--only PUB-12,PUB-13`). A full 13-case run only when a change touches
     every call (prompts for all steps, hooks used everywhere).
  3. `--reps 3` only for the pre-freeze check (Sun before 15:00 UTC), not after every change.
  4. Never rerun an unchanged agent to "see if it passes this time" more than once; read the transcript instead
     (`freya.get_call(call_id)`, free).
  5. Before a run of more than 5 calls, one chat turn first (`POST /api/v2/chat/message`) to make sure the
     platform works (the sandbox outage cost 2.6 credits).
  6. Announce every simulation in our chat (shared workspace, one at a time) and say how many calls it is.
  7. Coding agents: ask the human before starting any simulation; state the cases and the estimated credits.
  Balance: `freya.api("GET", f"/api/v2/workspaces/{freya.workspace_id()}/credits")` → `creditsLeft`.
  Usage: `/api/v2/analytics/credits` (in credits, not dollars).
- No Anthropic API key. The builder uses the Claude Code login (subscription limits apply).
- Dashboard (Optimize → Solutions, Simulations, AI Studio) = manual tools. Rules forbid hand-editing the agent, so
  we only use the dashboard to read transcripts.
- Rana's machine also has the `/gstack` and `/superpowers` skills and a server set up with Berk (details in
  Rana's own chat). Not needed so far: the builder runs locally and talks to Freya over the API.

## Architecture (branch `feat/generator`, on top of PR #1 and #2)

```
build.py  brief(s) + openapi.json
  spec.py       2 parallel Claude calls → facts (calendar, bands, floors, callback window, outcome table)
                + every rule as per-stage instructions; checked against the tool API, 1 fix round
  generate.py   fixed call shape, filled from the spec:
                setup(code) → opening → identity → load_account(get_account) → compute(code) → collection
                opening → third_party;  close_call runs at end of call
  phone_code.py date/account engine run as a Freya code step: deadlines per band, business days, holidays,
                callback window, product facts. Values only from the spec.
  tools.py      the 7 tools generated from openapi.json + post-hooks ("what_to_do_next" for the weak agent
                model: verify result, promise retry, callback, transfer) + close_call pre-hook that sets the
                outcome from the call's records (promise / transfer / identity failed / callback)
  deploy.py     create or update the workflow BY NAME in the shared workspace, publish
  then: dry-run validation, one chat turn smoke test, optional practice cases, export to submission/
```

Run: `uv run builder/build.py kit/briefs/brief-a.md kit/briefs/brief-b.md kit/tools/openapi.json --test B`
(workflow name `$DEV_WORKFLOW_NAME-<brief>`, so each of us keeps our own dev workflow).
Offline tests (no Freya, no credit; run all before every PR):
- `uv run python -m builder.test_phone_code` — date engine on all practice cases
- `uv run python -m builder.test_tools` — every hook with fake results
- `uv run python -m builder.test_generate` — builds a workflow from every spec in `out/` and `tests/out/` and checks
  routes, tool enums vs the tool API, the code step (compiled and run on synthetic accounts), prompt variables
- `uv run python -m builder.test_spec [--cached]` — spec extraction on `tests/briefs/` (Claude calls, no Freya).
  10 Oct: **raw-a PASS** (memo's 3 changes caught), **rules-c PASS** (3 bands, postcode/birth_year, renamed
  outcomes and queues); both also pass `test_generate`.

## Results so far (practice cases)

| Agent | Brief A (10) | Brief B (3) |
|---|---|---|
| Kit example (base-agent) | 0 | – |
| Builder v1, spec from A | 9 (PUB-10: judge read "this call is recorded" in the opening as "recorded" too early; ledger was right) | – |
| Builder v1, spec from A+B, full pipeline, build 222 s | – | 2 (PUB-12: 2 persuasion attempts on an early-band product; ledger was right) |
| v1 + per-product attempt wording, 13 cases × 2 | **invalid run**: Freya's Python sandbox was down (see below) | |

The agent model (`experimental-5`) is sometimes slow (median turn 10–26 s); `run_cases.py` warns when it is.
Test A cases with an agent built from Brief A only: an A+B agent applies Brief B's add_note rule to A cases.

**Platform outage, 10 Oct from ~14:38 UTC:** every code step and every tool with a pre/post hook failed with
`Failed to reach snekbox: Cannot connect to host snekbox-svc.staging.local:8060`. A failing hook fails the whole
tool call, so `verify_identity` and `close_call` failed too. Reported to the organisers. **Do not run simulations
while it lasts** (a one-turn chat probe is enough to check). Open question: make the critical tools work without
hooks so an outage during the final does not take every call down.

## Timeline (UTC; TR = UTC+3)

- Sat: builder working end to end ✅ → robustness (raw material, other rules, speech styles).
- **Sun 15:00 code freeze on `main`**; after that only crash fixes.
- Sun 17:00 hidden briefs: `uv run builder/build.py <brief> <openapi> --name submission-<brief> 2>&1 | tee traces/hidden-N.log`,
  check the trace, commit `submission/` + `traces/`, send the submission JSON (target 19:00, deadline 20:00).

## Owners and next steps

| Rana | Şevval |
|---|---|
| `spec.py` from now on (extraction, schema, checks) and its tests (`test_spec.py`, `tests/briefs/`) | `generate.py`, `tools.py`, `phone_code.py`, `deploy.py`, `build.py` |
| Run `test_spec.py` on `raw-a` and `rules-c`; fix misses in spec.py | Outage resilience; persuasion counting; speech styles |
| Idea: a "normalise" step (raw material → one consolidated brief) if `raw-a` shows misses | Before freeze: `--reps 3` on all cases + a few `--style` runs, final-run rehearsal |

Ideas not started (decide by cost): self-test personas generated from the spec (the mock bank creates practice
sessions only for the 13 public case ids, so hidden-brief self-tests need another way), and an LLM repair loop on
failed transcripts (fits the 30 min budget, but costs Freya credit per run).

Hook tests: `uv run python -m builder.test_tools` (Rana's three findings fixed: no engine `vars`, string body,
identity-failed flag `fx_identity`).

## Gotchas already solved (do not debug these again)

- Python on Şevval's Windows machine fails TLS to the mock bank ("certificate has expired"): set
  `SSL_CERT_FILE=C:/Users/<you>/.ssl/ca-bundle.crt` (a copy of Git's CA bundle) in `.env`. No spaces in the path:
  `uv run --env-file` cannot parse them.
- Kit scripts do not read `.env`: run them with `uv run --env-file .env ...`.
- `python3` on Windows opens the Store; a shim in `~/bin` fixes Git Bash.
- `fk_` keys from the public Freya playground do not work; staging keys start with `fak_`.
- `cryptography>=49` has no wheel for Intel Macs: PR #3 pins it below 49.
- The workflow list route returns `{"workflows": [...], "total", "limit", "offset"}` (deploy.py relies on it).
