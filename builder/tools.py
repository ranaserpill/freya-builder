"""Freya tool objects built from the bank's tool API file (OpenAPI), plus the Python hooks around them.

Every field, enum and description comes from the tool API file. Only the seven tool names are fixed by the
event. Hook sources must not contain double curly braces (the engine templates them); `dbl_safe` guards that.
"""
import json

END_PHRASE = "Have a good day."


def dbl_safe(text: str) -> str:
    out = text.replace("{" + "{", "{ {").replace("}" + "}", "} }")
    assert "{" + "{" not in out and "}" + "}" not in out
    return out


def operations(tool_api: dict) -> dict:
    """tool name -> (url, operation). The name is the last path segment."""
    base = ((tool_api.get("servers") or [{}])[0].get("url") or "").rstrip("/")
    out = {}
    for path, ops in (tool_api.get("paths") or {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        out[path.rstrip("/").split("/")[-1]] = (base + path, op)
    return out


def _body_schema(op: dict) -> dict:
    return (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema", {})


def api_tool(name: str, url: str, op: dict, description: str, post_hook: str = "", pre_hook: str = "", lifecycle: str = "") -> dict:
    schema = _body_schema(op)
    props = {}
    for field, s in (schema.get("properties") or {}).items():
        leaf = {"type": s.get("type", "string")}
        desc = s.get("description", "")
        if s.get("format") == "date":
            desc = (desc + " Format YYYY-MM-DD.").strip()
        if s.get("enum"):
            leaf["enum"] = s["enum"]
            desc = (desc + " One of: " + ", ".join(map(str, s["enum"])) + ".").strip()
        if desc:
            leaf["description"] = desc
        # A call variable of the same name (customer_id) is baked in; any other field is filled by the model.
        leaf["default"] = "{{" + field + "}}"
        props[field] = leaf
    tool = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": 0},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": description,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": url},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props, "required": [r for r in schema.get("required", []) if r != "customer_id"]},
            }},
        },
    }
    if lifecycle:
        tool["config"]["alwaysRunsAt"] = [lifecycle]
    if post_hook:
        tool["post_process_code"] = dbl_safe(post_hook)
    if pre_hook:
        tool["pre_process_code"] = dbl_safe(pre_hook)
    return tool


def end_call_tool() -> dict:
    return {
        "type": "function",
        "config": {"timeoutMs": 10000},
        "function": {
            "name": "end_call",
            "handler": "__function__:end_call",
            "description": f'Ends the call. You normally do NOT call this: the sentence "{END_PHRASE}" ends the call by itself. '
                           "Call it without any text only if the customer speaks again after your goodbye.",
            "parameters": {"type": "object", "properties": {
                "message_mode": {"type": "string", "default": "none"},
                "interruptible": {"type": "boolean", "default": True},
                "trigger_pattern": {"type": "string", "default": END_PHRASE.rstrip(".") + "|" + END_PHRASE.rstrip(".").lower()},
                "trigger_timeout": {"type": "number", "default": 3},
                "trigger_pattern_both": {"type": "string", "default": "goodbye|bye|have a good day|you too|thank you|thanks|take care"},
            }},
        },
    }


# ---- post-hooks: turn a bare result into a sentence the phone agent can act on --------------------------------

# `vars` is not documented for post-hooks: without it the name falls back to Python's builtin vars(), so test
# for a mapping, not for the name. A body that arrives as a JSON string is parsed, not dropped.
_VARS = """    try:
        _v = vars
    except Exception:
        _v = None
    if not (hasattr(_v, 'get') and hasattr(_v, '__setitem__')):
        _v = dict()
"""
_HOOK_HEAD = """try:
    _d = result.get('data') if isinstance(result, dict) else None
    if isinstance(result, dict):
        result.pop('header', None)
    if isinstance(_d, str):
        try:
            import json as _json
            _d = _json.loads(_d)
        except Exception:
            _d = dict(text=_d)
    if not isinstance(_d, dict):
        _d = dict()
    if isinstance(result, dict):
        result['data'] = _d
    _ok = str(_d.get('ok')).lower() == 'true'
    _err = str(_d.get('error') or result.get('message') or 'unknown error') if isinstance(result, dict) else 'unknown error'
""" + _VARS
_HOOK_TAIL = """    _d['what_to_do_next'] = _msg + ' Now say something to the customer or call the next tool. Never stay silent.'
except Exception:
    pass
"""


def _hook(body: str) -> str:
    return _HOOK_HEAD + body + _HOOK_TAIL


