"""Check phone_code.py against the public practice cases.

    uv run python -m builder.test_phone_code

The spec below is written by hand from kit/briefs/brief-a.md. It is a test fixture only: the builder itself
gets its spec from the brief at run time (spec.py).
"""
import json
from pathlib import Path

from builder import phone_code

ROOT = Path(__file__).resolve().parent.parent
SPEC_A = {
    "weekend_days": ["Saturday", "Sunday"],
    "holidays": ["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"],
    "bands": [
        {"name": "early", "min_days_late": 1, "max_days_late": 7, "deadline_unit": "business_days", "deadline_count": 12, "persuasion_attempts": 1},
        {"name": "late", "min_days_late": 8, "max_days_late": 45, "deadline_unit": "business_days", "deadline_count": 7, "persuasion_attempts": 2},
    ],
    "product_types": [
        {"type": "credit_card", "label_template": "credit card ending [card_last4]", "floor_field": "minimum_payment"},
        {"type": "personal_loan", "label_template": "personal loan", "floor_field": "instalment_amount"},
        {"type": "car_loan", "label_template": "car loan", "floor_field": "instalment_amount"},
    ],
    "callback": {"earliest": "10:00", "latest": "19:00", "max_business_days_ahead": 1},
}


def run(case, as_flat=False):
    products = [dict(p, product_id=f"p{i + 1}") for i, p in enumerate(case["products"])]
    v = {"now": case["variables"]["now"]}
    if as_flat:   # the engine may hand the list over as flattened keys
        for i, p in enumerate(products):
            for k, x in p.items():
                v[f"get_account_response.data.products.{i}.{k}"] = x
    else:
        v["fx_products_raw"] = json.dumps(products)
    return phone_code.compute(v, SPEC_A)


def main():
    cases = [c for c in json.load(open(ROOT / "kit" / "public-test-set.json")) if c["brief"] in "AB"]
    bad = 0
    for c in cases:
        for flat in (False, True):
            v = run(c, flat)
            if v.get("fx_error") or v["fx_account_state"] != "ok":
                print("ERROR", c["id"], v.get("fx_error"), v["fx_account_state"]); bad += 1; continue
            for pr in c["expected"]["promises"]:
                n = int(pr["product_id"][1:])
                deadline = v[f"fx_p{n}_deadline"]
                if pr["date"] > deadline:
                    print("FAIL", c["id"], pr, "after deadline", deadline); bad += 1
                line = next(l for l in v["fx_calendar"].splitlines() if l.startswith(f"- {pr['date']} "))
                if not line.endswith(": business day"):
                    print("FAIL", c["id"], pr["date"], "is not a business day:", line); bad += 1
    # Exact deadlines the cases name in their checks
    expect = {("PUB-04", 1): "2026-10-23", ("PUB-13", 2): "2026-10-23", ("PUB-07", 1): "2026-11-02", ("PUB-13", 1): "2026-11-02"}
    byid = {c["id"]: c for c in cases}
    for (cid, n), want in expect.items():
        got = run(byid[cid])[f"fx_p{n}_deadline"]
        if got != want:
            print("FAIL deadline", cid, n, got, "expected", want); bad += 1
    v = run(byid["PUB-07"])
    assert "2026-10-26 Monday 26 October 2026 (the week after next): bank HOLIDAY" in v["fx_calendar"], v["fx_calendar"]
    v = run(byid["PUB-02"])
    assert "Thursday 15 October 2026" in v["fx_callback_text"], v["fx_callback_text"]
    assert "(2026-10-16)" in v["fx_date_facts"]          # last business day of this week, used by attempt 1
    src = (ROOT / "builder" / "phone_code.py").read_text()
    assert "{" + "{" not in src and "}" + "}" not in src, "phone_code.py must not contain double braces"
    print("example facts (PUB-13):\n" + run(byid["PUB-13"])["fx_account_facts"])
    print("\nOK" if not bad else f"\n{bad} problem(s)")
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
