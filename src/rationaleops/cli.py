"""Command-line entry points for RationaleOps."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from rationaleops.datahub_gateway import DataHubSdkWriter, load_demo_context
from rationaleops.datahub_mcp import DataHubMcpReader
from rationaleops.full_workflow import run_recorded_full_demo
from rationaleops.mining import mine_decision_points
from rationaleops.models import DecisionContract, MutationApproval
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

    demo_all = subparsers.add_parser(
        "demo-all",
        help="run all three deterministic hero outcomes",
    )
    demo_all.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".rationaleops/full-demo"),
        help="directory for generated evidence and artifacts",
    )
    demo_all.add_argument(
        "--approve-actions",
        action="store_true",
        help="approve all three validated recorded action proposals",
    )
    demo_all.add_argument(
        "--approve-writeback",
        action="store_true",
        help=("approve three recorded fixture writes (never contacts a live DataHub)"),
    )
    demo_all.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        default=date(2026, 7, 23),
        metavar="YYYY-MM-DD",
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

    seed = subparsers.add_parser(
        "seed-datahub",
        help="idempotently seed the 47-asset demo into DataHub OSS",
    )
    seed.add_argument(
        "--server",
        default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
    )
    seed.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))

    inspect_datahub = subparsers.add_parser(
        "inspect-datahub",
        help="read the seeded query, lineage, owner, glossary, and schema via MCP",
    )
    inspect_datahub.add_argument(
        "--server",
        default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
    )
    inspect_datahub.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    inspect_datahub.add_argument(
        "--dataset-urn",
        default=load_demo_context().dataset_urn,
    )

    writeback = subparsers.add_parser(
        "writeback-datahub",
        help="write one explicitly approved, verified contract to DataHub",
    )
    writeback.add_argument(
        "--server",
        default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
    )
    writeback.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    writeback.add_argument(
        "--approve-contract",
        required=True,
        choices=(
            "decision-active-window-v1",
            "decision-germany-hold-v1",
            "decision-active-status-v1",
        ),
        help="exact Decision Contract receiving this one mutation",
    )
    writeback.add_argument(
        "--approved-by",
        required=True,
        help="authorized DataHub user URN approving this mutation",
    )
    writeback.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".rationaleops/live-writeback"),
    )
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
    print(f"Recorded write-back visible: {summary['datahub_write_back_visible']}")
    print(f"Artifacts: {args.output_dir.resolve()}")
    return 0


def _run_demo_all(args: argparse.Namespace) -> int:
    summary = run_recorded_full_demo(
        output_dir=args.output_dir,
        approve_actions=args.approve_actions,
        approve_writeback=args.approve_writeback,
        as_of_date=args.as_of_date,
    )
    print("RationaleOps complete recorded demo finished")
    print(f"Decision points found: {summary['decision_points_found']}")
    print("Outcomes: " + ", ".join(summary["outcomes"]))
    print(f"Active-window test passes: {summary['generated_test_passes']}")
    print(f"Germany-removal patch passes: {summary['expired_workaround_patch_passes']}")
    print(f"Documentation update valid: {summary['documentation_update_valid']}")
    print(f"Recorded write-backs visible: {summary['datahub_write_back_visible']}")
    print(f"Artifacts: {args.output_dir.resolve()}")
    return 0


def _run_mine(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.sql_file:
        if not args.query_urn or not args.dataset_urn:
            parser.error("--query-urn and --dataset-urn are required with --sql-file")
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


def _run_seed_datahub(args: argparse.Namespace) -> int:
    from rationaleops.datahub_seed import DataHubDemoSeeder

    result = DataHubDemoSeeder(server=args.server, token=args.token).seed()
    print(json.dumps(result, indent=2))
    return 0


def _run_inspect_datahub(args: argparse.Namespace) -> int:
    context = asyncio.run(
        DataHubMcpReader(server=args.server, token=args.token).get_query_context(
            args.dataset_urn
        )
    )
    print(context.model_dump_json(indent=2))
    return 0


def _run_writeback_datahub(args: argparse.Namespace) -> int:
    run_recorded_full_demo(
        output_dir=args.output_dir,
        approve_actions=False,
        approve_writeback=False,
    )
    contract_path = args.output_dir / "contracts" / f"{args.approve_contract}.json"
    contract = DecisionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if args.approved_by not in contract.authority.authorized_confirmers:
        raise ValueError("--approved-by is not an authorized confirmer")
    approved_at = max(
        value
        for value in (
            datetime.now(UTC),
            contract.authority.confirmed_at,
            contract.verification.checked_at,
        )
        if value is not None
    )
    receipt = DataHubSdkWriter(
        server=args.server,
        token=args.token,
    ).write_contract(
        contract,
        MutationApproval(
            contract_id=contract.id,
            approved_by=args.approved_by,
            approved_at=approved_at,
        ),
    )
    print(receipt.model_dump_json(indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "demo-all":
        return _run_demo_all(args)
    if args.command == "mine":
        return _run_mine(args, parser)
    if args.command == "seed-datahub":
        return _run_seed_datahub(args)
    if args.command == "inspect-datahub":
        return _run_inspect_datahub(args)
    if args.command == "writeback-datahub":
        return _run_writeback_datahub(args)
    parser.error(f"unknown command: {args.command}")
    return 2
