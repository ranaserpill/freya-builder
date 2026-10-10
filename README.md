# freya-builder

Team entry for Freya "Build the Builder" (Oct 10–11, 2026).

```
python3 builder/build.py <brief.md> <openapi.json> 2>&1 | tee traces/<brief>.log
```

- `kit/` – files from the organisers' kit (briefs, tools/openapi.json, docs/, freya.py, run_cases.py)
- `builder/` – our builder
- `traces/` – one log per builder run we submit
- `submission/` – exported workflows (`freya.export_workflow`)

Rules for humans and coding agents: see [AGENTS.md](AGENTS.md).
