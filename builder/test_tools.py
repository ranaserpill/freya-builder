"""Run the Python hooks from tools.py locally with fake `result` / `vars` / `config` values.

    uv run python -m builder.test_tools

The engine runs a hook's source with `result` (post-hooks), `config` (pre-hooks) and `vars` in scope. We do the
same with exec(). Checks: no hook ever raises, every post-hook leaves a `what_to_do_next` sentence, the promise
retry counts correctly, and the close pre-hook picks the outcome the call's records require.
"""
import copy
import sys

from builder import tools

FAILS = []


def expect(label: str, got, want):
    if got != want:
        FAILS.append(f"{label}: got {got!r}, expected {want!r}")


def run(code: str, result=None, vars_=None, config=None, with_vars=True) -> dict:
    """Execute a hook like the engine does. Returns the scope after the run (result, vars, config)."""
    scope = {"result": result, "config": config if config is not None else {}}
    if with_vars:
        scope["vars"] = vars_ if vars_ is not None else {}
    try:
        exec(code, scope)
    except Exception as exc:  # a hook must never raise into the engine
        FAILS.append(f"hook raised {type(exc).__name__}: {exc}")
    return scope


def ok(**data):
    return {"status": 200, "header": {"x": "y"}, "data": {"ok": True, **data}}


def fail(error="boom", **data):
    return {"status": 200, "data": {"ok": False, "error": error, **data}}


def next_step(scope) -> str:
    r = scope["result"]
    return (r.get("data") or {}).get("what_to_do_next", "") if isinstance(r, dict) else ""


# ---- post-hooks never raise and always leave a next step -------------------------------------------------------

ODD_RESULTS = [None, "text", 42, [], {}, {"data": None}, {"data": "not a dict"}, {"status": 500},
               {"status": 500, "message": "upstream timeout"}, ok(), fail()]

POST_HOOKS = {"verify": tools.VERIFY_HOOK, "generic": tools.GENERIC_HOOK, "callback": tools.CALLBACK_HOOK,
              "transfer": tools.TRANSFER_HOOK, "promise(2)": tools.promise_hook(2)}

for name, hook in POST_HOOKS.items():
    for r in ODD_RESULTS:
        scope = run(hook, copy.deepcopy(r), {})
        if isinstance(r, dict) and not next_step(scope):
            FAILS.append(f"{name} hook left no what_to_do_next for result {r!r}")
    expect(f"{name} hook strips the response header", "header" in run(hook, ok(), {})["result"], False)
    for marker in ("{" + "{", "}" + "}"):
        expect(f"{name} hook source contains {marker!r} (the engine would template it)", marker in hook, False)


# ---- verify_identity -------------------------------------------------------------------------------------------

def verify_says(data: dict) -> str:
    return next_step(run(tools.VERIFY_HOOK, {"data": data}, {}))

expect("verify: all verified", "VERIFIED" in verify_says({"ok": True, "verified": True, "all_verified": True}), True)
expect("verify: one correct answer", "next security question" in verify_says({"ok": True, "verified": True, "all_verified": False}), True)
expect("verify: wrong, 2 left", "Wrong answers left: 2" in verify_says({"ok": True, "verified": False, "wrong_answers_left": 2}), True)
expect("verify: wrong, none left", "FAILED" in verify_says({"ok": True, "verified": False, "wrong_answers_left": 0}), True)
expect("verify: unreadable answer", "NOT count" in verify_says({"ok": False, "error": "cannot read date"}), True)
expect("verify: day/month hint", "day_month_swapped" in verify_says({"ok": True, "verified": False, "hint": "day_month_swapped", "wrong_answers_left": 2}), True)
expect("verify: booleans as strings", "VERIFIED" in verify_says({"ok": "true", "verified": "true", "all_verified": "True"}), True)


# ---- create_promise retry --------------------------------------------------------------------------------------

def promise_sequence(attempts_max: int, outcomes: list[bool]) -> tuple[list[str], dict]:
    v, says = {}, []
    hook = tools.promise_hook(attempts_max)
    for success in outcomes:
        says.append(next_step(run(hook, ok(promise_id="pr1") if success else fail("service down"), v)))
    return says, v

says, v = promise_sequence(2, [False, True])
expect("promise: 1st failure asks for a retry", "again right now" in says[0], True)
expect("promise: success after retry is recorded", "IS recorded" in says[1], True)
expect("promise: ok counter after retry", v.get("fx_promises_ok"), "1")

says, v = promise_sequence(2, [False, False])
expect("promise: 2nd failure stops (max 2)", "must not try again" in says[1], True)
expect("promise: no recorded promise after two failures", v.get("fx_promises_ok"), None)

says, v = promise_sequence(3, [False, False, True])
expect("promise: max 3 still retries after 2 failures", "again right now" in says[1], True)
expect("promise: max 3, third attempt recorded", v.get("fx_promises_ok"), "1")

says, v = promise_sequence(2, [True, False, False, True])   # product 1 ok, product 2 fails twice, product 3 ok
expect("promise: per-product failure counter resets", ["IS recorded" in says[0], "again right now" in says[1],
                                                        "must not try again" in says[2], "IS recorded" in says[3]],
       [True, True, True, True])
expect("promise: two products recorded", v.get("fx_promises_ok"), "2")

says, v = promise_sequence(1, [False])
expect("promise: max 1 never retries", "must not try again" in says[0], True)


# ---- callback / transfer set the flags close_call reads --------------------------------------------------------