VERIFY_HOOK = _hook("""    _left = _d.get('wrong_answers_left')
    if str(_d.get('all_verified')).lower() == 'true':
        _v['fx_identity'] = 'verified'
        _msg = 'All security questions are answered correctly: the identity is VERIFIED. Ask no more security questions.'
    elif not _ok and _d.get('verified') is None:
        _msg = 'The service could not use this answer (' + _err + '). It does NOT count as a wrong answer. Ask for the same answer again in the expected form.'
    elif _d.get('hint'):
        _msg = 'The bank returned the hint ' + repr(_d.get('hint')) + ' for this answer. Follow your instructions for this hint.'
    elif str(_d.get('verified')).lower() == 'true':
        _msg = 'This answer is CORRECT. Ask the next security question now.'
    elif str(_left) == '0':
        _v['fx_identity'] = 'failed'
        _msg = 'This answer is WRONG and no wrong answers are left: the identity check has FAILED. Do not ask again and do not state any debt. Follow your instructions for a failed identity check, then end the call.'
    else:
        _msg = 'This answer is WRONG. Wrong answers left: ' + str(_left) + '. Follow your instructions for a wrong answer.'
""")

GENERIC_HOOK = _hook("""    _msg = 'Done: the bank accepted it.' if _ok else 'FAILED: ' + _err + '. Nothing was recorded. Do not say it was recorded.'
""")

CALLBACK_HOOK = _hook("""    if _ok:
        _v['fx_callback_ok'] = 'yes'
        _msg = 'The callback IS scheduled.'
    else:
        _msg = 'FAILED: ' + _err + '. No callback was scheduled. Do not say it was scheduled.'
""")

TRANSFER_HOOK = _hook("""    if _ok:
        _v['fx_transfer_ok'] = 'yes'
        _q = _v.get('transfer_to_agent_args.queue')
        if _q:
            _v['fx_transfer_queue'] = str(_q)
        _msg = 'The transfer IS done. Tell the customer a colleague will take over, then end the call.'
    else:
        _msg = 'FAILED: ' + _err + '. The transfer did not happen.'
""")


def promise_hook(attempts_max: int) -> str:
    return _hook("""    _f = int(_v.get('fx_promise_fail') or 0)
    if _ok:
        _v['fx_promises_ok'] = str(int(_v.get('fx_promises_ok') or 0) + 1)
        _v['fx_promise_fail'] = '0'
        _msg = 'The promise IS recorded. Only now may you tell the customer it is recorded.'
    elif _f + 1 < MAX_ATTEMPTS:
        _v['fx_promise_fail'] = str(_f + 1)
        _msg = 'FAILED: ' + _err + '. NOTHING was recorded. Do not say it is recorded. Call create_promise again right now with exactly the same values.'
    else:
        _v['fx_promise_fail'] = '0'
        _msg = 'FAILED again: ' + _err + '. NOTHING was recorded and you must not try again for this product. Tell the customer you could not record it and follow your instructions for a promise that could not be recorded.'
""".replace("MAX_ATTEMPTS", str(max(1, int(attempts_max)))))


def close_hook(deterministic: dict, outcomes: list) -> str:
    """Pre-hook of the end-of-call close tool. Where the call's own records decide the outcome, code sets it;
    otherwise the model's choice stays. Reasons the outcome table does not use are dropped."""
    no_reason = sorted({o["outcome"] for o in outcomes} - {o["outcome"] for o in outcomes if o.get("reason")})
    data = json.dumps({"d": deterministic, "no_reason": no_reason})
    return ("""try:
    import json as _json
    _D = _json.loads(DATA)
    _b = config.get('body')
""" + _VARS + """    if isinstance(_b, dict):
        _pick = None
        _q = _v.get('fx_transfer_queue') or _v.get('transfer_to_agent_args.queue')
        if _v.get('fx_transfer_ok') == 'yes' and _q:
            for _t in _D['d'].get('transfers') or []:
                if _t.get('queue') == str(_q):
                    _pick = _t
        elif int(_v.get('fx_promises_ok') or 0) > 0:
            _pick = _D['d'].get('promise_recorded')
        elif _v.get('fx_identity') == 'failed' or (str(_v.get('verify_identity_response.data.wrong_answers_left')) == '0' and str(_v.get('verify_identity_response.data.all_verified')).lower() != 'true'):
            _pick = _D['d'].get('identity_failed')
        elif _v.get('fx_callback_ok') == 'yes':
            _pick = _D['d'].get('callback_scheduled')
        if _pick and _pick.get('outcome'):
            _b['outcome'] = _pick['outcome']
            _b['reason'] = _pick.get('reason') or ''
        _r = str(_b.get('reason') or '')
        if not _r or '{' in _r or _b.get('outcome') in _D['no_reason']:
            _b.pop('reason', None)
except Exception:
    pass
""").replace("DATA", repr(data))


def outcome_table(outcomes: list) -> str:
    return "\n".join(f"- outcome {o['outcome']}" + (f", reason {o['reason']}" if o.get("reason") else ", no reason") + f": {o['when']}" for o in outcomes)
