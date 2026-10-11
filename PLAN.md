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
- **Freya credit (checked 11 Oct 06:20 UTC): 496.5 credits left ≈ $248** (1 credit = $0.50; topped up twice).
  Used so far: 5.98 credits, all on 10 Oct. Costs are in **credits**: ~0.10 credit per simulated call, so a
  13-case `--reps 3` run ≈ 4 credits. A builder run without `--test` (spec + deploy + one chat turn) ≈ 0.
  **Budget for 11 Oct (Rana + Şevval agreed):**
  | Bucket | Credits | When |
  |---|---|---|
  | Hidden-brief reserve: builder runs, chat probes, reruns after a crash fix | 150 | Sun 17:00–20:00 UTC |
  | Team's manual tests at the end | 50 | before submitting |
  | Pre-freeze check: 13 cases `--reps 3` + one `--style` run per style | ~15 (×2 if a fix needs a recheck) | Sun before 15:00 UTC |
  | Daytime development (targeted cases) | the rest | until 15:00 UTC |
  **Hard floor: never let the balance drop below 200 credits before 17:00 UTC** (150 reserve + 50 manual).
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
| 11 Oct, agent from `tests/briefs/raw-a.md` (raw material), A cases the memo does not change | 8/9 (only PUB-10, judge read "this call is recorded") | – |
| same + spec fix "we are recording this call" (PR #13) | PUB-10 **3/3** | – |
| same, `--style in_words` PUB-01/06/07 | **3/3** | – |
| same, `--style pieces` PUB-01/03/06 | 2/3 — PUB-03: the simulated customer mixed its pieces into the *correct* date of birth; the agent behaved right (transcript read, not rerun) | – |
| 11 Oct, A+B agent from main (PRs #11–#14) | – | 2/3 (PUB-12: no persuasion on products refused up front) |
| + spec: an attempt is an offer, count offers not refusals (PR #15) | PUB-05/06/07 3/3 (agent from A) | **PUB-12 3/3**, PUB-11 ✓, PUB-13 ✓ |
| 11 Oct 07:20, all 13 cases, agents from main after #15 | 9/10 (PUB-05: support team mentioned again in the goodbye) | 2/3 (**PUB-13: the agent said 30 Oct is after the 2 Nov deadline** — the model compares dates wrongly; code computed the deadline right) |
| + spec: "offer once" = never brought up again (PR #16) | PUB-05 **3/3**, PUB-03 ✓, PUB-06 ✓ | – |
| + allowed promise dates per product (PR #17, measured by Rana) | PUB-07 **3/3**, PUB-04 ✓, PUB-06 ✓ | **PUB-13 3/3**, PUB-11 ✓ |
| + concrete persuasion offers per product (PR #17, A+B agent, 11 Oct 09:00 UTC) | – | PUB-12 **2/3** (offer counts right in all 3; the failing run skipped the two `add_note` calls in a run with a 70 s agent turn and a customer hang-up), PUB-11 ✓, PUB-13 ✓ |

Date comparisons: done (PR #17 lists each product's allowed dates; the agent checks membership). rules-c and
rules-c-multi pass `test_spec` with the offers check.

**add_note fix (PR #19, 11 Oct 09:40 UTC):** the failing PUB-12 run was the agent going silent after
`create_promise` (customer hung up, notes never written). Now the promise hook's `what_to_do_next` says: record the
next confirmed promise, then make the other required calls (e.g. notes), then tell the customer. PUB-12 **2/2 PASS**
(promise + both notes, offer counts right); the 3rd run was lost to a Freya API outage (503/504).
**Tried and reverted:** "write each product's note as soon as it is settled" made the agent note a refusal before
making any offer and say "recorded" before recording (PUB-12 0/3). Do not reintroduce it.

**Pre-freeze rehearsal (11 Oct, agents rebuilt from `main` after #21; Freya unstable 10:15–12:20 UTC):**
- A agent, rep 1: **10/10**. Rep 2: ledger right in **10/10**; 6 judge "pass", 4 judge **"inconclusive"** whose reasons
  say "all criteria met" (late analysis). Rep 3 and 4 hit the outage (no tool calls / runs stuck) → invalid, cancelled.
  Clean rerun after the platform recovered (12:45 UTC): **10/10**.
- A+B agent, B cases `--reps 3`: **PUB-11 3/3, PUB-13 3/3, PUB-12 1/3** — run 1 hit the outage (DOB asked 39× on
  tool errors); run 3 is a real miss: no second offer on the late-band personal loan. **Known risk, not fixed before
  the freeze** (persuasion wording lives in spec.py; a change there touches every case).
- Final-command rehearsal with `--name submission-rehearsal` (no simulation): raw-a ✅ 305 s (chat 504 retried),
  rules-c + rules-c-multi ✅ 109 s. Found and fixed: a chat-route 504 stopped the build before export (PR #25).
  The rehearsal workflow was deleted afterwards (workspace: 7 workflows).
- Fix for the PUB-12 miss (PR #27): the agent took the customer's up-front "not paying those" as settling the products
  and wrote the notes with no offer. Now: an up-front refusal does not settle a product; make its listed offers first;
  the promise hook lists offers before notes. Measured: B x3 → run 1 invalid (median agent turn 70 s, 2 hang-ups),
  runs 2–3 **3/3 and 3/3** (PUB-12 offers then notes); A x1 **10/10**.
- Speech styles on PUB-04/06/07 (A agent): asks_back **3/3**; talkative 2/3 (PUB-04: the simulated customer's turns
  were cut mid-sentence and never gave a date; the agent treated non-answers as refusals as the brief says — simulator
  artefact); corrects 2/3 (PUB-04: **real miss**, the agent lowered the amount to the floor, claiming the customer had
  said the full amount was too much).
- Fix (PR #28): "when the customer accepts a date, keep the amount on the table; never lower it on your own; never
  attribute words to the customer". Measured: PUB-04 corrects **2/2**, PUB-04 + PUB-06 normal ✓, PUB-12 ✓.
- **Verdict: freeze `main` after PR #28.**
- Judge verdict values seen: `pass`, `fail`, `inconclusive`, `error`. `score_sim` shows ledger-right + no verdict as `JUDGE?`.

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

## Final-night checklist (Sun, UTC; TR = UTC+3)

**One machine runs the final** (Şevval's, tested end to end; Rana's is the backup). The other person checks.

16:30 pre-flight (no simulation):
- [ ] `git checkout main && git pull && uv sync`; `claude` logged in; `.env` has the Freya key and team key.
- [ ] Offline tests pass: `test_phone_code`, `test_tools`, `test_generate`.
- [ ] Platform up: one chat turn, or `GET /api/v2/workspaces` answers 200. Credit: `creditsLeft` > 150.
- [ ] **At most 8 workflows in the workspace** (the hackathon page says 10 per workspace; the final creates 2).
      List: `GET /api/v2/workflow?workspaceId=…` → `total`. Delete unused dev ones:
      `freya.api("DELETE", "/api/v2/workflow/<id>", workspaceId=freya.workspace_id())` (works). 11 Oct 12:25 UTC: 7.
- [ ] If `run_cases.py` died on a 5xx: rescore the finished simulation with `python -m builder.score_sim <sim_id>`;
      run tests through `python -m builder.run_cases_retry …` (same arguments, retries 5xx).
- [ ] Repo reachable for the organisers (public, or their account added). Decide before 17:00.

17:00 hidden briefs arrive (mail):
- [ ] Save as `briefs/hidden-1.md`, `briefs/hidden-1.openapi.json`, `briefs/hidden-2.md`, `briefs/hidden-2.openapi.json`
      (raw material with several files: pass all brief files in order, the openapi last).
- [ ] Run both (they can run in parallel, ~2–4 min each):
      `uv run builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json --name submission-hidden-1 2>&1 | tee traces/hidden-1.log`
      `uv run builder/build.py briefs/hidden-2.md briefs/hidden-2.openapi.json --name submission-hidden-2 2>&1 | tee traces/hidden-2.log`
- [ ] Each trace ends with `END ok`, shows the MODEL lines, `FREYA workflow=… agent=…`, `TEST chat smoke test … 1/1`, and
      `exported to submission/submission-hidden-N.workflow.json`. Check for leftover keys (trace.py redacts them).
- [ ] Read `out/submission-hidden-N.spec.json` once: identity questions, bands, holidays, outcomes look like the brief.
- [ ] If a run crashes: fix the bug generically (nothing from the hidden brief in code or prompts), commit, rerun, and
      submit only the trace of the run whose workflow you submit. Never edit the agent on the platform.

18:30 submit (deadline 20:00):
- [ ] Commit `submission/submission-hidden-*.workflow.json` and `traces/hidden-*.log` to `main`; note the commit hash.
- [ ] Send the form to the address in the kit email:

```json
{
  "team": "<our team name>",
  "repo": "https://github.com/ranaserpill/freya-builder",
  "commit": "<hash of the commit above>",
  "run_command": "uv run builder/build.py {brief_path} {tool_api_path}",
  "workflows": {
    "hidden-1": "submission/submission-hidden-1.workflow.json",
    "hidden-2": "submission/submission-hidden-2.workflow.json"
  },
  "traces": {"hidden-1": "traces/hidden-1.log", "hidden-2": "traces/hidden-2.log"}
}
```

Organisers rerun the top 10 from the commit: setup is in README (uv, `.env` with their Freya key and team key, a Claude
login or `ANTHROPIC_API_KEY`).

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

**Freya outages (tips from another team, confirmed by us on 11 Oct 09:38–10:07 UTC: 503/504/502):**
- Check the parts separately: a 504 on `/api/v2/chat/message` does not mean simulations are down.
- What runs in the workspace: `GET /api/v2/simulations?workspaceId=…&limit=10`. Only one runs at a time.
- Do not kill `run_cases.py` hoping to stop a run: the simulation keeps running on Freya and the next test waits
  for it. A stuck one (another team had one "running" for 9 h) stops with `POST /api/v2/simulations/{id}/cancel`.
- `builder/deploy.py` now retries 5xx answers 3× with 10 s waits (GET/PUT/dry run/publish/chat; a workflow create
  is never repeated blindly). `kit/freya.py` alone does not retry; `run_cases.py` does not either.
- **No tool calls in any customer and a median agent turn of 0 s = an outage, not a bug in the agent.** Do not
  "fix" the workflow after such a run; wait and rerun. (Ours: PUB-12 run with `tools: []`, judge "analysis never arrived".)

- Python on Şevval's Windows machine fails TLS to the mock bank ("certificate has expired"): set
  `SSL_CERT_FILE=C:/Users/<you>/.ssl/ca-bundle.crt` (a copy of Git's CA bundle) in `.env`. No spaces in the path:
  `uv run --env-file` cannot parse them.
- Kit scripts do not read `.env`: run them with `uv run --env-file .env ...`.
- `python3` on Windows opens the Store; a shim in `~/bin` fixes Git Bash.
- `fk_` keys from the public Freya playground do not work; staging keys start with `fak_`.
- `cryptography>=49` has no wheel for Intel Macs: PR #3 pins it below 49.
- The workflow list route returns `{"workflows": [...], "total", "limit", "offset"}` (deploy.py relies on it).
