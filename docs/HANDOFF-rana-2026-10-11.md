# Handoff: Rana's Claude Code session, 11 Oct 2026 (morning)

For Şevval's coding agent, which continues from here. PLAN.md stays the single source of truth for status and
rules; this file is the history behind today's changes. Read PLAN.md, AGENTS.md, then
`docs/HANDOFF-sevval-2026-10-10.md`, then this file. **Do not redo anything under "Done": read the results.**

## Done today (all merged to `main`)

| PR | What | Measured |
|---|---|---|
| #3 | `cryptography<49` so `uv sync` works on Intel Macs | – |
| #11 | `tests/briefs/rules-c-multi.md`: multi-product addendum (like A+B) + holiday move; `test_spec` takes several files | test_spec PASS |
| #12 | Credit budget in PLAN.md | – |
| #13 | spec: recording notice phrased with "recording" ("we are recording this call"); quoted sentences stay verbatim | **PUB-10 3/3** (was failing every build) |
| #14 | build.py: dry run under a throwaway name (`<name>-dryrun-<ts>`) | reruns with the same `--name` work (were 409 → `END failed`) |
| #15 | spec: a persuasion attempt is an offer; count offers, not refusals | PUB-12 3/3 once, later flaky (see #17) |
| #16 | spec: "offer once" = never brought up again, not even in the goodbye | **PUB-05 3/3**, PUB-03 ✓, PUB-06 ✓ |
| #17 | phone_code: **allowed promise dates listed per product** + generate prompt "look dates up in the list, never compare"; how to read a date not in the list | **PUB-13 3/3**, **PUB-07 3/3**, PUB-04 ✓, PUB-06 ✓, PUB-11 ✓ |
| #17 | spec bands get structured `offers[]` (amount: full/floor/full_or_floor/other; date: end_of_week/deadline/today/next_business_day/other; text); `check()` wants one offer per attempt; phone_code prints each product's offers as amounts + dates; attempts spelled out ("ONE offer… make no second offer") | see "Results" below |

Also: `raw-a` agent (raw material brief) on the A cases the memo does not change: 8/9, then 9/9 with #13;
speech styles on that agent: `in_words` 3/3, `pieces` 2/3 (PUB-03: the simulated customer mixed its pieces into
the *correct* date of birth — agent behaved right; not a builder bug).

## Results (practice cases)

- Full 13-case run on main after #15 (07:20 UTC): **11/13** → the two failures were fixed by #16 (PUB-05) and #17 (PUB-13).
- PUB-12 (persuasion counting across products) was the flakiest case: 3/3 → 0/3 → 1/3 across rebuilds with prompt-only
  fixes, because the model invents offers (skips a product, adds a third offer). #17 moves the offers into code.
  **Result of the offer lists on PUB-12: NOT MEASURED.** From ~11:10 UTC Freya answered 504 to everything (even
  `GET /api/v2/workspaces`), so the A+B rebuild never deployed. Offline: test_spec PASS on raw-a / rules-c /
  rules-c-multi including the new offers check, test_phone_code / test_tools / test_generate OK.
  → First thing to do once Freya answers again: item 1 below.

## Decisions and why (do not reopen without new evidence)

- **Dates and offers belong in code, not in the agent's head.** PUB-13 proved the agent model compares dates wrongly
  even when the deadline is given; listing the allowed dates fixed it. Same reasoning for persuasion offers.
- **Prompt rules that fixed a judge reading** (#13 "recording", #16 "once") are generic, not tuned to a brief.
- **No spec speed-up**: spec takes ~75–90 s per brief (the instructions call). Splitting it could save ~45 s but
  risks rule quality; build time is only the 2nd tie-break.
- **Never trust a simulation unless the build said `END ok`**; one test ran against a stale agent because a build
  failed (fixed by #14). Freya sometimes answers 504 while polling: `run_cases.py` then crashes; check the
  simulation list and rerun, do not count that run.

## Lessons

- Claude Code **session limit** hit once at ~09:00 UTC on Rana's Pro account (`spec` calls failed with "You've hit
  your session limit"). The builder needs Claude at 17:00 UTC: keep test_spec / rebuild runs modest in the
  afternoon, and keep the other person's machine as a backup builder.
- **Freya returned 504** twice today: once while `run_cases.py` polled a simulation, once on the dry-run POST in
  `build.py` (→ `END failed` after 5 min of spec work). A retry worked. **Add a retry with backoff around Freya
  calls in build.py/deploy.py before the final** (item 0 below), and if it happens tonight just rerun the build
  (#14 makes reruns safe).
- The spec instructions call once took 233 s / 25k output tokens instead of ~75 s / 9k: build time varies.
- zsh does not split a variable holding two file names; pass brief files literally.
- `tests/out/` is gitignored; `test_generate` needs those specs → run `test_spec` first on a fresh machine.

## Not done yet (ordered)

0. **Retry Freya 5xx** in build.py / deploy.py (validate, create/update, publish, chat smoke test): 3 tries with
   10–30 s backoff, logged to the trace. Small, protects the final.
1. **Confirm #17 on the full set**: rebuild `dev-<you>-a` (Brief A) and `dev-<you>-ab` (A+B), run all 13 cases once
   (~1.3 credits). Expect ≥ 12/13. If PUB-12 still fails, read the transcript before changing anything.
2. **Pre-freeze check before 15:00 UTC**: all 13 cases `--reps 3` (~4 credits) + `--style pieces|corrects|talkative|asks_back`
   on 2–3 cases each.
3. **Final rehearsal**: run the exact final command on `tests/briefs/raw-a.md` and `rules-c.md` with
   `--name submission-rehearsal-*`, check the trace has start/end, model calls, workflow/agent ids, chat test.
4. **15:00 UTC freeze. 17:00 UTC** hidden briefs: `uv run builder/build.py <brief(s)> <openapi> --name submission-hidden-N 2>&1 | tee traces/hidden-N.log`,
   check `END ok`, export is in `submission/`, commit `submission/` + `traces/`, make the repo reachable for the jury,
   send the submission JSON (target 19:00, deadline 20:00 UTC).
5. Optional if time: `create_promise` pre-hook guard (handoff 10 Oct item 1), outage resilience (item 5).

Credits at handoff: ~490 (floor 200 before 17:00 UTC; 150 reserved for the evening, 50 for manual tests).
