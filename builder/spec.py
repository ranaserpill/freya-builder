"""Brief + tool API -> spec: the structured facts the generator needs.

Two model calls run in parallel:
  * facts: the values code needs (calendar, bands, product floors, callback window, outcome table, ...)
  * instructions: every rule of the brief rewritten as an instruction for one stage of the call

Then the spec is checked against the tool API (enum values, response fields). If something does not fit,
the model gets the list of problems once and fixes its answer.

Nothing in this file may name a value from a brief. Stage names and tool names are ours / fixed by the event.
"""
import asyncio
import json

from builder import llm, trace

STAGES = {
    "global": "rules that hold for the whole call, in every stage",
    "opening": "the first sentence and finding out who is on the line, before any security question",
    "third_party": "someone other than the customer answered (relative, wrong number, death, callback)",
    "identity": "the security questions and their outcomes (wrong answers, refusals, hints)",
    "collection": "after identity is verified: stating the debt, dates, amounts, persuasion, special situations "
                  "the customer raises (hardship, already paid, dispute, plan, human, scam, robot), read-back, "
                  "confirmation, recording promises, notes, transfers",
    "closing": "how every call ends: what to say, outcome and reason codes",
}

S = lambda **p: {"type": "object", "properties": p, "required": list(p), "additionalProperties": False}
STR, INT = {"type": "string"}, {"type": "integer"}
ARR = lambda items: {"type": "array", "items": items}

FACTS_SCHEMA = S(
    bank_name=STR,
    language=STR,
    opening_line=STR,
    identity_questions=ARR(S(field=STR, ask=STR, answer_format=STR)),
    weekend_days=ARR(STR),
    holidays=ARR(STR),
    bands=ARR(S(name=STR, min_days_late=INT, max_days_late=INT,
                deadline_unit={"type": "string", "enum": ["business_days", "calendar_days"]},
                deadline_count=INT, persuasion_attempts=INT,
                offers=ARR(S(amount={"type": "string", "enum": ["full", "floor", "full_or_floor", "other"]},
                             date={"type": "string", "enum": ["end_of_week", "deadline", "today", "next_business_day", "other"]},
                             text=STR)))),
    product_types=ARR(S(type=STR, label_template=STR, floor_field=STR)),
    callback=S(earliest=STR, latest=STR, max_business_days_ahead=INT),
    promise_attempts_max=INT,
    outcomes=ARR(S(outcome=STR, reason=STR, when=STR)),
    deterministic=S(
        promise_recorded=S(outcome=STR, reason=STR),
        identity_failed=S(outcome=STR, reason=STR),
        callback_scheduled=S(outcome=STR, reason=STR),
        transfers=ARR(S(queue=STR, outcome=STR, reason=STR)),
    ),
)

INSTRUCTIONS_SCHEMA = S(**{k: ARR(STR) for k in STAGES})

SYSTEM = """You turn a bank's specification for outbound payment-collection phone calls into structured input \
for a program that builds the phone agent. The phone agent is a weaker model: it only knows what you write down.

The specification may be one clean document or raw material (mails, policy extracts, memos, code lists). When a \
later document changes an earlier one, the later one wins: output only the rules in force. Never invent a rule \
or a value that the material does not give. Use the tool API file for exact tool field names and allowed values."""

FACTS_PROMPT = """Extract these values.

- bank_name, language (of the calls).
- opening_line: the agent's exact first spoken line, built from the material's opening rules, ending with the \
question that asks whether the right person is on the line. Write call variables as {{{{title}}}}, \
{{{{first_name}}}}, {{{{last_name}}}}. Reserve words like \"recorded\", \"saved\" and \"registered\" for something a tool has just stored successfully. When the material asks the agent to say, in its own words, that the call is being recorded, say it with \"recording\" (\"we are recording this call\"), so the customer never hears \"recorded\" before a tool has stored something. A sentence the material quotes word for word stays exactly as quoted.
- identity_questions: in the order they are asked. field = the exact value the identity tool expects for that \
question (from the tool API). ask = the question to say. answer_format = how to send the answer to the tool.
- weekend_days: weekday names that are not business days. holidays: every non-business date as YYYY-MM-DD.
- bands: how lateness (days_late) sets the latest allowed promise date and the number of persuasion attempts. \
deadline_count counted from today in deadline_unit. Cover every days_late range the material names. \
offers: the band's persuasion attempts in order, exactly persuasion_attempts entries: what the agent proposes after \
a refusal. amount: full = the full past-due amount; floor = the product's lowest accepted amount; full_or_floor = the \
full amount, or the floor if the customer already said the full amount is too much; other = anything else. date: \
end_of_week = the last business day of the current week (of next week if today is that day); deadline = the band's \
latest allowed date; today; next_business_day; other = anything else. text = the attempt in the material's own words.
- product_types: one per product type in the tool API's account result. label_template = how the agent names \
the product aloud, with account fields in square brackets, e.g. "loan ending [last4]". floor_field = the account \
result field that holds the lowest amount the bank accepts for that product ("" if none).
- callback: earliest and latest time of day (HH:MM) for a callback, and how many business days after today a \
callback may be (0 = today only).
- promise_attempts_max: how many times in total the agent may call the promise tool for one product when it fails.
- outcomes: every row of the closing outcome table: outcome code, reason code ("" if none), and when it applies.
- deterministic: the outcome and reason to record when (a) at least one promise was recorded, (b) the identity \
check failed on wrong answers, (c) a callback was scheduled, and (d) for each transfer queue, after a transfer \
to it. Use "" where the material gives no reason.

Tool API:
{tool_api}

Specification material:
{brief}"""

