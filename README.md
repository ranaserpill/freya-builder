# freya-builder

Team entry for Freya "Build the Builder" (Oct 10–11, 2026).

```
uv run builder/build.py <brief.md> <openapi.json> 2>&1 | tee traces/<brief>.log
```

- `kit/` – files from the organisers' kit (briefs, tools/openapi.json, docs/, freya.py, run_cases.py)
- `builder/` – our builder
- `traces/` – one log per builder run we submit
- `submission/` – exported workflows (`freya.export_workflow`)

## Setup (each machine)

1. Install [uv](https://docs.astral.sh/uv/) (it brings Python 3.12 and the deps itself), then `uv sync`.
2. Log in to Claude Code once (`claude`, then `/login`). The builder calls Claude with that login; we have
   no API key. Leave `ANTHROPIC_API_KEY` empty.
3. `cp .env.example .env` and fill in the Freya key and the shared team key (never commit `.env`).
4. `uv run builder/build.py <brief.md> <openapi.json>`

`builder/trace.py` writes the required trace; `builder/llm.py` is the only place the builder calls a model;
`builder/deploy.py` is the only place it creates or updates a workflow.

Rules for humans and coding agents: see [AGENTS.md](AGENTS.md).
