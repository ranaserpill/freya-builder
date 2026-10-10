# Plan

Times in UTC (TR = UTC+3). Hidden briefs open **Sun 17:00**, submission **Sun 20:00**.

## 0. Unblock (Sat, now)
- [ ] Freya API key: staging-app.freyavoice.ai → Settings → API Keys → into `.env` on both machines.
- [ ] `claude` logged in on both machines (builder calls Claude through it).
- [ ] Baseline, recorded in `RESULTS.md`:
  - `examples/base-agent.json` on Brief A (expect ~2/13).
  - `examples/agent_builder.py` on A and on A+B, `--reps 3`. This is the number to beat.

## 1. Builder architecture (hybrid: LLM reads, code decides)
```
brief files + openapi.json
  1. normalise   LLM  raw material (mail, policy, memo that overrides, code list) -> one consolidated brief
  2. extract     LLM  consolidated brief -> spec.json (strict JSON schema, every rule keeps its id/quote)
  3. check       code spec sanity: tables complete, dates parse, enums exist in openapi, every outcome reachable
  4. generate    code spec -> workflow skeleton (nodes, routes, code nodes for calendar/deadline/floor math)
                 LLM  per-node prompts written only from the rules routed to that node
  5. validate    API  dry-run validate, then deploy.py (update in place, publish)
  6. self-test   API  personas generated FROM THE SPEC (hidden briefs have no practice cases) + kit cases if any
  7. repair      LLM  failing transcripts -> targeted prompt/route fixes, redeploy; stop at the time budget
```
- spec.json is generic: identity questions, third-party/callback window, calendar (business days, holidays),
  bands table (days_late range → deadline in business days, attempts), floor field per product type,
  amount rules, outcome/reason table, multi-product rules, tool field enums. Nothing brief-specific in code.
- All date/amount arithmetic runs in code nodes generated from spec values, never in the agent's head.
- Trace every stage (`builder/trace.py`). Hard stop at 25 min to leave margin under the 30 min limit.

## 2. Robustness (Sat evening → Sun 15:00)
- Our own "hidden-like" briefs: rewrite A/B with other holidays, bands, identity questions, outcome names,
  and one as raw material (mail + policy + overriding memo + code list). The builder must handle them
  with **no code change** — this is the no-hardcoding test.
- Practice with `run_cases.py --style pieces|corrects|talkative|asks_back|in_words`, always `--reps 3`.
- Track every run in `RESULTS.md` (date, commit, brief, score, notes).

## 3. Final (Sun)
- 15:00 code freeze on `main`. Only crash fixes after this.
- 17:00 run `uv run builder/build.py <brief> <openapi> 2>&1 | tee traces/hidden-N.log` for both briefs.
- Export with `freya.export_workflow`, commit `submission/` + `traces/`, make repo reachable for the jury,
  send the submission JSON before 20:00 (target 19:00).

## Who does what
| Rana | Şevval |
|---|---|
| 1 normalise + 2 extract + 3 check (spec schema) | 4 generate + 5 deploy |
| mutated test briefs | 6 self-test personas + 7 repair loop |

One simulation at a time per workspace: announce before running `run_cases.py`.
