#!/usr/bin/env python3
"""Augment a pip-compile lock with official PyPI release SHA-256 hashes.

``pip-compile --generate-hashes`` records artifacts visible to its resolver
host.  This intentionally small, sequential tool keeps those exact pins and
replaces each pin's hash block with the complete SHA-256 set published by
PyPI's release JSON endpoint.  It is suitable for a checked-in lock consumed
on more than one supported platform; it is not a dependency resolver.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Iterable, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


PYPI_RELEASE_URL = "https://pypi.org/pypi/{project}/{version}/json"
MAX_RESPONSE_BYTES = 5_000_000
_HASH_VALUE = re.compile(r"[0-9a-f]{64}")
_AUGMENTATION_MARKER = (
    "# Hashes below were augmented from official PyPI release metadata for every "
    "pinned artifact.\n"
)


class PinnedEntry(NamedTuple):
    """One exact requirement and the adjacent hash lines that belong to it."""

    start: int
    stop: int
    requirement_text: str
    name: str
    version: str
    newline: str


def parse_entry(lines: list[str], start: int) -> PinnedEntry | None:
    """Parse one pip-compile exact pin and its immediately following hashes."""
    source = lines[start]
    stripped = source.strip()
    if not stripped or source[:1].isspace() or stripped.startswith(("#", "-")):
        return None

    newline = "\r\n" if source.endswith("\r\n") else "\n"
    requirement_text = source.removesuffix("\r\n").removesuffix("\n").rstrip()
    if requirement_text.endswith("\\"):
        requirement_text = requirement_text[:-1].rstrip()
    try:
        requirement = Requirement(requirement_text)
    except InvalidRequirement:
        return None

    specifiers = list(requirement.specifier)
    exact_pins = [specifier for specifier in specifiers if specifier.operator == "=="]
    if requirement.url or len(specifiers) != 1 or len(exact_pins) != 1:
        raise ValueError(
            f"line {start + 1}: expected exactly one == pin, got {requirement_text!r}"
        )

    stop = start + 1
    while stop < len(lines) and _is_hash_line(lines[stop]):
        stop += 1
    return PinnedEntry(
        start=start,
        stop=stop,
        requirement_text=requirement_text,
        name=canonicalize_name(requirement.name),
        version=exact_pins[0].version,
        newline=newline,
    )


def fetch_hashes(
    name: str,
    version: str,
    timeout: float,
    retries: int,
    max_files: int,
    deadline: float | None = None,
) -> list[str]:
    """Fetch one bounded release response from the official PyPI JSON API."""
    url = PYPI_RELEASE_URL.format(
        project=quote(name, safe=""), version=quote(version, safe="")
    )
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "EasyQuant-lock-hash-enricher/1",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        request_timeout = _remaining_timeout(timeout, deadline)
        try:
            with urlopen(request, timeout=request_timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError(f"{name}=={version}: PyPI response exceeds size limit")
            payload = json.loads(raw)
            files = payload.get("urls")
            if not isinstance(files, list) or not files:
                raise ValueError(f"{name}=={version}: PyPI returned no release files")
            if len(files) > max_files:
                raise ValueError(
                    f"{name}=={version}: {len(files)} files exceeds limit {max_files}"
                )
            hashes = {
                item.get("digests", {}).get("sha256", "").lower()
                for item in files
                if isinstance(item, dict)
            }
            hashes.discard("")
            if not hashes or any(
                _HASH_VALUE.fullmatch(digest) is None for digest in hashes
            ):
                raise ValueError(
                    f"{name}=={version}: PyPI response has an invalid or missing SHA256"
                )
            return sorted(hashes)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            last_error = error
            if attempt + 1 == retries:
                break
            time.sleep(min(0.5 * (attempt + 1), _remaining_timeout(timeout, deadline)))
    raise RuntimeError(
        f"failed to fetch {name}=={version} from official PyPI JSON API: {last_error}"
    )


def enrich(
    input_path: Path,
    output_path: Path,
    *,
    timeout: float,
    retries: int,
    max_entries: int,
    max_files: int,
    deadline: float | None = None,
) -> tuple[int, int]:
    """Atomically write a lock with every exact pin's official release hashes."""
    _validate_limits(timeout, retries, max_entries, max_files, deadline)
    source_lines = input_path.read_text(encoding="utf-8").splitlines(keepends=True)
    entries = _find_entries(source_lines)
    if not entries:
        raise ValueError("no exact pinned requirements found")
    if len(entries) > max_entries:
        raise ValueError(
            f"{len(entries)} pinned requirements exceeds limit {max_entries}"
        )

    deadline_at = time.monotonic() + deadline if deadline is not None else None
    hashes_by_release: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        key = (entry.name, entry.version)
        if key not in hashes_by_release:
            hashes_by_release[key] = fetch_hashes(
                entry.name,
                entry.version,
                timeout,
                retries,
                max_files,
                deadline_at,
            )

    rendered = _render_lock(source_lines, entries, hashes_by_release)
    _atomic_write(output_path, rendered)
    return len(entries), sum(len(hashes) for hashes in hashes_by_release.values())


