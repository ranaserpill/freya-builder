# PLAN — single source of truth for the team (Şevval, Rana) and our coding agents

**Coding agents: read this file and AGENTS.md before you plan, research or write code.** Most research is done;
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
- **Freya credit is ~$10** (organisers said they will raise it). 2.84 $ used by 14:40 UTC on 10 Oct; a 13-case
  run costs roughly 0.5–1 $. Check: `freya.api("GET", "/api/v2/analytics/credits", workspaceId=freya.workspace_id())`.
  → Run only the cases a change affects (`run_cases.py --only PUB-12`). Full `--reps 3` runs only before freezing.
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
Engine test (no Freya, no cost): `uv run python -m builder.test_phone_code`.

## Results so far (practice cases)

| Agent | Brief A (10) | Brief B (3) |
|---|---|---|
| Kit example (base-agent) | 0 | – |
| Builder v1, spec from A | 9 (PUB-10: judge read "this call is recorded" in the opening as "recorded" too early; ledger was right) | – |
| Builder v1, spec from A+B, full pipeline, build 222 s | – | 2 (PUB-12: 2 persuasion attempts on an early-band product; ledger was right) |
| v1 + per-product attempt wording | running (13 cases × 2) | |

The agent model (`experimental-5`) is sometimes slow (median turn 10–26 s); `run_cases.py` warns when it is.

## Known issues / next steps (owner)

1. Robustness to the raw-material hidden brief — **Rana**: write test briefs in `tests/briefs/` (Brief A as mail
   + policy + amending memo + code list; a brief with other holidays, 3 bands, another identity question,
   other outcome/queue names, with a matching openapi), run `spec.extract` only (no Freya), report misses.
2. Local tests of the hooks in `builder/tools.py` (`builder/test_tools.py`) — **Rana**.
3. Fix what 1–2 find in spec.py / tools.py / generate.py, persuasion counting, speech styles — **Şevval**.
4. Before freezing: `--reps 3` on all 13 cases, plus a couple of `--style` runs. Then rehearse the final run with
   `--name submission-<brief>` and check the trace has everything the organisers ask for.

## Gotchas already solved (do not debug these again)

- Python on Şevval's Windows machine fails TLS to the mock bank ("certificate has expired"): set
  `SSL_CERT_FILE=C:/Users/<you>/.ssl/ca-bundle.crt` (a copy of Git's CA bundle) in `.env`. No spaces in the path:
  `uv run --env-file` cannot parse them.
- Kit scripts do not read `.env`: run them with `uv run --env-file .env ...`.
- `python3` on Windows opens the Store; a shim in `~/bin` fixes Git Bash.
- `fk_` keys from the public Freya playground do not work; staging keys start with `fak_`.
- The workflow list route returns `{"workflows": [...], "total", "limit", "offset"}` (deploy.py relies on it).
