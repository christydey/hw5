"""Command line entry point.

    python -m backend.run --ticket 101
    python -m backend.run --ticket 103 --agent inventory --task "How short are we on size M?"

Prints the final AgentReport as JSON. Nothing is paid or sent; the report
lists what needs human approval.
"""

import argparse
import asyncio
import sys

from .models import AGENT_NAMES
from .team import run_ticket


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team on one ticket.")
    parser.add_argument("--ticket", type=int, required=True)
    parser.add_argument("--agent", choices=AGENT_NAMES, default="boss", help="entry agent (default: boss)")
    parser.add_argument("--task", help="override the default task text")
    args = parser.parse_args()

    try:
        report = asyncio.run(run_ticket(args.ticket, args.task, args.agent))
    except Exception as exc:
        print(f"Run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("See output/audit_trail.json for the steps recorded before the failure.", file=sys.stderr)
        return 1
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
