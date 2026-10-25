from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import AVAILABLE_SOURCES, search_literature, search_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Search open literature sources without API keys.")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--plan", type=Path, help="Path to a SearchPlan JSON file.")
    parser.add_argument("--sources", nargs="+", choices=AVAILABLE_SOURCES, default=list(AVAILABLE_SOURCES))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = search_plan(plan, args.timeout)
    elif args.query:
        result = search_literature(args.query, args.sources, args.limit, args.start_year, args.end_year, args.timeout)
    else:
        parser.error("provide either query or --plan")
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
