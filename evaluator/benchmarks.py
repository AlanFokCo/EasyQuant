"""Bounded, comparable performance evidence for eqlib evaluator runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
from typing import Sequence

from .models import Finding, Severity


_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class BenchmarkSample:
    """One wall-time and peak-RSS observation."""

    seconds: float
    max_rss_mb: float


@dataclass(frozen=True)
class BenchmarkResult:
    """Stable aggregate performance result."""

    name: str
    seconds: float
    max_rss_mb: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "seconds": self.seconds,
            "max_rss_mb": self.max_rss_mb,
        }


def measure_benchmark(
    name: str, command: Sequence[str], repeats: int = 5
) -> BenchmarkResult | None:
    """Measure median wall time and maximum RSS, or return unavailable."""
    samples = _samples(command, repeats)
    if not samples:
        return None
    return BenchmarkResult(
        name=name,
        seconds=float(statistics.median(sample.seconds for sample in samples)),
        max_rss_mb=float(max(sample.max_rss_mb for sample in samples)),
    )


def evaluate_benchmarks(
    root: Path, baseline: dict[str, dict[str, float]]
) -> list[Finding]:
    """Compare the controlled cold import benchmark with its approved baseline."""
    result = measure_benchmark(
        "import_eqlib", [sys.executable, "-c", "import eqlib"], repeats=5
    )
    if result is None:
        return [
            Finding(
                "PERF-302",
                Severity.P2,
                "Performance measurement unavailable",
                "The platform time utility did not produce usable wall-time and RSS evidence.",
                status="unavailable",
                remediation="Run the evaluator on macOS or Linux with /usr/bin/time available.",
            )
        ]
    expected = baseline.get(result.name)
    if expected is None:
        return [
            Finding(
                "PERF-302",
                Severity.P2,
                "Performance baseline unavailable",
                f"No approved baseline exists for {result.name}.",
                evidence=result.to_dict(),
                status="unavailable",
                remediation="Record a reviewed baseline for this controlled environment.",
            )
        ]
    if (
        result.seconds > expected["seconds"] * 2
        or result.max_rss_mb > expected["max_rss_mb"] * 2
    ):
        return [
            Finding(
                "PERF-301",
                Severity.P2,
                "Cold import regression",
                "import eqlib exceeds the approved 2x baseline.",
                evidence={"actual": result.to_dict(), "baseline": expected},
                remediation="Investigate import-time or memory growth before accepting the regression.",
            )
        ]
    return []


def _samples(command: Sequence[str], repeats: int) -> list[BenchmarkSample] | None:
    """Collect platform-native /usr/bin/time samples without inventing RSS values."""
    time_command = _time_command(command)
    if time_command is None:
        return None
    results = []
    for _ in range(repeats):
        try:
            completed = subprocess.run(
                time_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        sample = _parse_time_output(completed.stderr)
        if sample is None:
            return None
        results.append(sample)
    return results


def _time_command(command: Sequence[str]) -> list[str] | None:
    """Select a native time implementation with peak-RSS output."""
    system = platform.system()
    if system == "Darwin":
        return ["/usr/bin/time", "-l", *command]
    if system == "Linux":
        return ["/usr/bin/time", "-v", *command]
    return None


def _parse_time_output(output: str) -> BenchmarkSample | None:
    """Parse macOS or GNU time output into normalized units."""
    mac_seconds = re.search(r"^\s*([0-9.]+)\s+real\b", output, re.MULTILINE)
    mac_rss = re.search(r"(\d+)\s+maximum resident set size", output)
    if mac_seconds and mac_rss:
        return BenchmarkSample(
            float(mac_seconds.group(1)), int(mac_rss.group(1)) / 1_048_576
        )
    linux_seconds = re.search(r"Elapsed \(wall clock\) time .*?:\s*([0-9:.]+)", output)
    linux_rss = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", output)
    if linux_seconds and linux_rss:
        return BenchmarkSample(
            _parse_elapsed(linux_seconds.group(1)), int(linux_rss.group(1)) / 1024
        )
    return None


def _parse_elapsed(value: str) -> float:
    """Parse GNU time's H:MM:SS or MM:SS elapsed value."""
    parts = [float(item) for item in value.split(":")]
    seconds = 0.0
    for item in parts:
        seconds = seconds * 60 + item
    return seconds