INSTRUCTIONS_PROMPT = """Rewrite EVERY rule of the specification as short imperative instructions for the phone \
agent, grouped by the stage of the call where the agent needs it. Stages:
{stages}

Rules:
- Do not drop any rule, number, limit, condition or exception. Most failed calls come from one skipped rule.
- Copy every sentence the agent must say word for word, in double quotes.
- Reserve words like \"recorded\", \"saved\" and \"registered\" for something a tool has just stored successfully. When the material asks the agent to say, in its own words, that the call is being recorded, say it with \"recording\" (\"we are recording this call\"), so the customer never hears \"recorded\" before a tool has stored something. A sentence the material quotes word for word stays exactly as quoted.
- Replace cross-references ("see rule 30") with the content they point to.
- A rule that proposes a fallback (for example the deadline) when the customer gives no day or no answer applies only when they really gave none. Write next to it that a day the customer does name but that is not allowed is handled by the rules for weekends, holidays and dates after the deadline, never by that fallback.
- When the material limits how many times the agent may ask or try something (ask once more, at most N times), write the total as a number and what to do right after the last one (for example: ask at most twice in total; after the second unclear answer, end the call with that outcome).
- A rule that proposes a fallback (for example the deadline) when the customer gives no day or no answer applies only when they really gave none. Write next to it that a day the customer does name but that is not allowed is handled by the rules for weekends, holidays and dates after the deadline, never by that fallback.
- When the material limits how many times the agent may ask or try something (ask once more, at most N times), write the total as a number and what to do right after the last one (for example: ask at most twice in total; after the second unclear answer, end the call with that outcome).
- When the material says to offer, ask or explain something once, write that the agent says it exactly once and, after the customer declines or answers, never brings it up again in the call, not even in the goodbye.
- If the material counts persuasion attempts, spell out what an attempt is: an offer the agent makes after the customer refuses. Write that a refusal is answered with the next attempt's offer while the product has attempts left, that this also holds when the customer refuses several products at once (take them one by one), and that a product ends without a promise only after the customer has refused its last attempt. Make the count concrete: the agent counts the offers it has made for that product, not the customer's refusals; a product with N attempts gets at most N offers in total (the opening question about paying today is not an offer); restate this next to each band's attempt number.
- Name the tool to call and the exact field values to send (from the tool API).
- A rule that matters in several stages goes into each of them.
- Write for the agent, not about it: "Ask ...", "Never ...", "If the customer ..., then ...".
- The agent receives today's date, a calendar of business days and holidays, and per product the floor amount, \
the deadline and the number of persuasion attempts already computed. Keep the rules that say how to use them.
- Do not tell the agent to end the call with a particular phrase and do not mention a close_call-style tool: the \
program adds call ending and outcome recording itself. Do keep what the agent must say before the call ends.

Tool API:
{tool_api}

Specification material:
{brief}"""

FIX_PROMPT = """Your extraction has these problems against the tool API:
{problems}

Return the corrected extraction. Previous answer:
{previous}

Tool API:
{tool_api}

Specification material:
{brief}"""


def _schema(tool_api: dict, path_suffix: str) -> dict:
    for path, ops in (tool_api.get("paths") or {}).items():
        if path.rstrip("/").endswith("/" + path_suffix):
            return ops.get("post") or next(iter(ops.values()))
    return {}


