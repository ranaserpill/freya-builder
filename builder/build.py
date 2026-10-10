"""Builder entry point: brief + tool API in, phone agent on Freya out.

    uv run builder/build.py <brief.md> <openapi.json>

Pipeline:
  1. read inputs
  2. extract a structured spec from the brief (LLM)        -> spec.py   (TODO)
  3. generate the Freya workflow JSON from spec + tool API -> generate.py (TODO, needs kit docs/)
  4. create/update the workflow on Freya                   -> kit/freya.py
  5. self-test against practice cases, repair, redeploy    -> selftest.py (TODO, needs kit tools/run_cases.py)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builder import trace  # noqa: E402


def load_env(path: Path) -> None:
    """Minimal .env loader (no dependency); existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    brief_path, tool_api_path = argv[1], argv[2]
    load_env(Path(__file__).resolve().parent.parent / ".env")

    trace.start(brief_path, tool_api_path)
    ok = False
    try:
        brief = Path(brief_path).read_text()
        tool_api = Path(tool_api_path).read_text()
        trace.step(f"read brief ({len(brief)} chars) and tool API ({len(tool_api)} chars)")

        raise NotImplementedError("spec extraction / workflow generation not written yet")
    except NotImplementedError as exc:
        trace.log("TODO", str(exc))
    finally:
        trace.end(ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
