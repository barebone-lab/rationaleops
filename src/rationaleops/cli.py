"""Command-line entry points for RationaleOps."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from rationaleops.datahub_gateway import load_demo_context
from rationaleops.mining import mine_decision_points
from rationaleops.workflow import run_recorded_vertical_slice


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rationaleops",
        description="Preserve the authorized why behind hidden data logic.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser(
        "demo",
        help="run the deterministic 37-day vertical slice",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".rationaleops/demo"),
        help="directory for generated evidence and artifacts",
    )
    demo.add_argument(
        "--approve-writeback",
        action="store_true",
        help=(
            "explicitly approve the recorded fixture write-back "
            "(never contacts a live DataHub)"
        ),
    )
    demo.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        default=date(2026, 7, 23),
        metavar="YYYY-MM-DD",
    )

    mine = subparsers.add_parser(
        "mine",
        help="show deterministic decision points in the bundled SQL",
    )
    mine.add_argument(
        "--sql-file",
        type=Path,
        help="optional SQL file; defaults to the bundled demo query",
    )
    mine.add_argument(
        "--query-urn",
        help="required with --sql-file",
    )
    mine.add_argument(
        "--dataset-urn",
        help="required with --sql-file",
    )
    mine.add_argument("--dialect", default="postgres")
    return parser


def _run_demo(args: argparse.Namespace) -> int:
    summary = run_recorded_vertical_slice(
        output_dir=args.output_dir,
        approve_writeback=args.approve_writeback,
        as_of_date=args.as_of_date,
    )
    print("RationaleOps recorded vertical slice complete")
    print(f"Decision points found: {summary['decision_points_found']}")
    print(f"Selected risk score: {summary['knowledge_risk']['total']:.4f}")
    print(f"Contract status: {summary['contract_status']}")
    print(f"Generated SQL test passes: {summary['generated_test_passes']}")
    print(
        "Recorded write-back visible: "
        f"{summary['datahub_write_back_visible']}"
    )
    print(f"Artifacts: {args.output_dir.resolve()}")
    return 0


def _run_mine(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.sql_file:
        if not args.query_urn or not args.dataset_urn:
            parser.error(
                "--query-urn and --dataset-urn are required with --sql-file"
            )
        sql = args.sql_file.read_text(encoding="utf-8")
        query_urn = args.query_urn
        dataset_urn = args.dataset_urn
        dialect = args.dialect
    else:
        context = load_demo_context()
        sql = context.sql
        query_urn = context.query_urn
        dataset_urn = context.dataset_urn
        dialect = context.dialect

    points = mine_decision_points(
        sql,
        query_urn=query_urn,
        dataset_urn=dataset_urn,
        dialect=dialect,
    )
    print(
        json.dumps(
            [point.model_dump(mode="json") for point in points],
            indent=2,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "mine":
        return _run_mine(args, parser)
    parser.error(f"unknown command: {args.command}")
    return 2
