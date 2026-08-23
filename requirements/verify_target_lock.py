#!/usr/bin/env python3
"""Compare marker-active hash-lock pins with a resolver result for one target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


def compare(
    lock_path: Path,
    resolved_path: Path,
    *,
    platform: str,
    python_full_version: str = "3.10.20",
) -> dict[str, list[str]]:
    """Return exact-pin differences for one explicit Python 3.10 target."""
    environment = _target_environment(platform, python_full_version)
    locked = _active_pins(lock_path, environment)
    resolved = _active_pins(resolved_path, environment)
    missing = sorted(set(resolved) - set(locked))
    extra = sorted(set(locked) - set(resolved))
    version_mismatch = sorted(
        f"{name}: resolved {resolved[name]}, lock {locked[name]}"
        for name in set(resolved) & set(locked)
        if resolved[name] != locked[name]
    )
    return {
        "missing": missing,
        "extra": extra,
        "version_mismatch": version_mismatch,
    }


def _target_environment(platform: str, python_full_version: str) -> dict[str, str]:
    settings = {
        "linux": ("Linux", "linux", "x86_64"),
        "macos": ("Darwin", "darwin", "arm64"),
    }
    try:
        platform_system, sys_platform, platform_machine = settings[platform]
    except KeyError as exc:
        raise ValueError(f"unsupported target platform: {platform}") from exc
    pieces = python_full_version.split(".")
    if len(pieces) < 2 or any(not part.isdigit() for part in pieces):
        raise ValueError("python_full_version must be a numeric dotted version")

    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "implementation_version": python_full_version,
            "os_name": "posix",
            "platform_machine": platform_machine,
            "platform_python_implementation": "CPython",
            "platform_release": "",
            "platform_system": platform_system,
            "platform_version": "",
            "python_full_version": python_full_version,
            "python_version": ".".join(pieces[:2]),
            "sys_platform": sys_platform,
            "extra": "",
        }
    )
    return {key: str(value) for key, value in environment.items()}


def _active_pins(path: Path, environment: Mapping[str, str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line or raw_line[:1].isspace() or raw_line.startswith("#"):
            continue
        requirement_text = raw_line.rstrip().removesuffix("\\").strip()
        try:
            requirement = Requirement(requirement_text)
        except InvalidRequirement as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid requirement {requirement_text!r}"
            ) from exc
        if requirement.url:
            raise ValueError(
                f"{path}:{line_number}: direct URL requirements are unsupported"
            )
        specifiers = list(requirement.specifier)
        exact = [specifier for specifier in specifiers if specifier.operator == "=="]
        if len(specifiers) != 1 or len(exact) != 1:
            raise ValueError(f"{path}:{line_number}: expected one exact == pin")
        if requirement.marker is not None and not requirement.marker.evaluate(
            environment
        ):
            continue
        name = canonicalize_name(requirement.name)
        version = exact[0].version
        if name in pins:
            raise ValueError(f"{path}:{line_number}: duplicate active pin for {name}")
        pins[name] = version
    return pins


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("resolved", type=Path)
    parser.add_argument("--platform", choices=("linux", "macos"), required=True)
    parser.add_argument("--python-full-version", default="3.10.20")
    args = parser.parse_args()
    result = compare(
        args.lock,
        args.resolved,
        platform=args.platform,
        python_full_version=args.python_full_version,
    )
    print(json.dumps(result, sort_keys=True))
    if any(result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
