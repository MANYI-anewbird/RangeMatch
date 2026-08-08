"""Command-line entry point for deterministic RangeMatch evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .demo_report import write_demo_closure
from .engine import evaluate_land_profile
from .geometry_replace import write_replaced_profile


COMMANDS = {
    "evaluate",
    "demo-closure",
    "replace-geometry",
    "f07-live-gate",
    "f08-data-reuse-gate",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rangematch")
    subparsers = parser.add_subparsers(dest="command")

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Evaluate a Land Profile and print MatchResult JSON"
    )
    evaluate_parser.add_argument("profile", type=Path)
    evaluate_parser.add_argument("--output", type=Path)

    demo_parser = subparsers.add_parser(
        "demo-closure",
        help="Build the demo Factor closure HTML/JSON product surface",
    )
    demo_parser.add_argument("profile", type=Path)
    demo_parser.add_argument("--html-output", type=Path)
    demo_parser.add_argument("--json-output", type=Path)

    replace_parser = subparsers.add_parser(
        "replace-geometry",
        help="Bind a Land Profile to a new geometry and invalidate stale Factor evidence",
    )
    replace_parser.add_argument("profile", type=Path)
    replace_parser.add_argument("geometry", type=Path)
    replace_parser.add_argument("--output", type=Path, required=True)
    replace_parser.add_argument(
        "--geometry-reference",
        type=str,
        help="Optional repository-relative geometry reference to store on the profile",
    )

    f07_parser = subparsers.add_parser(
        "f07-live-gate",
        help="Run CPER F07 live gate against TIGER/Line 2025 All Roads",
    )
    f07_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory for cached TIGER county/roads zip downloads",
    )
    f07_parser.add_argument(
        "--no-write-artifacts",
        action="store_true",
        help="Do not rewrite Land Profile / MatchResult / demo closure fixtures",
    )

    f08_parser = subparsers.add_parser(
        "f08-data-reuse-gate",
        help="Run CPER F08 gate by reusing the existing F02 RAP coverV3 artifact",
    )
    f08_parser.add_argument(
        "--no-write-artifacts",
        action="store_true",
        help="Do not rewrite Land Profile / MatchResult / demo closure fixtures",
    )
    return parser


def _emit_match_result(profile_path: Path, output_path: Path | None) -> None:
    result = evaluate_land_profile(json.loads(profile_path.read_text()))
    rendered = json.dumps(result, indent=2) + "\n"
    if output_path:
        output_path.write_text(rendered)
    else:
        print(rendered, end="")


def _run_legacy(argv: list[str]) -> None:
    """Backward-compatible: python -m rangematch.cli <profile> [--output PATH]."""
    parser = argparse.ArgumentParser(prog="rangematch")
    parser.add_argument("legacy_profile", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    _emit_match_result(args.legacy_profile, args.output)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] not in COMMANDS and argv[0] not in {"-h", "--help"}:
        if not argv[0].startswith("-"):
            _run_legacy(argv)
            return

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo-closure":
        payload = write_demo_closure(
            args.profile,
            html_output=args.html_output,
            json_output=args.json_output,
        )
        print(
            json.dumps(
                {
                    "demo_closure_version": payload["demo_closure_version"],
                    "sections": payload["sections"],
                },
                indent=2,
            )
        )
        return

    if args.command == "replace-geometry":
        replaced = write_replaced_profile(
            args.profile,
            args.geometry,
            args.output,
            geometry_reference=args.geometry_reference,
        )
        print(
            json.dumps(
                {
                    "geometry_id": replaced["geometry_id"],
                    "geometry_hash": replaced["geometry_hash"],
                    "geometry_reference": replaced["geometry_reference"],
                    "factor_evidence_invalidated": replaced["geometry_replacement"][
                        "factor_evidence_invalidated"
                    ],
                },
                indent=2,
            )
        )
        return

    if args.command == "f07-live-gate":
        from .f07_tiger_adapter import run_cper_f07_live_gate

        repo_root = Path(__file__).resolve().parents[2]
        payload = run_cper_f07_live_gate(
            repo_root=repo_root,
            cache_dir=args.cache_dir,
            write_artifacts=not args.no_write_artifacts,
        )
        print(json.dumps(payload["live_gate"], indent=2) + "\n", end="")
        return

    if args.command == "f08-data-reuse-gate":
        from .f08_derivation import run_cper_f08_data_reuse_gate

        repo_root = Path(__file__).resolve().parents[2]
        payload = run_cper_f08_data_reuse_gate(
            repo_root=repo_root,
            write_artifacts=not args.no_write_artifacts,
        )
        print(json.dumps(payload["live_gate"], indent=2) + "\n", end="")
        return

    if args.command == "evaluate":
        _emit_match_result(args.profile, args.output)
        return

    parser.error("profile path is required")


if __name__ == "__main__":
    main()
