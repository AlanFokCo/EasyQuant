"""Run eqlib's dependency evaluator and write machine-readable evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from evaluator.runner import run_evaluation  # noqa: E402


def main() -> int:
    """Parse CLI arguments and return the evaluator policy exit code."""
    parser = argparse.ArgumentParser(description="Audit eqlib dependency contracts")
    parser.add_argument("--profile", choices=("offline", "live"), default="offline")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/eqlib-evaluator")
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    _, exit_code = run_evaluation(Path.cwd(), args.profile, args.output, args.strict)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