def _find_entries(lines: list[str]) -> list[PinnedEntry]:
    entries = []
    index = 0
    while index < len(lines):
        entry = parse_entry(lines, index)
        if entry is None:
            index += 1
        else:
            entries.append(entry)
            index = entry.stop
    return entries


def _is_hash_line(line: str) -> bool:
    value = line.strip()
    if value.endswith("\\"):
        value = value[:-1].rstrip()
    return bool(re.fullmatch(r"--hash=sha256:[0-9a-fA-F]{64}", value))


def _render_lock(
    source_lines: list[str],
    entries: list[PinnedEntry],
    hashes_by_release: dict[tuple[str, str], list[str]],
) -> str:
    result: list[str] = []
    cursor = 0
    has_marker = any(
        _AUGMENTATION_MARKER.rstrip() == line.rstrip() for line in source_lines
    )
    for position, entry in enumerate(entries):
        result.extend(source_lines[cursor : entry.start])
        if position == 0 and not has_marker:
            result.extend([_AUGMENTATION_MARKER, "\n"])
        result.extend(
            _render_entry(entry, hashes_by_release[(entry.name, entry.version)])
        )
        cursor = entry.stop
    result.extend(source_lines[cursor:])
    return "".join(result)


def _render_entry(entry: PinnedEntry, hashes: Iterable[str]) -> list[str]:
    values = list(hashes)
    if not values:
        raise ValueError(f"{entry.name}=={entry.version}: empty hash set")
    lines = [f"{entry.requirement_text} \\{entry.newline}"]
    for index, digest in enumerate(values):
        continuation = " \\" if index + 1 < len(values) else ""
        lines.append(f"    --hash=sha256:{digest}{continuation}{entry.newline}")
    return lines


def _remaining_timeout(timeout: float, deadline: float | None) -> float:
    if deadline is None:
        return timeout
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("overall lock-enrichment deadline exceeded")
    return min(timeout, remaining)


def _validate_limits(
    timeout: float,
    retries: int,
    max_entries: int,
    max_files: int,
    deadline: float | None,
) -> None:
    if timeout <= 0 or retries < 1 or max_entries < 1 or max_files < 1:
        raise ValueError("timeout and all limits must be positive")
    if deadline is not None and deadline <= 0:
        raise ValueError("deadline must be positive when supplied")


def _atomic_write(output_path: Path, value: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(value)
        os.replace(temporary, output_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--deadline", type=float, default=180.0)
    parser.add_argument("--max-entries", type=int, default=100)
    parser.add_argument("--max-files", type=int, default=500)
    args = parser.parse_args()
    entries, hashes = enrich(
        args.input,
        args.output,
        timeout=args.timeout,
        retries=args.retries,
        max_entries=args.max_entries,
        max_files=args.max_files,
        deadline=args.deadline,
    )
    print(f"enriched {entries} pins with {hashes} release SHA256 hashes: {args.output}")


if __name__ == "__main__":
    main()
