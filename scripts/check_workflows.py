"""Static checks for GitHub Actions workflow hygiene.

This script intentionally avoids third-party dependencies so it can run in
local development and CI before actionlint is available.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

DEPRECATED_ACTIONS = {
    "actions/checkout@v4": "Use actions/checkout@v7 or newer.",
    "actions/setup-python@v5": "Use actions/setup-python@v6 or newer.",
    "actions/setup-node@v4": "Use actions/setup-node@v6 or newer.",
    "conda-incubator/setup-miniconda@v3": (
        "Use conda-incubator/setup-miniconda@v4 or newer."
    ),
}


def _line_no(text: str, needle: str) -> int:
    return text[: text.index(needle)].count("\n") + 1


def _check_file(path: Path) -> list[str]:
    text = path.read_text()
    rel = path.relative_to(ROOT)
    failures: list[str] = []

    for action, hint in DEPRECATED_ACTIONS.items():
        if action in text:
            failures.append(f"{rel}:{_line_no(text, action)}: {action} is deprecated. {hint}")

    if "macos-latest" in text:
        failures.append(
            f"{rel}:{_line_no(text, 'macos-latest')}: pin macOS runner instead of macos-latest."
        )

    miniconda_blocks = re.finditer(
        r"uses:\s*conda-incubator/setup-miniconda@[^\n]+(?P<body>(?:\n\s+[^\n]*)*)",
        text,
    )
    for match in miniconda_blocks:
        body = match.group("body")
        if "channels:" not in body and "conda-remove-defaults:" not in body:
            line = text[: match.start()].count("\n") + 1
            failures.append(
                f"{rel}:{line}: setup-miniconda must set channels or conda-remove-defaults."
            )

    return failures


def main() -> int:
    if not WORKFLOWS.exists():
        print("No .github/workflows directory found.")
        return 0

    failures: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        failures.extend(_check_file(path))

    if failures:
        print("Workflow hygiene checks failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Workflow hygiene checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