v = {}
run(tools.CALLBACK_HOOK, ok(), v)
expect("callback ok sets flag", v.get("fx_callback_ok"), "yes")
v = {}
run(tools.CALLBACK_HOOK, fail(), v)
expect("failed callback sets no flag", v.get("fx_callback_ok"), None)
v = {"transfer_to_agent_args.queue": "support"}
run(tools.TRANSFER_HOOK, ok(), v)
expect("transfer ok sets flag + queue", (v.get("fx_transfer_ok"), v.get("fx_transfer_queue")), ("yes", "support"))


# ---- close_call pre-hook picks the outcome ---------------------------------------------------------------------

DET_A = {
    "promise_recorded": {"outcome": "promise", "reason": ""},
    "identity_failed": {"outcome": "not_verified", "reason": "failed"},
    "callback_scheduled": {"outcome": "not_reached", "reason": "callback"},
    "transfers": [{"queue": "restructuring", "outcome": "transferred", "reason": "restructuring"},
                  {"queue": "general", "outcome": "transferred", "reason": "human"},
                  {"queue": "support", "outcome": "transferred", "reason": "support"}],
}
OUTCOMES_A = [{"outcome": o, "reason": r, "when": ""} for o, r in [
    ("promise", ""), ("paid", ""), ("transferred", "restructuring"), ("transferred", "human"), ("transferred", "support"),
    ("no_promise", "refused"), ("no_promise", "hardship"), ("no_promise", "dispute"), ("no_promise", "service_error"),
    ("not_verified", "failed"), ("not_verified", "declined"), ("not_reached", "callback"), ("not_reached", "no_callback"),
    ("not_reached", "wrong_number"), ("not_reached", "deceased"), ("not_reached", "unclear")]]
CLOSE = tools.close_hook(DET_A, OUTCOMES_A)


def close(vars_: dict, model_outcome: str, model_reason: str = "", with_vars=True) -> tuple:
    body = {"customer_id": "c1", "outcome": model_outcome}
    if model_reason is not None:
        body["reason"] = model_reason
    run(CLOSE, None, dict(vars_), {"body": body}, with_vars=with_vars)
    return body.get("outcome"), body.get("reason")

CASES = [
    ("promise recorded beats model's no_promise", {"fx_promises_ok": "1"}, ("no_promise", "refused"), ("promise", None)),
    ("transfer after promise -> transferred", {"fx_promises_ok": "1", "fx_transfer_ok": "yes", "fx_transfer_queue": "restructuring"},
     ("promise", ""), ("transferred", "restructuring")),
    ("support transfer -> transferred/support", {"fx_transfer_ok": "yes", "fx_transfer_queue": "support"},
     ("no_promise", "hardship"), ("transferred", "support")),
    ("general queue maps to reason human", {"fx_transfer_ok": "yes", "fx_transfer_queue": "general"},
     ("transferred", "general"), ("transferred", "human")),
    ("queue only in tool args still counts", {"fx_transfer_ok": "yes", "transfer_to_agent_args.queue": "support"},
     ("no_promise", "hardship"), ("transferred", "support")),
    ("three wrong answers -> not_verified/failed", {"verify_identity_response.data.wrong_answers_left": 0,
                                                     "verify_identity_response.data.all_verified": False},
     ("not_verified", "declined"), ("not_verified", "failed")),
    ("callback booked -> not_reached/callback", {"fx_callback_ok": "yes"}, ("not_reached", "unclear"), ("not_reached", "callback")),
    ("failed transfer does not count", {"fx_transfer_queue": "support"}, ("no_promise", "hardship"), ("no_promise", "hardship")),
    ("nothing deterministic keeps the model's choice", {}, ("no_promise", "dispute"), ("no_promise", "dispute")),
    ("paid: reason dropped", {}, ("paid", "already_paid"), ("paid", None)),
    ("template leftover reason dropped", {}, ("no_promise", "{reason}"), ("no_promise", None)),
    ("empty reason dropped", {}, ("not_reached", ""), ("not_reached", None)),
    ("promise_recorded reason '' is dropped", {"fx_promises_ok": "2"}, ("promise", "x"), ("promise", None)),
]
for label, v, (mo, mr), want in CASES:
    expect(f"close: {label}", close(v, mo, mr), want)

# The engine may not inject `vars` into a hook. Python then finds the builtin vars() instead of a NameError.
expect("close without engine vars keeps the model's choice", close({}, "no_promise", "refused", with_vars=False),
       ("no_promise", "refused"))
scope = run(tools.CALLBACK_HOOK, ok(), with_vars=False)
if not next_step(scope):
    FAILS.append("callback hook without engine `vars` leaves no what_to_do_next: `_v = vars` binds the builtin "
                 "vars() function, `_v['fx_callback_ok'] = 'yes'` raises TypeError, the outer except swallows it")
scope = run(tools.promise_hook(2), ok(), with_vars=False)
if not next_step(scope):
    FAILS.append("promise hook without engine `vars` leaves no what_to_do_next (same builtin vars() cause)")

# A result whose data arrives as a JSON string is replaced by an empty dict: the agent loses the tool's answer.
scope = run(tools.GENERIC_HOOK, {"status": 200, "data": '{"ok": true}'}, {})
if (scope["result"] or {}).get("data", {}).get("ok") is None:
    FAILS.append("post-hooks replace a string `data` ('{\"ok\": true}') with {}: the tool's answer is lost and "
                 "a success is reported as FAILED")


if __name__ == "__main__":
    print("\n".join(f"FAIL {f}" for f in FAILS) or "all hook checks passed")
    sys.exit(1 if FAILS else 0)
