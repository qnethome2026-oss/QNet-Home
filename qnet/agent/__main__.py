# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""CLI entry point: ``python -m qnet.agent --config config/house.yaml`` (§5, §6).

Everything tunable comes from the house config; the only flags are which config
to read, where the broker is, and whether the model is in the loop.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import yaml

from qnet.agent import engine

DEFAULT_CONFIG = "config/house.yaml"


def build_parser() -> argparse.ArgumentParser:
    """The agent's command line. Kept here so tests and the engine share one surface."""
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
    parser.add_argument(
        "--broker",
        default=None,
        metavar="HOST",
        help=f"broker host, overriding the config's mqtt.host (default: {engine.DEFAULT_BROKER})",
    )
    parser.add_argument("--port", type=int, default=None, help=f"broker port (default: {engine.DEFAULT_PORT})")
    parser.add_argument(
        "--timer-scale",
        type=float,
        default=None,
        metavar="X",
        help="multiply every phase timer and the comfort interval by X, overriding "
        "the config's dev.timer_scale - 0.05 turns the 30 s/15 s fall ladder into "
        "1.5 s/0.75 s so a whole incident replays in seconds (default: 1.0)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Load the house config and serve until Ctrl-C."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        with open(args.config, encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
    except OSError as exc:
        print(f"qnet.agent: cannot read {args.config}: {exc}", file=sys.stderr)
        return 2

    if args.timer_scale is not None:
        config.setdefault("dev", {})["timer_scale"] = args.timer_scale

    # aiomqtt drives paho through the loop's reader callbacks, which the Windows
    # proactor loop does not implement - the selector loop does.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        return asyncio.run(engine.run(config, use_llm=not args.no_llm, broker=args.broker, port=args.port))
    except KeyboardInterrupt:
        print("qnet.agent: stopped", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
