# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""CLI entry point: ``python -m qnet.agent`` (DESIGN.md §5, §6).

T0.4 wires up the argument surface only; ``--help`` is fully functional and the
run path lands with the agent skeleton in T1.3.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_CONFIG = "config/house.yaml"


def build_parser() -> argparse.ArgumentParser:
    """The agent's command line. Kept here so tests and T1.3 share one surface."""
    parser = argparse.ArgumentParser(
        prog="python -m qnet.agent",
        description=(
            "QNet Home agent - the brain. Subscribes to the MQTT fabric "
            "(contracts/mqtt.md), runs skills on engine-enforced rails."
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help=f"house config to load (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="walk the phases on their timers with canned openings and regex "
        "exit matching - no model in the loop (the G2 fallback build)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and start the agent. Running is a T1.3 stub."""
    args = build_parser().parse_args(argv)
    print(
        f"qnet.agent: stub (T0.4) - config={args.config} no_llm={args.no_llm}",
        file=sys.stderr,
    )
    print("The agent loop is not implemented yet; it lands in T1.3.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