def _request_props(op: dict) -> dict:
    return (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema", {}).get("properties", {})


def _enum(tool_api: dict, tool: str, field: str) -> list:
    return _request_props(_schema(tool_api, tool)).get(field, {}).get("enum") or []


def _account_item(tool_api: dict) -> dict:
    """Properties of one product in get_account's response."""
    op = _schema(tool_api, "get_account")
    schema = (((op.get("responses") or {}).get("200") or {}).get("content") or {}).get("application/json", {}).get("schema", {})
    return ((schema.get("properties", {}).get("products") or {}).get("items") or {}).get("properties", {})


def check(facts: dict, tool_api: dict) -> list[str]:
    """Problems that code can see. Empty when the facts fit the tool API."""
    problems = []
    fields = _enum(tool_api, "verify_identity", "field")
    for q in facts["identity_questions"]:
        if fields and q["field"] not in fields:
            problems.append(f"identity field {q['field']!r} is not one of {fields}")
    account = _account_item(tool_api)
    types = (account.get("type") or {}).get("enum") or []
    for t in facts["product_types"]:
        if types and t["type"] not in types:
            problems.append(f"product type {t['type']!r} is not one of {types}")
        if account and t["floor_field"] and t["floor_field"] not in account:
            problems.append(f"floor_field {t['floor_field']!r} is not an account field ({sorted(account)})")
    outcomes = _enum(tool_api, "close_call", "outcome")
    for o in facts["outcomes"] + [facts["deterministic"][k] for k in ("promise_recorded", "identity_failed", "callback_scheduled")] + facts["deterministic"]["transfers"]:
        if outcomes and o["outcome"] not in outcomes:
            problems.append(f"outcome {o['outcome']!r} is not one of {outcomes}")
    queues = _enum(tool_api, "transfer_to_agent", "queue")
    for t in facts["deterministic"]["transfers"]:
        if queues and t["queue"] not in queues:
            problems.append(f"queue {t['queue']!r} is not one of {queues}")
    for h in facts["holidays"]:
        if len(h) != 10 or h[4] != "-" or h[7] != "-":
            problems.append(f"holiday {h!r} is not YYYY-MM-DD")
    for b in facts["bands"]:
        if len(b.get("offers") or []) != b["persuasion_attempts"]:
            problems.append(f"band {b['name']!r}: {len(b.get('offers') or [])} offers for {b['persuasion_attempts']} persuasion attempts")
    ranges = sorted((b["min_days_late"], b["max_days_late"]) for b in facts["bands"])
    if not ranges:
        problems.append("no bands")
    for (a1, b1), (a2, b2) in zip(ranges, ranges[1:]):
        if a2 != b1 + 1:
            problems.append(f"bands leave a gap or overlap between {b1} and {a2} days late")
    if "{{last_name}}" not in facts["opening_line"] and "{{first_name}}" not in facts["opening_line"]:
        problems.append("opening_line must name the customer with {{title}} / {{first_name}} / {{last_name}}")
    return problems


async def _extract(brief: str, tool_api_text: str, tool_api: dict) -> dict:
    stages = "\n".join(f"- {k}: {v}" for k, v in STAGES.items())
    facts, instructions = await asyncio.gather(
        llm.ask_json_async("spec: extract rule values (calendar, bands, floors, outcomes)", SYSTEM,
                           FACTS_PROMPT.format(tool_api=tool_api_text, brief=brief), schema=FACTS_SCHEMA),
        llm.ask_json_async("spec: rewrite every brief rule as per-stage agent instructions", SYSTEM,
                           INSTRUCTIONS_PROMPT.format(stages=stages, tool_api=tool_api_text, brief=brief), schema=INSTRUCTIONS_SCHEMA),
    )
    problems = check(facts, tool_api)
    if problems:
        trace.step("spec problems, asking once for a fix: " + "; ".join(problems))
        facts = await llm.ask_json_async("spec: fix extraction problems found by code", SYSTEM,
                                         FIX_PROMPT.format(problems="\n".join(problems), previous=json.dumps(facts, indent=1),
                                                           tool_api=tool_api_text, brief=brief), schema=FACTS_SCHEMA)
        problems = check(facts, tool_api)
        if problems:
            trace.step("spec problems left (continuing): " + "; ".join(problems))
    return {**facts, "instructions": instructions}


def extract(briefs: list[str], tool_api_text: str) -> dict:
    brief = "\n\n".join(f"=== Document {i + 1} ===\n{b}" for i, b in enumerate(briefs))
    return asyncio.run(_extract(brief, tool_api_text, json.loads(tool_api_text)))
