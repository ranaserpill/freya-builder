# freya-builder

Team entry for Freya "Build the Builder" (Oct 10–11, 2026).

```
uv run builder/build.py <brief.md> <openapi.json> 2>&1 | tee traces/<brief>.log
```

- `kit/` – files from the organisers' kit (briefs, tools/openapi.json, docs/, freya.py, run_cases.py)
- `builder/` – our builder
- `traces/` – one log per builder run we submit
- `submission/` – exported workflows (`freya.export_workflow`)

## Rerunning our builder (organisers)

1. Install [uv](https://docs.astral.sh/uv/) and run `uv sync` (Python 3.12 and all dependencies; the Claude Agent SDK
   ships its own Claude Code CLI, nothing else to install).
2. `cp .env.example .env`, then set `FREYA_API_KEY`, `FREYA_API_URL`, `FREYA_BANK_TEAM_KEY` and **either**
   `ANTHROPIC_API_KEY` **or** leave it empty and log in once with Claude Code (`uv run python -c "import claude_agent_sdk"`
   is enough to check the install; log in with `claude` → `/login` if you have the CLI). The builder uses the API key
   when it is set, otherwise the login.
3. One command per brief; several brief files (raw material) are read in order, the tool API file comes last:

   ```
   uv run builder/build.py <brief file(s)> <openapi.json> --name <workflow name> 2>&1 | tee traces/<name>.log
   ```

   It extracts the spec, generates the workflow, validates it, creates or updates the workflow **by name** (a rerun
   updates the same one), publishes it, runs one chat turn and exports it to `submission/<name>.workflow.json`.
   The trace on stdout lists start/end, every model call, the Freya workflow/agent ids and the self-test. Typical
   build time: 2–5 minutes.

## Setup (each machine)

1. Install [uv](https://docs.astral.sh/uv/) (it brings Python 3.12 and the deps itself), then `uv sync`.
2. Log in to Claude Code once (`claude`, then `/login`). The builder calls Claude with that login; we have
   no API key, so we leave `ANTHROPIC_API_KEY` empty (an empty value is ignored).
3. `cp .env.example .env` and fill in the Freya key and the shared team key (never commit `.env`).
4. `uv run builder/build.py <brief.md> <openapi.json>`

`builder/trace.py` writes the required trace; `builder/llm.py` is the only place the builder calls a model;
`builder/deploy.py` is the only place it creates or updates a workflow.

Rules for humans and coding agents: see [AGENTS.md](AGENTS.md).
