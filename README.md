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

1. Install [uv](https://docs.astral.sh/uv/) (it brings Python 3.12 and the deps itself).
2. `cp .env.example .env` and fill in the keys (never commit `.env`).
3. `uv run builder/build.py <brief.md> <openapi.json>`

`builder/trace.py` writes the required trace; `builder/llm.py` is the only place the builder calls a model.

Rules for humans and coding agents: see [AGENTS.md](AGENTS.md).
