"""Create or update a Freya workflow by its name.

The team shares one Freya workspace from several machines. kit/freya.py's save_workflow() remembers workflow ids
in a local file, so two machines using the same slot would each create their own workflow. Here the platform is
the source of truth: we look the name up in the workspace and update that workflow, or create it once.

Names: `dev-<person>` while developing, `submission-<brief>` for the final run (see AGENTS.md).

NOTE: the list route's result shape is not documented in the kit; it is read defensively below.
Check it against the real API once we have a key.
"""
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "kit"


def _freya():
    # Imported lazily: freya.py reads FREYA_API_KEY when it is imported, so .env must be loaded first.
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))
    import freya
    return freya


def _items(result) -> list:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("workflows", "items", "data"):
            if isinstance(result.get(key), list):
                return result[key]
    return []


def find(name: str) -> dict | None:
    """The workflow called `name` in our workspace, or None."""
    freya = _freya()
    found = [w for w in _items(freya.api("GET", "/api/v2/workflow", workspaceId=freya.workspace_id())) if w.get("name") == name]
    if len(found) > 1:
        raise RuntimeError(f"{len(found)} workflows are named {name!r}; delete the extras in the dashboard")
    return found[0] if found else None


def deploy(name: str, workflow: dict) -> dict:
    """Update the workflow called `name` and publish it, or create it. Returns workflow_id, agent_id, version, created."""
    freya = _freya()
    existing = find(name)
    if existing is None:
        return {**freya.create_workflow(name, workflow), "version": 1, "created": True}
    workflow_id = existing["id"]
    version = freya.update_workflow(workflow_id, workflow)
    agent_id = existing.get("agentId") or freya.api("GET", f"/api/v2/workflow/{workflow_id}", workspaceId=freya.workspace_id())["workflow"]["agentId"]
    return {"workflow_id": workflow_id, "agent_id": agent_id, "version": version, "created": False}
