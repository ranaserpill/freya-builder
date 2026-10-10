"""Builder entry point: brief(s) + tool API in, phone agent on Freya out.

    uv run builder/build.py <brief.md> [<more brief files> ...] <openapi.json> [--name NAME] [--test A|B] [--reps N]

Several brief files are read in order as one specification (later ones may change earlier ones).
--name   workflow name in the shared workspace (default: $DEV_WORKFLOW_NAME-<brief>, or submission-<brief>)
--test   also run the kit's practice cases for that brief (practice only; the hidden briefs have none)

Pipeline:
  1. read inputs
  2. spec.py      extract a structured spec from the brief (two model calls in parallel)
  3. generate.py  build the Freya workflow JSON from spec + tool API
  4. deploy.py    validate (dry run), then create or update the workflow by name, and publish it
  5. self-test    one chat turn to prove the agent starts; optionally the practice cases
  6. export the workflow to submission/<name>.workflow.json
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builder import trace  # noqa: E402


def load_env(path: Path) -> None:
    """Minimal .env loader (no dependency); existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():  # an empty ANTHROPIC_API_KEY= would override the Claude Code login
                os.environ.setdefault(key.strip(), value.strip())


def smoke_chat(freya, workflow_id: str, variables: dict) -> str:
    """Start a chat call and send one turn. Returns what the agent said. Raises if the workflow cannot start."""
    r = freya.api("POST", "/api/v2/chat/message", {"workflowId": workflow_id, "message": "Hello?", "customerVariables": variables})
    try:
        freya.api("POST", "/api/v2/chat/end", {"callId": r.get("callId")})
    except Exception:
        pass
    return str(r.get("response") or "")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="brief file(s), then the tool API file")
    ap.add_argument("--name")
    ap.add_argument("--test", choices=["A", "B"])
    ap.add_argument("--reps", type=int, default=1)
    a = ap.parse_args(argv[1:])
    if len(a.files) < 2:
        ap.error("give at least one brief file and the tool API file")
    *brief_paths, tool_api_path = a.files
    load_env(ROOT / ".env")
    slot = Path(brief_paths[-1]).stem
    dev = os.environ.get("DEV_WORKFLOW_NAME")
    name = a.name or (f"{dev}-{slot}" if dev else f"submission-{slot}")

    trace.start(" ".join(brief_paths), tool_api_path)
    trace.step(f"workflow name: {name}")
    ok, t0 = False, time.time()
    try:
        from builder import deploy, generate, spec
        briefs = [Path(p).read_text(encoding="utf-8") for p in brief_paths]
        tool_api_text = Path(tool_api_path).read_text(encoding="utf-8")
        tool_api = json.loads(tool_api_text)
        trace.step(f"read {len(briefs)} brief file(s) ({sum(map(len, briefs))} chars) and tool API ({len(tool_api.get('paths', {}))} tools)")

        s = spec.extract(briefs, tool_api_text)
        out = ROOT / "out"
        out.mkdir(exist_ok=True)
        (out / f"{name}.spec.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
        trace.step(f"spec: {len(s['identity_questions'])} identity questions, {len(s['bands'])} bands, {len(s['holidays'])} holidays, "
                   f"{len(s['outcomes'])} outcomes, {sum(len(v) for v in s['instructions'].values())} instructions")

        workflow = generate.build(s, tool_api)
        (out / f"{name}.workflow.json").write_text(json.dumps(workflow, indent=1, ensure_ascii=False), encoding="utf-8")
        steps, n_tools = generate.summary(workflow)
        trace.step(f"generated workflow: {steps} steps, {n_tools} tool slots")

        freya = deploy._freya()
        freya.validate_workflow(name, workflow)
        trace.step("dry-run validation passed")
        made = deploy.deploy(name, workflow)
        trace.created(made["workflow_id"], made["agent_id"], steps, n_tools)
        trace.step(f"{'created' if made['created'] else 'updated'} and published version {made['version']}")

        said = smoke_chat(freya, made["workflow_id"], workflow["test_variables"])
        trace.test_result("chat smoke test (agent speaks)", int(bool(said)), 1, repr(said[:160]))

        if a.test:
            cmd = [sys.executable, str(ROOT / "kit" / "tools" / "run_cases.py"), made["agent_id"], "--brief", a.test, "--reps", str(a.reps),
                   "--out", str(out / f"{name}.cases.json")]
            trace.step("practice cases: " + " ".join(cmd[1:]))
            run = subprocess.run(cmd, cwd=ROOT / "kit", capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            for line in (run.stdout + run.stderr).splitlines():
                trace.log("CASES", line)
            try:
                r = json.loads((out / f"{name}.cases.json").read_text(encoding="utf-8"))
                trace.test_result(f"practice cases brief {a.test} x{a.reps}", r["passed"], r["total"])
            except Exception as e:
                trace.log("CASES", f"no result file: {e}")

        sub = ROOT / "submission"
        sub.mkdir(exist_ok=True)
        path = freya.export_workflow(made["workflow_id"], str(sub / f"{name}.workflow.json"))
        trace.step(f"exported to {Path(path).relative_to(ROOT)}")
        ok = True
    except Exception as exc:
        trace.log("ERROR", f"{type(exc).__name__}: {exc}")
    finally:
        trace.step(f"build time {time.time() - t0:.0f} s")
        trace.end(ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
