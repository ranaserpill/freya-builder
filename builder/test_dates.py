"""Date engine on call days the practice cases never use (they all run on Wed 14 Oct 11:00).

    uv run python -m builder.test_dates

The final runs customers "on several calendar days". The spec below is a test fixture (Brief A's values plus one
extra holiday on a Friday); the builder itself gets its spec from the brief at run time.
"""
import json
import sys

from builder import phone_code as pc
from builder.test_phone_code import SPEC_A

SPEC = dict(SPEC_A, holidays=SPEC_A["holidays"] + ["2026-10-30"])
PRODUCTS = json.dumps([
    {"product_id": "p1", "type": "personal_loan", "past_due": 540, "days_late": 5, "instalment_amount": 180},
    {"product_id": "p2", "type": "car_loan", "past_due": 900, "days_late": 20, "instalment_amount": 300},
])
FAILS = []


def facts(now, spec=SPEC):
    v = {"now": now, "fx_products_raw": PRODUCTS}
    pc.compute(v, spec)
    if v.get("fx_error"):
        FAILS.append(f"{now}: engine error {v['fx_error']}")
    return v


def expect(label, ok):
    if not ok:
        FAILS.append(label)


# Friday: "end of week" offers move to next Friday; deadlines count from Friday.
v = facts("2026-10-16T11:00")
expect("Fri: offer 1 on next Friday 23 Oct", "offer 1: 540.00 (or the floor 180.00 if the customer already said the full amount is too much) on Friday 23 October 2026" in v["fx_account_facts"])
expect("Fri: early deadline 5 Nov (12 business days, 26 Oct and 30 Oct holidays)", "(deadline): Thursday 5 November 2026" in v["fx_account_facts"])
expect("Fri: late deadline 28 Oct (7 business days)", "(deadline): Wednesday 28 October 2026" in v["fx_account_facts"])
expect("Fri: next business day Monday 19 Oct", "Next business day after today: Monday 19 October 2026" in v["fx_date_facts"])

# Thursday before a Friday holiday: Thursday is the last business day of the week.
v = facts("2026-10-29T11:00")
expect("Thu before Fri holiday: offer 1 moves to Fri 6 Nov", "on Friday 6 November 2026 (2026-11-06); offer 2" in v["fx_account_facts"])
expect("Thu before Fri holiday: next business day Mon 2 Nov", "Monday 2 November 2026" in v["fx_date_facts"])
expect("Thu before Fri holiday: 30 Oct not allowed", "2026-10-30" not in v["fx_account_facts"].split("Allowed promise dates for product 1")[1].split("\n")[0])

# Saturday call: today is not a business day, not an allowed promise date, not a callback day.
v = facts("2026-10-17T11:00")
expect("Sat: today flagged NOT a business day", "Today is NOT a business day" in v["fx_date_facts"])
expect("Sat: callback only Monday", v["fx_callback_text"].count("2026-10-") == 1 and "Monday 19 October" in v["fx_callback_text"])
expect("Sat: today not in allowed dates", "2026-10-17" not in v["fx_account_facts"])

# Late in the day: no callback slot left today once the window has closed.
expect("19:30: today dropped from callbacks", "Wednesday 14 October" not in facts("2026-10-14T19:30")["fx_callback_text"])
expect("18:30: today kept, later than now", "later than now (18:30) until 19:00" in facts("2026-10-14T18:30")["fx_callback_text"])
expect("09:00: today from the window start", "Wednesday 14 October 2026 (2026-10-14), from 10:00" in facts("2026-10-14T09:00")["fx_callback_text"])

# Times written without a leading zero or with a dot still compare correctly.
spec = dict(SPEC, callback={"earliest": "9:00", "latest": "17.30", "max_business_days_ahead": 2})
v = facts("2026-10-14T08:15", spec)
expect("9:00/17.30 normalised, 3 callback days", "from 09:00 until 17:30" in v["fx_callback_text"] and v["fx_callback_text"].count("until 17:30") == 3)

# Around Christmas and New Year.
v = facts("2026-12-24T11:00")
expect("24 Dec: next business day Mon 28 Dec", "Monday 28 December 2026" in v["fx_date_facts"])
expect("24 Dec: late deadline 6 Jan 2027 (25 Dec and 1 Jan skipped)", "(deadline): Wednesday 6 January 2027" in v["fx_account_facts"])

# Calendar-day deadlines (another brief may count them so).
spec = dict(SPEC, bands=[dict(b, deadline_unit="calendar_days", deadline_count=10) for b in SPEC["bands"]])
v = facts("2026-10-14T11:00", spec)
expect("calendar days: deadline 24 Oct", "(deadline): Saturday 24 October 2026" in v["fx_account_facts"])

if __name__ == "__main__":
    print("\n".join("FAIL " + f for f in FAILS) or "all date checks passed")
    sys.exit(1 if FAILS else 0)
