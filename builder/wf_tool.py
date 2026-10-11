"""Small CLI the case-building agent calls through Bash. Every Freya call goes through deploy._freya() (5xx retries).

    python -m builder.wf_tool validate <workflow.json>
    python -m builder.wf_tool deploy <name> <workflow.json>          -> prints {"workflow_id", "agent_id", ...}
    python -m builder.wf_tool chat <workflow_id> '<variables json>' "turn 1" "turn 2" ...
    python -m builder.wf_tool call <call_id>                          -> transcript with tool calls and results

The chat command plays the customer's turns in order and prints the agent's replies and the tool calls it made, so the
agent can see whether its workflow behaves. It never edits the workflow on the platform.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builder import deploy  # noqa: E402
from builder.build import load_env  # noqa: E402


def _events(freya, call_id: str) -> list[str]:
    out = []
    for m in freya.get_call(call_id).get("messages", []):
        role = m.get("role")
        if role in ("user", "assistant"):
            out.append(f"{role.upper()}: {m.get('message', '')}")
        elif role == "system":
            try:
                e = json.loads(m.get("message") or "{}")
            except Exception:
                continue
            ev = e.get("event")
            if ev == "node_enter":
                out.append(f"  [step] {e.get('node')}")
            elif ev == "function_call_start":
                args = e.get("args") or {}
                out.append(f"  [tool] {e.get('function')} {json.dumps(args.get('body', args), ensure_ascii=False)[:300]}")
            elif ev == "function_call_complete":
                out.append(f"  [result] {json.dumps(e.get('result'), ensure_ascii=False)[:400]}")
            elif ev in ("error", "function_call_error"):
                out.append(f"  [ERROR] {json.dumps(e, ensure_ascii=False)[:400]}")
    return out


def main(argv: list[str]) -> int:
    load_env(ROOT / ".env")
    freya = deploy._freya()
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "validate":
        wf = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        print(json.dumps(freya.validate_workflow("validate-only", wf), ensure_ascii=False))
    elif cmd == "deploy":
        wf = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        print(json.dumps(deploy.deploy(argv[2], wf)))
    elif cmd == "chat":
        wid, variables, turns = argv[2], json.loads(argv[3]), argv[4:]
        r = freya.api("POST", "/api/v2/chat/message", {"workflowId": wid, "message": turns[0] if turns else "Alo?", "customerVariables": variables})
        cid = r.get("callId")
        print(f"call_id {cid}")
        for t in turns[1:]:
            freya.api("POST", "/api/v2/chat/message", {"callId": cid, "message": t})
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": cid})
        except Exception:
            pass
        print("\n".join(_events(freya, cid)))
    elif cmd == "call":
        print("\n".join(_events(freya, argv[2])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
