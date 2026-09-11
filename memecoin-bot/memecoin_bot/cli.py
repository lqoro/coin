"""Command line entry point: memecoin-bot rank."""
from __future__ import annotations

import argparse
import sys

from .report import render_json, render_table
from .scoring import rank_callers
from .sources import SourceError, load_callouts, load_outcomes, resolve_outcomes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memecoin-bot",
        description="Rank pump.fun callers by consistency of outcome, not by following.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--callouts",
        help="JSONL of raw callouts; market caps are resolved live from pump.fun.",
    )
    source.add_argument(
        "--outcomes",
        help="JSONL of already-priced callouts (adds peak_mcap_usd / mcap_now_usd).",
    )
    parser.add_argument(
        "--min-calls",
        type=int,
        default=5,
        help="Callers below this many calls are dropped as too small a sample (default: 5).",
    )
    parser.add_argument("--top", type=int, default=0, help="Show only the top N callers.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.outcomes:
            outcomes = load_outcomes(args.outcomes)
        else:
            outcomes = list(resolve_outcomes(load_callouts(args.callouts)))
    except (OSError, SourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not outcomes:
        print("error: no priced callouts to rank", file=sys.stderr)
        return 1

    ranked = rank_callers(outcomes, min_calls=args.min_calls)
    if args.top:
        ranked = ranked[: args.top]

    print(render_json(ranked) if args.json else render_table(ranked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
