"""Offline checks of a generated workflow: no Freya call, no credit.

    uv run python -m builder.test_generate                       # every spec in out/ and tests/out/
    uv run python -m builder.test_generate tests/out/rules-c.spec.json tests/briefs/rules-c.openapi.json

For each spec: build the workflow, then check that routes point at real steps, tool enums equal the tool API,
the code step compiles and runs on synthetic accounts without error, hooks compile, and prompts reference only
variables that exist at run time.
"""
import json
import re
import sys
from pathlib import Path

from builder import generate, tools

ROOT = Path(__file__).resolve().parent.parent
CALL_VARS = {"customer_id", "first_name", "last_name", "title", "now"}


def synthetic_products(spec: dict, tool_api: dict) -> list[dict]:
    """One product per product type, with every numeric account field filled."""
    from builder.spec import _account_item
    fields = _account_item(tool_api)
    out = []
    for i, t in enumerate(spec["product_types"]):
        p = {"product_id": f"p{i + 1}", "type": t["type"]}
        for name, s in fields.items():
            if name in p:
                continue
            p[name] = {"number": 123.45, "integer": 3 + 9 * i}.get(s.get("type"), "4821")
        out.append(p)
    return out


def check(spec: dict, tool_api: dict) -> list[str]:
    bad = []
    wf = generate.build(spec, tool_api)
    nodes = wf["nodes"]
    if wf["initial_node"] not in nodes:
        bad.append("initial_node missing")
    for name, n in nodes.items():
        for t in n.get("transitions", []):
            if t["target_node"] not in nodes:
                bad.append(f"{name}: route to unknown step {t['target_node']}")
        if n.get("passthrough") and n.get("passthrough_default_transition") not in nodes:
            bad.append(f"{name}: passthrough target missing")
    ops = tools.operations(tool_api)
    seen = set()
    for n in list(nodes.values()) + [{"tools": wf.get("tools", [])}]:
        for t in n.get("tools", []) + n.get("pre_actions", []):
            fn = t["function"]
            seen.add(fn["name"])
            for hook in ("pre_process_code", "post_process_code"):
                if t.get(hook):
                    try:
                        compile(t[hook], f"{fn['name']}.{hook}", "exec")
                    except SyntaxError as e:
                        bad.append(f"{fn['name']} {hook} does not compile: {e}")
            if fn["name"] in ops:
                api_props = tools._body_schema(ops[fn["name"]][1]).get("properties", {})
                body = fn["parameters"]["properties"]["body"]["properties"]
                for field, s in api_props.items():
                    if field not in body:
                        bad.append(f"{fn['name']}: field {field} missing")
                    elif s.get("enum") and body[field].get("enum") != s["enum"]:
                        bad.append(f"{fn['name']}.{field}: enum differs from tool API")
    for must in ("verify_identity", "get_account", "create_promise", "close_call"):
        if must not in seen:
            bad.append(f"tool {must} not used anywhere")
    # the code step: compile, then run it as the sandbox would, before and after the account is loaded
    src = nodes["setup"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
    code = compile(src, "code_step", "exec")
    for products in ([], synthetic_products(spec, tool_api)):
        v = {"now": "2026-10-14T11:00", "customer_id": "c_x", "fx_products_raw": json.dumps(products)}
        exec(code, {"vars": v, "__name__": "code_step"})
        if v.get("fx_error"):
            bad.append(f"code step error: {v['fx_error']}")
        if products and v.get("fx_account_state") != "ok":
            bad.append("code step did not read the products")
        if products and "unknown" in v.get("fx_account_facts", ""):
            bad.append("a product got no band or deadline: " + v["fx_account_facts"][:200])
    produced = set(v)
    # variables named in prompts must exist: call variables, code-step outputs, or tool result keys
    text = wf["system_prompt"] + "".join(n.get("task_message", "") + json.dumps(n.get("on_enter", {})) for n in nodes.values())
    for var in sorted(set(re.findall(r"\{\{\s*([^}\s]+)\s*\}\}", text))):
        if var not in CALL_VARS and var not in produced:
            bad.append(f"prompt uses {{{{{var}}}}} which nothing sets")
    return bad


def main(argv: list[str]) -> int:
    pairs = []
    if len(argv) == 3:
        pairs = [(Path(argv[1]), Path(argv[2]))]
    else:
        for f in sorted((ROOT / "out").glob("*.spec.json")):
            pairs.append((f, ROOT / "kit" / "tools" / "openapi.json"))
        for f in sorted((ROOT / "tests" / "out").glob("*.spec.json")):
            api = ROOT / "tests" / "briefs" / f.name.replace(".spec.json", ".openapi.json")
            pairs.append((f, api))
    total = 0
    for spec_path, api_path in pairs:
        bad = check(json.loads(spec_path.read_text(encoding="utf-8")), json.loads(api_path.read_text(encoding="utf-8")))
        total += len(bad)
        print(("OK  " if not bad else "FAIL") + f" {spec_path.relative_to(ROOT)}")
        for b in bad:
            print("     -", b)
    if not pairs:
        print("no spec files found")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
