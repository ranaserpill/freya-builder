"""Check spec.extract() against test briefs whose correct values are known.

    uv run python -m builder.test_spec              # extract (model calls) and check every brief
    uv run python -m builder.test_spec raw-a        # one brief
    uv run python -m builder.test_spec --cached     # re-check the last extraction without model calls

The briefs in tests/briefs/ are written by us to differ from the kit's: raw-a is Brief A as raw material with
a memo that changes three rules; rules-c has other bands, holidays, identity questions, outcomes and queues;
rules-c-multi is rules-c plus a multi-product addendum mail (like Brief A + Brief B) that also moves a holiday.
The EXPECTED values below are test fixtures only, never builder input.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "tests" / "briefs"
OUT = ROOT / "tests" / "out"

EXPECTED = {
    "raw-a": {
        "identity_fields": ["date_of_birth", "phone_last4"],
        "weekend_days": {"saturday", "sunday"},
        "holidays": {"2026-10-26", "2026-10-30", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"},
        "bands": [(1, 7, 12, 1), (8, 45, 5, 2)],          # memo: late band 7 -> 5 business days
        "offers": {1: [("full_or_floor", "end_of_week")], 8: [("full_or_floor", "end_of_week"), ("floor", "deadline")]},
        "floors": {"credit_card": "minimum_payment", "personal_loan": "instalment_amount", "car_loan": "instalment_amount"},
        "callback": ("10:00", "18:00", 1),                 # memo: 19:00 -> 18:00
        "promise_attempts_max": 2,
        "outcomes": {
            ("promise", ""), ("paid", ""),
            ("transferred", "restructuring"), ("transferred", "human"), ("transferred", "support"),
            ("no_promise", "refused"), ("no_promise", "hardship"), ("no_promise", "dispute"), ("no_promise", "service_error"),
            ("not_verified", "failed"), ("not_verified", "declined"),
            ("not_reached", "callback"), ("not_reached", "no_callback"), ("not_reached", "wrong_number"),
            ("not_reached", "deceased"), ("not_reached", "unclear"),
        },
        "deterministic": {
            "promise_recorded": ("promise", ""), "identity_failed": ("not_verified", "failed"),
            "callback_scheduled": ("not_reached", "callback"),
            "transfers": {"restructuring": ("transferred", "restructuring"), "general": ("transferred", "human"),
                          "support": ("transferred", "support")},
        },
        "must_say": ["I am sorry for your loss", "You will receive a text message confirming this promise", "Do you confirm"],
        "must_not_appear": ["19:00", "7th business day"],
    },
    "rules-c": {
        "identity_fields": ["postcode", "birth_year"],
        "weekend_days": {"saturday", "sunday"},
        "holidays": {"2026-10-19", "2026-11-02", "2026-12-24", "2026-12-31", "2027-01-06"},
        "bands": [(1, 10, 10, 1), (11, 30, 6, 2), (31, 60, 3, 2)],
        "offers": {1: [("full", "deadline")], 11: [("full", "deadline"), ("floor", "deadline")],
                   31: [("full", "deadline"), ("floor", "deadline")]},
        "floors": {"credit_card": "minimum_due", "overdraft": "minimum_due", "mortgage": "monthly_payment"},
        "callback": ("09:00", "17:30", 2),
        "promise_attempts_max": 3,
        "outcomes": {
            ("committed", ""), ("settled", ""),
            ("escalated", "plan"), ("escalated", "agent"), ("escalated", "welfare"),
            ("declined", "refusal"), ("declined", "vulnerability"), ("declined", "contested"), ("declined", "system_error"),
            ("unverified", "wrong_answers"), ("unverified", "refused_checks"),
            ("no_contact", "callback_booked"), ("no_contact", "no_slot"), ("no_contact", "wrong_party"),
            ("no_contact", "bereavement"), ("no_contact", "unconfirmed"),
        },
        "deterministic": {
            "promise_recorded": ("committed", ""), "identity_failed": ("unverified", "wrong_answers"),
            "callback_scheduled": ("no_contact", "callback_booked"),
            "transfers": {"payment_plans": ("escalated", "plan"), "customer_care": ("escalated", "agent"),
                          "welfare_team": ("escalated", "welfare")},
        },
        "must_say": ["Please accept our condolences", "A confirmation email is on its way to you", "Is that correct"],
        "must_not_appear": ["Freya Bank", "text message", "date_of_birth", "phone_last4"],
    },
}

# Two files, like Brief A + Brief B: the addendum adds multi-product rules and moves one holiday.
EXPECTED["rules-c-multi"] = {
    **EXPECTED["rules-c"],
    "files": ["rules-c.md", "rules-c-multi.md"],
    "holidays": {"2026-10-19", "2026-11-03", "2026-12-24", "2026-12-31", "2027-01-06"},
    "must_say": EXPECTED["rules-c"]["must_say"] + ["add_note", "system_error", "contested", "vulnerability"],
    # 2026-11-02 may still appear as "is NOT a holiday"; the holiday set above already checks the change.
}


def _pair(o: dict) -> tuple:
    return (o.get("outcome", ""), o.get("reason", "") or "")


def check(name: str, spec: dict) -> list[str]:
    """Differences between the extracted spec and the expected values. Empty = all good."""
    exp, bad = EXPECTED[name], []

    def eq(label, got, want):
        if got != want:
            bad.append(f"{label}: got {got!r}, expected {want!r}")

    eq("identity fields (in order)", [q["field"] for q in spec["identity_questions"]], exp["identity_fields"])
    eq("weekend days", {d.lower() for d in spec["weekend_days"]}, exp["weekend_days"])
    eq("holidays", set(spec["holidays"]), exp["holidays"])
    bands = sorted((b["min_days_late"], b["max_days_late"], b["deadline_count"], b["persuasion_attempts"]) for b in spec["bands"])
    eq("bands (min, max, deadline, attempts)", bands, exp["bands"])
    offers = {b["min_days_late"]: [(o["amount"], o["date"]) for o in b.get("offers") or []] for b in spec["bands"]}
    eq("band offers (amount, date) by min days late", offers, exp["offers"])
    units = {b["deadline_unit"] for b in spec["bands"]}
    eq("band deadline units", units, {"business_days"})
    eq("product floors", {p["type"]: p["floor_field"] for p in spec["product_types"]}, exp["floors"])
    cb = spec["callback"]
    eq("callback window", (cb["earliest"], cb["latest"], cb["max_business_days_ahead"]), exp["callback"])
    eq("promise attempts max", spec["promise_attempts_max"], exp["promise_attempts_max"])
    eq("outcome table", {_pair(o) for o in spec["outcomes"]}, exp["outcomes"])

    det, want = spec["deterministic"], exp["deterministic"]
    for key in ("promise_recorded", "identity_failed", "callback_scheduled"):
        eq(f"deterministic.{key}", _pair(det[key]), want[key])
    eq("deterministic.transfers", {t["queue"]: _pair(t) for t in det["transfers"]}, want["transfers"])

    text = json.dumps(spec["instructions"], ensure_ascii=False) + " " + spec.get("opening_line", "")
    for phrase in exp["must_say"]:
        if phrase.lower() not in text.lower():
            bad.append(f"instructions miss the sentence {phrase!r}")
    for phrase in exp["must_not_appear"]:
        if phrase.lower() in text.lower():
            bad.append(f"instructions contain {phrase!r}, which this brief does not use (or a memo replaced)")
    return bad


def extract(name: str) -> dict:
    from builder import spec  # imported here so --cached needs no Claude login
    exp = EXPECTED[name]
    files = exp.get("files", [f"{name}.md"])
    result = spec.extract([(BRIEFS / f).read_text(encoding="utf-8") for f in files],
                          (BRIEFS / exp.get("openapi", f"{name}.openapi.json")).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.spec.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def main(args: list[str]) -> int:
    cached = "--cached" in args
    names = [a for a in args if not a.startswith("--")] or list(EXPECTED)
    failed = 0
    for name in names:
        result = json.loads((OUT / f"{name}.spec.json").read_text(encoding="utf-8")) if cached else extract(name)
        problems = check(name, result)
        failed += bool(problems)
        print(f"{'PASS' if not problems else 'FAIL'} {name}" + "".join(f"\n   - {p}" for p in problems))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
