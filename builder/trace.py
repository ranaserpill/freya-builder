"""Builder trace: the run record the organisers require (start/end, model calls, Freya objects, self-tests).

Everything goes to stdout so `... | tee traces/<brief>.log` captures it. Secrets are redacted.
"""
import os
import re
import sys
from datetime import datetime, timezone

_SECRET_ENV = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
_KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|fak_[A-Za-z0-9_\-]{8,}|Bearer\s+\S+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _redact(text: str) -> str:
    for name in _SECRET_ENV:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, f"<{name}>")
    return _KEY_PATTERN.sub("<redacted>", text)


def log(kind: str, message: str) -> None:
    print(_redact(f"[{_now()}] {kind:<8} {message}"), flush=True)


def start(brief_path: str, tool_api_path: str) -> None:
    log("START", f"brief={brief_path} tool_api={tool_api_path} python={sys.version.split()[0]}")


def end(ok: bool) -> None:
    log("END", "ok" if ok else "failed")


def model_call(model: str, purpose: str, usage=None) -> None:
    tokens = f" in={usage.input_tokens} out={usage.output_tokens}" if usage else ""
    log("MODEL", f"{model} | {purpose}{tokens}")


def created(workflow_id: str, agent_id: str, steps: int, tools: int) -> None:
    log("FREYA", f"workflow={workflow_id} agent={agent_id} steps={steps} tools={tools}")


def test_result(name: str, passed: int, total: int, detail: str = "") -> None:
    log("TEST", f"{name}: {passed}/{total} {detail}".rstrip())


def step(message: str) -> None:
    log("STEP", message)
