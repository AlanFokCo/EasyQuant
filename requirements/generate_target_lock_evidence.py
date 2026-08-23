#!/usr/bin/env python3
"""Write deterministic checked evidence for four CPython 3.10 target branches.

Use a marker-preserving universal output for the 3.10.0 boundary and separate
macOS-arm64/manylinux-x86_64 runtime outputs for Python 3.10.20. This tool does
not resolve dependencies itself; it serializes the target results only when
each one exactly matches the active branch of the checked hash lock.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

from packaging.requirements import InvalidRequirement, Requirement


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluator.inventory import (  # noqa: E402
    _LOCK_TARGET_MATRIX,
    _RESOLVER_EVIDENCE_SCHEMA,
    _active_hash_lock_pins,
    _read_hash_lock,
    _read_lock_input_fingerprint,
    _resolver_evidence_resolver,
    _resolver_pin_difference_detail,
    normalize_distribution_name,
)


def generate(
    lock_path: Path,
    universal_resolved_path: Path,
    macos_resolved_path: Path,
    linux_resolved_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Atomically record four exact target resolutions bound to ``lock_path``."""
    lock_path = Path(lock_path)
    pins = _read_hash_lock(lock_path)
    fingerprint_state, fingerprint = _read_lock_input_fingerprint(lock_path)
    if fingerprint_state != "valid" or fingerprint is None:
        raise ValueError("lock must contain one valid lock-input fingerprint")

    resolved_paths = {
        "universal": Path(universal_resolved_path),
        "macos": Path(macos_resolved_path),
        "linux": Path(linux_resolved_path),
    }
    universal_pins = _read_hash_lock(resolved_paths["universal"])
    targets = {}
    for target in _LOCK_TARGET_MATRIX:
        target_id = target["id"]
        if target["evidence_source"] == "universal":
            resolved = _active_hash_lock_pins(universal_pins, target)
        else:
            resolved = _read_resolved_pins(
                resolved_paths[target["platform"]], target["marker_environment"]
            )
        locked = _active_hash_lock_pins(pins, target)
        difference = _resolver_pin_difference_detail(target_id, locked, resolved)
        if difference is not None:
            raise ValueError(difference)
        targets[target_id] = {
            "platform": target["platform"],
            "python_full_version": target["python_full_version"],
            "pins": dict(sorted(resolved.items())),
        }

    payload: dict[str, Any] = {
        "schema": _RESOLVER_EVIDENCE_SCHEMA,
        "lock_sha256": sha256(lock_path.read_bytes()).hexdigest(),
        "lock_input_fingerprint": f"v1:{fingerprint}",
        "resolver": _resolver_evidence_resolver(),
        "targets": targets,
    }
    _atomic_write(output_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def _read_resolved_pins(path: Path, environment: Mapping[str, str]) -> dict[str, str]:
    pins = {}
    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[:1].isspace() or raw_line.rstrip().endswith("\\"):
            raise ValueError(f"{path}:{line_number}: unsupported resolver output line")
        try:
            requirement = Requirement(stripped)
        except InvalidRequirement as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid requirement {stripped!r}"
            ) from exc
        if requirement.url:
            raise ValueError(
                f"{path}:{line_number}: direct URL requirements are unsupported"
            )
        specifiers = list(requirement.specifier)
        exact = [specifier for specifier in specifiers if specifier.operator == "=="]
        if len(specifiers) != 1 or len(exact) != 1 or exact[0].version.endswith(".*"):
            raise ValueError(f"{path}:{line_number}: expected one exact == pin")
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        name = normalize_distribution_name(requirement.name)
        if name in pins:
            raise ValueError(f"{path}:{line_number}: duplicate active pin for {name}")
        pins[name] = exact[0].version
    return pins


def _atomic_write(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(value)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--universal-resolved", type=Path, required=True)
    parser.add_argument("--macos-resolved", type=Path, required=True)
    parser.add_argument("--linux-resolved", type=Path, required=True)
    args = parser.parse_args()
    payload = generate(
        args.lock,
        args.universal_resolved,
        args.macos_resolved,
        args.linux_resolved,
        args.output,
    )
    print(
        "wrote resolver evidence for "
        f"{len(payload['targets'])} Python 3.10 targets: {args.output}"
    )


if __name__ == "__main__":
    main()
