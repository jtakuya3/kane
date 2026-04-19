"""CLI entrypoint: ``python -m kane`` or ``kane``."""

from __future__ import annotations

import argparse
import logging
import sys

from . import pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily Elon/Anthropic clip+post pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    results = pipeline.run_once()
    logging.getLogger("kane").info("done; produced %d clip(s)", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
