"""The builder's own model calls (not the phone agent's model). Every call is written to the trace."""
import json
import re

import anthropic

from builder import trace

MODEL = "claude-opus-5-5"

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def ask(purpose: str, system: str, prompt: str, effort: str = "high") -> str:
    """One model call; returns the text. `purpose` is the one-line trace entry."""
    with _get_client().beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
    ) as stream:
        response = stream.get_final_message()
    trace.model_call(response.model, purpose, response.usage)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {purpose}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"model output truncated: {purpose}")
    return "".join(b.text for b in response.content if b.type == "text")


def ask_json(purpose: str, system: str, prompt: str, effort: str = "high"):
    """Like ask(), but the answer must be one JSON value (a fenced block is accepted)."""
    text = ask(purpose, system + "\n\nAnswer with a single JSON value and nothing else.", prompt, effort)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return json.loads(fenced.group(1) if fenced else text)
