"""Score a finished simulation without run_cases.py (e.g. after run_cases died on a Freya 5xx mid-run).

    uv run --env-file .env python -m builder.score_sim <simulation_id> [--out out/x.json]

For each run: the case id comes from the persona name ("PUB-07 ..."), the customer id from the call's tool calls,
the ledger from the mock bank, the conversation verdict from Freya's judge. Same checks as run_cases.py.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from builder import deploy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))
from score import http, score_ledger  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("simulation_id")
    ap.add_argument("--out")
    a = ap.parse_args()
    freya = deploy._freya()
    cases = {c["id"]: c for c in json.load(open(ROOT / "kit" / "public-test-set.json", encoding="utf-8"))}
    sim = freya.api("GET", f"/api/v2/simulations/{a.simulation_id}")
    sim = sim.get("simulation") or sim
    its = freya.api("GET", f"/api/v2/simulations/{a.simulation_id}/iterations")
    its = its.get("iterations") or its.get("items") or its
    runs = freya.get_iteration(a.simulation_id, its[0]["id"])["runs"]
    rows = []
    for r in runs:
        m = re.match(r"(PUB-\d+)", r.get("personaName") or "")
        case = cases.get(m.group(1)) if m else None
        if not case:
            continue
        call = freya.get_call(r["callId"]) if r.get("callId") else {"messages": []}
        text = json.dumps(call.get("messages", []))
        cid = re.search(r"c_[0-9a-f]{8}-[0-9a-f]{3,}", text)
        tools = [json.loads(x["message"]).get("function") for x in call.get("messages", [])
                 if x.get("role") == "system" and '"function_call_start"' in x.get("message", "")]
        res = score_ledger(case, http("/v1/practice/ledger/" + cid.group(0))) if cid else {"failed": ["no customer_id found in the call"]}
        verdict = r.get("outcome")
        if verdict != "pass":
            res["failed"].append(f"conversation ({verdict}): " + " ".join(str(r.get("reason") or "no verdict").split())[:400])
        outage = not [t for t in tools if t not in ("code_exec", "api_call")]
        # "inconclusive": Freya's judge gave no verdict (seen when its analysis came late). Ledger right + inconclusive
        # is a platform problem, not an agent failure; we count it separately.
        ledger_ok = not [f for f in res["failed"] if not f.startswith("conversation")]
        judge_gap = ledger_ok and verdict in ("inconclusive", "error", None)
        row = {"id": case["id"], "pass": not res["failed"], "failed": res["failed"], "tools": tools, "call_id": r.get("callId"),
               "ended": call.get("endedReason"), "outage_suspect": outage, "verdict": verdict, "judge_gap": judge_gap}
        rows.append(row)
        label = "PASS" if row["pass"] else ("JUDGE?" if judge_gap else "FAIL")
        print(label, case["id"], "| " + " > ".join(t for t in tools if t not in ("code_exec", "api_call"))
              + ("   (no bank tool calls: outage?)" if outage else ""))
        for f in row["failed"]:
            print("       -", f[:260])
    gaps = sum(r["judge_gap"] and not r["pass"] for r in rows)
    print(f"\n{sum(r['pass'] for r in rows)} / {len(rows)} passed" + (f", {gaps} more with a right ledger but no judge verdict" if gaps else "")
          + f". Simulation {a.simulation_id}, status {sim.get('status')}.")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"simulation_id": a.simulation_id, "rows": rows}, open(a.out, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
