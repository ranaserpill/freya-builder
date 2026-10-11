"""kit/tools/run_cases.py with our 5xx retries, so one Freya 503/504 does not kill a test that is still running.

    uv run --env-file .env python -m builder.run_cases_retry <agent_id> --brief A --reps 3 --out out/x.json

Same arguments as run_cases.py. The kit file is not changed: we patch freya.api (deploy._freya) and then run it.
"""
import runpy
import sys
from pathlib import Path

from builder import deploy

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    deploy._freya()                                   # patches freya.api with retries
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    sys.argv = [str(ROOT / "kit" / "tools" / "run_cases.py")] + sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
