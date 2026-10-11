"""spec + tool API -> Freya workflow JSON.

The call's shape is fixed by the event (an outbound collections call with the seven bank tools). The brief fills in
everything else through the spec: the words, the rules, the values the code steps compute with.

  setup (code) -> opening -> identity -> load_account (get_account) -> compute (code) -> collection
                  opening -> third_party
  close_call runs by itself when the call ends; its pre-hook sets the outcome where the call's records decide it.
"""
import json
from pathlib import Path

from builder import tools

PHONE_CODE = Path(__file__).with_name("phone_code.py")
ENGINE_KEYS = ("weekend_days", "holidays", "bands", "product_types", "callback")


def code_source(spec: dict) -> str:
    engine = {k: spec.get(k) for k in ENGINE_KEYS}
    src = PHONE_CODE.read_text(encoding="utf-8")
    src += "\n\nSPEC = json.loads(" + repr(json.dumps(engine)) + ")\ncompute(vars, SPEC)\n"
    return tools.dbl_safe(src)


def code_node(name: str, nxt: str, spec: dict) -> dict:
    return {
        "name": name,
        "node_type": "code",
        "passthrough": True,
        "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [{
            "type": "function",
            "function": {
                "name": "code_exec",
                "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {
                    "code": {"type": "string", "default": code_source(spec)},
                    "timeout_ms": {"type": "number", "default": 10000},
                }},
            },
        }],
        "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}],
    }


def bullets(lines: list[str]) -> str:
    return "\n".join("- " + line for line in lines)


def conversation(name: str, task: str, node_tools: list, transitions=None, on_enter=None, extraction=None) -> dict:
    node = {
        "name": name,
        "node_type": "conversation",
        "task_message": task,
        "tools": node_tools + [tools.end_call_tool()],
        "transitions": transitions or [],
        "max_node_turns": 80,
        "max_turn_transition": "wrap_up",   # a stuck call ends politely; close_call still runs
        "on_enter": on_enter or {"type": "llm"},
        "on_enter_first_entry_only": True,
    }
    if extraction:
        node["extraction_schema"] = extraction
    return node


def is_true(variable: str) -> dict:
    return {"logic": "or", "conditions": [
        {"variable": variable, "operator": "equals", "operand": "true"},
        {"variable": variable, "operator": "equals", "operand": "True"},
    ]}


def equals(variable: str, value: str) -> dict:
    return {"logic": "or", "conditions": [{"variable": variable, "operator": "equals", "operand": value}]}


