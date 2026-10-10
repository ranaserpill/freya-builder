# Freya workflow JSON — what we know before the kit arrives

Source: a screenshot of another team's Freya workspace ("Freya Bank Collections Base (2 nodes)",
JSON Workflow Editor). Unverified — replace with the kit's `docs/` once we have it.

- Top level: `nodes` (object keyed by node name), `global_nodes`, `system_prompt`, `test_variables`
  (e.g. `"now": "2026-10-14T11:00"`).
- Example base workflow has 2 nodes: `identity` → `collection`.
- Each node: ENTRY message, DIALOGUE PROMPTS, `tools` list, `pre_actions`, `transitions`.
  - `identity` tools: `verify_identity`, `end_call`.
  - `collection` tools: `get_account`, `create_promise`, `end_call`.
- Transitions carry a condition; the editor shows one like "both security answers ..." built as an OR
  over `verify_identity` results.
- Built-in `end_call` tool has params such as `trigger_timeout` (number, default 3) and
  `trigger_pattern_both` (string, e.g. "goodbye|bye|have a good day|..."); tool `config.timeoutMs` 10000.
- UI also has: Variables (29), Global Prompt, Global Tools, Global Nodes, Checks, Simulation (beta),
  versioned drafts (v3 Draft) with Save Changes.
