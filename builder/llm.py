"""The builder's own model calls (not the phone agent's model). Every call is written to the trace.

Claude is called through the Claude Agent SDK, so no API key is needed: it uses the Claude Code login on the
machine (run `claude` once and log in). If ANTHROPIC_API_KEY is set, the SDK uses that instead, so the organisers
can rerun the builder with their own key.

The model gets no tools and does not load this repo's CLAUDE.md/AGENTS.md: one prompt in, one answer out.
`ask_async` / `ask_json_async` let independent calls run in parallel (build time is a tie-break).
"""
import asyncio
import json
import os
import re
import tempfile

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

from builder import trace

MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
# An empty working dir, so the CLI does not pick up project files or settings.
_CWD = tempfile.mkdtemp(prefix="freya-builder-llm-")


def _options(system: str, effort: str, schema: dict | None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system,
        tools=[],                 # pure text generation: no Read/Bash/Web
        allowed_tools=[],
        setting_sources=[],       # ignore user/project settings and CLAUDE.md
        cwd=_CWD,
        effort=effort,
        thinking={"type": "adaptive"},
        max_turns=3,              # structured output may need a retry turn
        output_format={"type": "json_schema", "schema": schema} if schema else None,
    )


async def _run(purpose: str, system: str, prompt: str, effort: str, schema: dict | None):
    texts, result, model = [], None, MODEL
    async for message in query(prompt=prompt, options=_options(system, effort, schema)):
        if isinstance(message, AssistantMessage):
            model = message.model or model
            texts += [b.text for b in message.content if isinstance(b, TextBlock)]
        elif isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise RuntimeError(f"no result from model: {purpose}")
    trace.model_call(model, purpose, result.usage, result.total_cost_usd, result.duration_ms)
    if result.is_error:
        raise RuntimeError(f"model call failed ({result.subtype}): {purpose}: {result.errors or result.result}")
    return result, "".join(texts) or (result.result or "")


async def ask_async(purpose: str, system: str, prompt: str, effort: str = "high") -> str:
    """One model call; returns the text. `purpose` is the one-line trace entry."""
    _, text = await _run(purpose, system, prompt, effort, None)
    return text


async def ask_json_async(purpose: str, system: str, prompt: str, effort: str = "high", schema: dict | None = None):
    """Like ask_async(), but returns one parsed JSON value. With `schema`, the SDK enforces it."""
    if schema:
        result, text = await _run(purpose, system, prompt, effort, schema)
        if result.structured_output is not None:
            return result.structured_output
    else:
        text = await ask_async(purpose, system + "\n\nAnswer with a single JSON value and nothing else.", prompt, effort)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return json.loads(fenced.group(1) if fenced else text)


def ask(purpose: str, system: str, prompt: str, effort: str = "high") -> str:
    return asyncio.run(ask_async(purpose, system, prompt, effort))


def ask_json(purpose: str, system: str, prompt: str, effort: str = "high", schema: dict | None = None):
    return asyncio.run(ask_json_async(purpose, system, prompt, effort, schema))