def build(spec: dict, tool_api: dict) -> dict:
    ops = tools.operations(tool_api)
    ins = spec["instructions"]
    hooks = {
        "verify_identity": tools.VERIFY_HOOK,
        "create_promise": tools.promise_hook(spec.get("promise_attempts_max") or 2),
        "schedule_callback": tools.CALLBACK_HOOK,
        "transfer_to_agent": tools.TRANSFER_HOOK,
    }
    when = {
        "verify_identity": "CALL it every time the customer gives an answer to a security question, once per answer.",
        "create_promise": "CALL it only after the customer clearly said yes to your read-back. One call per product.",
        "add_note": "CALL it only when your instructions say to record a note for a product.",
        "schedule_callback": "CALL it as soon as an allowed callback day and time is agreed.",
        "transfer_to_agent": "CALL it when your instructions say to transfer, with the queue they name.",
    }

    def tool(name: str) -> dict:
        url, op = ops[name]
        desc = (op.get("summary") or op.get("description") or name) + " " + when.get(name, "")
        return tools.api_tool(name, url, op, desc.strip(), post_hook=hooks.get(name, tools.GENERIC_HOOK))

    def mentioned(stage_text: str, names: list[str]) -> list:
        return [tool(n) for n in names if n in ops and n in stage_text]

    closing = "\n\nHOW THE CALL ENDS\n" + bullets(ins["closing"])
    questions = "\n".join(f"{i + 1}. Ask: \"{q['ask']}\" Send field \"{q['field']}\", answer as {q['answer_format']}."
                          for i, q in enumerate(spec["identity_questions"]))

    system = f"""You are the digital assistant of {spec['bank_name']}, making an outbound phone call to {{{{title}}}} {{{{first_name}}}} {{{{last_name}}}}. Speak {spec['language']}.
Keep every turn to one or two short sentences. Ask one question at a time.
Now is {{{{now}}}} ({{{{fx_today_text}}}}). Use this date, never the real clock.

RULES FOR THE WHOLE CALL
{bullets(ins['global'])}

TOOLS
- When a rule says to use a tool, CALL the tool. Saying that you did it is not enough.
- Call one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing.
- A tool result may contain "what_to_do_next". Follow it.
- Never say something was recorded, scheduled or transferred unless the tool result says it succeeded.
- Do not record the call's outcome yourself: it is recorded automatically when the call ends.

ENDING THE CALL
- When the call is over, say what your instructions require, thank the customer, say goodbye, and end your last message with exactly "{tools.END_PHRASE}". That sentence hangs up the phone, so never say it earlier."""

    opening_task = f"""STEP: OPENING. You have said your first sentence. Find out whether the person on the line is {{{{title}}}} {{{{last_name}}}}.
{bullets(ins['opening'])}
Do not ask any security question in this step. Do not call any tool except to transfer or end the call as your rules say.""" + closing

    third_task = f"""STEP: SOMEONE OTHER THAN THE CUSTOMER IS ON THE LINE.
{bullets(ins['third_party'])}

DATES
{{{{fx_date_facts}}}}
{{{{fx_callback_text}}}}
Calendar:
{{{{fx_calendar}}}}""" + closing

    identity_task = f"""STEP: SECURITY QUESTIONS. The person confirmed they are {{{{title}}}} {{{{last_name}}}}.
Questions, in this order:
{questions}
{bullets(ins['identity'])}
The account is loaded for you automatically once identity is verified: never call get_account yourself.""" + closing

    collection_task = f"""STEP: THE CUSTOMER IS VERIFIED. The account has already been loaded for you (get_account was called; do not call it).

ACCOUNT (computed for you; trust these values)
{{{{fx_account_facts}}}}
To check a promise date, look it up in that product's "Allowed promise dates" list; never compare dates yourself. A date in the list is allowed, even the last one. For a weekend day or holiday before the deadline, the "Weekend days and holidays" line gives the first allowed date after it: use that date, never the deadline. For a date after the deadline, the latest allowed date is the deadline. Then follow your instructions for dates that are not allowed.

DATES (computed for you; trust these values)
{{{{fx_date_facts}}}}
Calendar:
{{{{fx_calendar}}}}

INSTRUCTIONS
{bullets(ins['collection'])}

RECORDING
- After the customer confirms, record every confirmed promise right away, one tool call after another, before you
  say anything else. Never say a promise is recorded before its tool result says so.

AMOUNTS STAY UNLESS THE CUSTOMER CHANGES THEM
- When the customer accepts a date you proposed, keep the amount that was on the table: the full past-due amount,
  unless the customer has said in their own words that it is too much, or proposed another amount. Then read back.
- Never lower an amount on your own, and never say the customer said something they did not say.

OFFERS BEFORE GIVING UP ON A PRODUCT
- A refusal the customer gives before you made any offer for a product (for example "I'm not paying that one" at the
  start) does not settle that product. Make that product's offers, in the order its ACCOUNT lines list them, one at a
  time. The product is settled only when the customer accepts an offer or has refused its last listed offer.
- Do not end the call, and do not record a "refused"-type note for a product, while it still has an offer you have
  not made.""" + closing

    party = [{
        "name": "fx_party",
        "type": "string",
        "enum_values": ["customer", "someone_else", "unclear"],
        "description": "Who answered the phone. customer: the person clearly confirmed being the customer named in the "
                       "call (for example yes, that's me, speaking, or the customer's own name). someone_else: the person "
                       "says they are not the customer, that the customer cannot come to the phone, that the number is not "
                       "the customer's, or that the customer has died. unclear: anything else, such as hello, go ahead, who "
                       "is this, or a question.",
        "min_confidence": 0.6,
    }]
    names = list(ops)
    nodes = {
        "setup": code_node("setup", "opening", spec),
        "opening": conversation(
            "opening", opening_task, mentioned("\n".join(ins["opening"]), ["transfer_to_agent"]),
            transitions=[
                {"target_node": "identity", "description": "the customer confirmed who they are", "condition": equals("fx_party", "customer")},
                {"target_node": "third_party", "description": "someone else answered", "condition": equals("fx_party", "someone_else")},
            ],
            on_enter={"type": "tts", "text": spec["opening_line"]},
            extraction=party,
        ),
        "third_party": conversation("third_party", third_task, mentioned("\n".join(ins["third_party"]), ["schedule_callback", "transfer_to_agent"])),
        "identity": conversation(
            "identity", identity_task,
            [tool("verify_identity")] + mentioned("\n".join(ins["identity"] + ins["global"]), ["transfer_to_agent"]),
            transitions=[{"target_node": "load_account", "description": "identity verified", "condition": {"logic": "or", "conditions":
                          is_true("verify_identity_response.data.all_verified")["conditions"]
                          + [{"variable": "fx_identity", "operator": "equals", "operand": "verified"}]}}],
        ),
        "load_account": {
            "name": "load_account",
            "node_type": "api_request",
            "passthrough": True,
            "passthrough_default_transition": "compute",
            "on_enter": {"type": "silent"},
            "disable_inactivity_monitor": True,
            "pre_actions": [dict(tool("get_account"), config={"timeoutMs": 12000, "maxRetries": 2})],
            "response_mapping": [{"path": "data.products", "variable": "fx_products_raw"}],
            "transitions": [{"target_node": "compute", "description": "always", "condition": {"operator": "always"}}],
        },
        "compute": code_node("compute", "collection", spec),
        "collection": conversation(
            "collection", collection_task,
            [tool("create_promise")] + mentioned("\n".join(ins["collection"] + ins["global"]), [n for n in names if n in ("add_note", "transfer_to_agent", "schedule_callback")]),
        ),
    }
    nodes["wrap_up"] = {
        "name": "wrap_up",
        "node_type": "end_call",
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "transitions": [],
        "terminal": {"type": "function", "function": {
            "name": "turn_limit_reached",
            "handler": "__function__:end_call",
            "parameters": {"type": "object", "properties": {
                "message_mode": {"type": "string", "default": "custom"},
                "spoken_message": {"type": "string", "default": "Thank you for your time. Goodbye."},
            }},
        }},
    }
    # Layout for the dashboard editor only (no effect on the call): main path left to right, third party below.
    for i, key in enumerate(["setup", "opening", "identity", "load_account", "compute", "collection"]):
        nodes[key]["position"] = {"x": i * 420, "y": 0}
    nodes["third_party"]["position"] = {"x": 420, "y": 520}
    nodes["wrap_up"]["position"] = {"x": 2100, "y": 520}
    url, op = ops["close_call"]
    close = tools.api_tool(
        "close_call", url, op,
        "Record how the call ended. Choose the outcome and reason from this table, using the whole conversation:\n" + tools.outcome_table(spec["outcomes"]),
        pre_hook=tools.close_hook(spec["deterministic"], spec["outcomes"]), lifecycle="end_of_call")
    return {
        "initial_node": "setup",
        "system_prompt": system,
        "nodes": nodes,
        "global_nodes": {},
        "tools": [close],
        # No customer_id here: in a chat call a test value was baked into tool bodies instead of the real one.
        "test_variables": {"first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
    }


def summary(workflow: dict) -> tuple[int, int]:
    """(steps, tools) for the trace."""
    nodes = workflow["nodes"].values()
    return len(workflow["nodes"]), sum(len(n.get("tools", [])) + len(n.get("pre_actions", [])) for n in nodes) + len(workflow.get("tools", []))
