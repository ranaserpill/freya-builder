"""Builder for a case folder: Claude (Agent SDK, Claude Code login) reads the client's raw material, writes the Freya
workflow with our rules (builder/case_skill.md), deploys and chat-tests it, fixes it; then this script deploys the
final file, runs a smoke chat and exports it.

    uv run builder/build_case.py <case_folder> --mock-url https://<mock>.workers.dev [--name final] [--minutes 40]

Outputs: submission/<name>.workflow.json, traces/<name>.log (our trace), traces/<name>.session.jsonl (the agent's
session log, which the organisers ask for when the builder runs a coding agent). Nothing case-specific lives here.
"""
import argparse
import asyncio
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builder import trace  # noqa: E402
from builder.build import load_env  # noqa: E402


async def run_agent(case: Path, out: Path, name: str, mock_url: str, minutes: int, session_log: Path) -> str:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query
    skill = (ROOT / "builder" / "case_skill.md").read_text(encoding="utf-8")
    prompt = (f"Case folder: {case}\nOutput folder: {out}\nWorkflow name to deploy under: {name}\n"
              f"Mock base URL for every tool: {mock_url}\nTime budget: {minutes} minutes from now "
              f"(started {time.strftime('%H:%M:%S')}). Use `date` to check the time.\n\nFollow the instructions.")
    options = ClaudeAgentOptions(
        cwd=str(ROOT),
        add_dirs=[str(case)],
        model=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"),
        system_prompt=skill,
        setting_sources=[],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        permission_mode="dontAsk",
        max_turns=200,
        env={"BASH_DEFAULT_TIMEOUT_MS": "300000", "BASH_MAX_TIMEOUT_MS": "600000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
    last = ""
    with session_log.open("w", encoding="utf-8") as log:
        async for message in query(prompt=prompt, options=options):
            log.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": type(message).__name__,
                                  **dataclasses.asdict(message)}, default=str, ensure_ascii=False) + "\n")
            log.flush()
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        last = block.text
                        trace.log("AGENT", block.text.strip().replace("\n", " ")[:300])
                    elif isinstance(block, ToolUseBlock):
                        trace.log("AGENT", f"[{block.name}] {json.dumps(block.input, ensure_ascii=False)[:200]}")
            elif isinstance(message, ResultMessage):
                trace.model_call(options.model, f"case builder agent: {message.num_turns} turns", message.usage,
                                 message.total_cost_usd, message.duration_ms)
    return last


SECRET_HEADER_HINTS = ("authorization", "token", "secret", "api-key", "apikey", "x-api", "cookie", "password")


def strip_secret_headers(node) -> list[str]:
    """Remove credential headers from every tool. Freya redacts them on export, and a workflow with a redacted value
    cannot be imported again (WORKFLOW_SECRET_REDACTED), so the organisers could not load our export. Returns paths."""
    removed = []

    def walk(x, path):
        if isinstance(x, dict):
            headers = x.get("headers")
            props = headers.get("properties") if isinstance(headers, dict) else None
            if isinstance(props, dict):
                for h in [h for h in props if any(s in h.lower() for s in SECRET_HEADER_HINTS)]:
                    props.pop(h)
                    removed.append(f"{path}.headers.{h}")
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(node, "workflow")
    return removed


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case")
    ap.add_argument("--mock-url", default=os.environ.get("MOCK_URL", ""))
    ap.add_argument("--name", default="final")
    ap.add_argument("--minutes", type=int, default=40)
    a = ap.parse_args(argv[1:])
    load_env(ROOT / ".env")
    a.mock_url = a.mock_url or os.environ.get("MOCK_URL", "")
    if not a.mock_url:
        ap.error("give --mock-url (or MOCK_URL in .env): the tools must call the mock")
    case, out = Path(a.case).resolve(), ROOT / "out" / a.name
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "traces").mkdir(exist_ok=True)
    session_log = ROOT / "traces" / f"{a.name}.session.jsonl"
    trace.start(str(case), a.mock_url)
    trace.step(f"workflow name: {a.name}; case files: {sum(1 for p in case.rglob('*') if p.is_file())}")
    ok, t0 = False, time.time()
    try:
        summary = asyncio.run(run_agent(case, out, a.name, a.mock_url.rstrip("/"), a.minutes, session_log))
        trace.step("agent summary: " + summary.replace("\n", " ")[:1500])
        wf_path = out / "workflow.json"
        workflow = json.loads(wf_path.read_text(encoding="utf-8"))
        workflow.pop("agent_config", None)
        removed = strip_secret_headers(workflow)
        if removed:
            trace.step(f"removed {len(removed)} credential header(s) (Freya redacts them on export; the export would not import): "
                       + ", ".join(sorted({r.rsplit('.', 1)[-1] for r in removed})))
        from builder import deploy
        freya = deploy._freya()
        freya.validate_workflow(f"{a.name}-dryrun-{time.strftime('%H%M%S')}", workflow)
        trace.step("dry-run validation passed")
        made = deploy.deploy(a.name, workflow)
        n_tools = sum(len(n.get("tools", [])) + len(n.get("pre_actions", [])) for n in workflow["nodes"].values()) + len(workflow.get("tools", []))
        trace.created(made["workflow_id"], made["agent_id"], len(workflow["nodes"]), n_tools)
        try:
            r = freya.api("POST", "/api/v2/chat/message", {"workflowId": made["workflow_id"], "message": "Alo?",
                                                            "customerVariables": workflow.get("test_variables", {})})
            trace.test_result("chat smoke test (agent speaks)", int(bool(r.get("response"))), 1, repr(str(r.get("response"))[:160]))
        except Exception as exc:
            trace.test_result("chat smoke test (agent speaks)", 0, 1, f"Freya chat failed: {str(exc)[:160]}")
        sub = ROOT / "submission"
        sub.mkdir(exist_ok=True)
        path = freya.export_workflow(made["workflow_id"], str(sub / f"{a.name}.workflow.json"))
        trace.step(f"exported to {Path(path).relative_to(ROOT)}; agent session log: {session_log.relative_to(ROOT)}")
        ok = True
    except Exception as exc:
        trace.log("ERROR", f"{type(exc).__name__}: {exc}")
    finally:
        trace.step(f"build time {time.time() - t0:.0f} s")
        trace.end(ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
