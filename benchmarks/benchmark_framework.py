"""Benchmark framework for performance measurement and historical tracking.

This module provides a standardized way to:
- Run benchmarks with statistical rigor
- Store results in JSON for historical comparison
- Detect performance regressions between versions

Usage:
    from benchmarks import BenchmarkSuite, run_benchmark, compare_results

    suite = BenchmarkSuite("my_benchmarks")

    @suite.add("simple_load")
    def bench_simple_load():
        schema.load(data)

    results = suite.run()
    suite.save_results("results/latest.json")

    # Compare with baseline
    comparison = compare_results("results/baseline.json", "results/latest.json")
"""

from __future__ import annotations

import functools
import gc
import hashlib
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class BenchmarkResult:
    """Result of a single benchmark.

    Attributes:
        name: Benchmark name/identifier.
        iterations: Number of iterations run.
        total_time_s: Total wall-clock time in seconds.
        mean_us: Mean time per operation in microseconds.
        median_us: Median time per operation in microseconds.
        std_dev_us: Standard deviation in microseconds.
        min_us: Minimum time in microseconds.
        max_us: Maximum time in microseconds.
        p95_us: 95th percentile in microseconds.
        p99_us: 99th percentile in microseconds.
        ops_per_sec: Operations per second throughput.
        samples: Raw sample timings (optional, for detailed analysis).
    """

    name: str
    iterations: int
    total_time_s: float
    mean_us: float
    median_us: float
    std_dev_us: float
    min_us: float
    max_us: float
    p95_us: float
    p99_us: float
    ops_per_sec: float
    samples: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, optionally excluding samples."""
        d = asdict(self)
        # Samples can be large; exclude by default in serialization
        d.pop("samples", None)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkResult:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            iterations=data["iterations"],
            total_time_s=data["total_time_s"],
            mean_us=data["mean_us"],
            median_us=data["median_us"],
            std_dev_us=data["std_dev_us"],
            min_us=data["min_us"],
            max_us=data["max_us"],
            p95_us=data["p95_us"],
            p99_us=data["p99_us"],
            ops_per_sec=data["ops_per_sec"],
            samples=data.get("samples", []),
        )


@dataclass
class BenchmarkSuiteResult:
    """Results from a complete benchmark suite run.

    Attributes:
        suite_name: Name of the benchmark suite.
        timestamp: ISO timestamp of when benchmarks were run.
        git_commit: Current git commit hash (if available).
        python_version: Python version string.
        platform_info: Platform/OS information.
        package_versions: Versions of key packages.
        results: Individual benchmark results.
        metadata: Additional metadata.
    """

    suite_name: str
    timestamp: str
    git_commit: str | None
    python_version: str
    platform_info: str
    package_versions: dict[str, str]
    results: dict[str, BenchmarkResult]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "suite_name": self.suite_name,
            "timestamp": self.timestamp,
            "git_commit": self.git_commit,
            "python_version": self.python_version,
            "platform_info": self.platform_info,
            "package_versions": self.package_versions,
            "results": {name: r.to_dict() for name, r in self.results.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkSuiteResult:
        """Create from dictionary."""
        return cls(
            suite_name=data["suite_name"],
            timestamp=data["timestamp"],
            git_commit=data.get("git_commit"),
            python_version=data["python_version"],
            platform_info=data["platform_info"],
            package_versions=data.get("package_versions", {}),
            results={
                name: BenchmarkResult.from_dict(r) for name, r in data["results"].items()
            },
            metadata=data.get("metadata", {}),
        )


def _get_git_commit() -> str | None:
    """Get current git commit hash if in a git repository."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_package_versions() -> dict[str, str]:
    """Get versions of relevant packages."""
    versions = {}
    packages = ["marshmallow", "pydantic", "marshmallow-pydantic"]

    for pkg in packages:
        try:
            if pkg == "marshmallow-pydantic":
                from pydantic_marshmallow import __version__

                versions[pkg] = __version__
            else:
                import importlib.metadata

                versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "unknown"

    return versions


def run_benchmark(
    func: Callable[[], Any],
    iterations: int = 1000,
    warmup: int = 100,
    name: str | None = None,
    collect_samples: bool = False,
) -> BenchmarkResult:
    """Run a benchmark with statistical analysis.

    Args:
        func: Zero-argument function to benchmark.
        iterations: Number of iterations to run.
        warmup: Number of warmup iterations (not counted).
        name: Optional benchmark name.
        collect_samples: Whether to save individual sample timings.

    Returns:
        BenchmarkResult with timing statistics.
    """
    # Warmup phase
    for _ in range(warmup):
        func()

    # Force garbage collection before measurement
    gc.collect()
    gc.disable()

    try:
        samples: list[float] = []
        start_total = time.perf_counter()

        for _ in range(iterations):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            samples.append(elapsed * 1_000_000)  # Convert to microseconds

        end_total = time.perf_counter()
    finally:
        gc.enable()

    total_time = end_total - start_total

    # Statistical analysis
    sorted_samples = sorted(samples)
    mean = statistics.mean(samples)
    median = statistics.median(samples)
    std_dev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    min_time = min(samples)
    max_time = max(samples)

    # Percentiles
    p95_idx = int(0.95 * len(sorted_samples))
    p99_idx = int(0.99 * len(sorted_samples))
    p95 = sorted_samples[p95_idx] if sorted_samples else 0.0
    p99 = sorted_samples[p99_idx] if sorted_samples else 0.0

    # Throughput
    ops_per_sec = iterations / total_time if total_time > 0 else 0.0

    return BenchmarkResult(
        name=name or func.__name__,
        iterations=iterations,
        total_time_s=total_time,
        mean_us=mean,
        median_us=median,
        std_dev_us=std_dev,
        min_us=min_time,
        max_us=max_time,
        p95_us=p95,
        p99_us=p99,
        ops_per_sec=ops_per_sec,
        samples=samples if collect_samples else [],
    )


class BenchmarkSuite:
    """Collection of related benchmarks with execution and result management.

    Usage:
        suite = BenchmarkSuite("validation_benchmarks")

        @suite.add("simple_load")
        def bench_simple_load():
            schema.load(data)

        results = suite.run()
        suite.save_results("results/validation_benchmarks.json")
    """

    def __init__(
        self,
        name: str,
        iterations: int = 1000,
        warmup: int = 100,
    ) -> None:
        """Initialize benchmark suite.

        Args:
            name: Suite name for identification.
            iterations: Default iterations per benchmark.
            warmup: Default warmup iterations.
        """
        self.name = name
        self.iterations = iterations
        self.warmup = warmup
        self._benchmarks: dict[str, tuple[Callable[[], Any], int, int]] = {}
        self._last_results: BenchmarkSuiteResult | None = None

    def add(
        self,
        name: str,
        iterations: int | None = None,
        warmup: int | None = None,
    ) -> Callable[[F], F]:
        """Decorator to add a benchmark to the suite.

        Args:
            name: Benchmark name.
            iterations: Override default iterations.
            warmup: Override default warmup.

        Returns:
            Decorator function.
        """

        def decorator(func: F) -> F:
            self._benchmarks[name] = (
                func,
                iterations or self.iterations,
                warmup or self.warmup,
            )
            return func

        return decorator

    def add_function(
        self,
        name: str,
        func: Callable[[], Any],
        iterations: int | None = None,
        warmup: int | None = None,
    ) -> None:
        """Add a benchmark function directly (without decorator).

        Args:
            name: Benchmark name.
            func: Function to benchmark.
            iterations: Override default iterations.
            warmup: Override default warmup.
        """
        self._benchmarks[name] = (
            func,
            iterations or self.iterations,
            warmup or self.warmup,
        )

    def run(
        self,
        verbose: bool = True,
        filter_pattern: str | None = None,
    ) -> BenchmarkSuiteResult:
        """Run all benchmarks in the suite.

        Args:
            verbose: Print progress and results.
            filter_pattern: Only run benchmarks matching pattern (substring match).

        Returns:
            BenchmarkSuiteResult with all results.
        """
        results: dict[str, BenchmarkResult] = {}

        benchmarks = self._benchmarks.items()
        if filter_pattern:
            benchmarks = [(n, b) for n, b in benchmarks if filter_pattern in n]

        if verbose:
            print(f"\n{'=' * 70}")
            print(f"Running benchmark suite: {self.name}")
            print(f"{'=' * 70}")

        for name, (func, iterations, warmup) in benchmarks:
            if verbose:
                print(f"  Running: {name} ({iterations} iterations)...", end=" ")

            result = run_benchmark(
                func, iterations=iterations, warmup=warmup, name=name
            )
            results[name] = result

            if verbose:
                print(f"{result.mean_us:.2f} µs (±{result.std_dev_us:.2f})")

        suite_result = BenchmarkSuiteResult(
            suite_name=self.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            git_commit=_get_git_commit(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            platform_info=platform.platform(),
            package_versions=_get_package_versions(),
            results=results,
        )

        self._last_results = suite_result

        if verbose:
            print(f"{'=' * 70}\n")

        return suite_result

    def save_results(self, filepath: str | Path) -> None:
        """Save last results to JSON file.

        Args:
            filepath: Path to save results.
        """
        if self._last_results is None:
            raise RuntimeError("No results to save. Run benchmarks first.")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self._last_results.to_dict(), f, indent=2)

    @staticmethod
    def load_results(filepath: str | Path) -> BenchmarkSuiteResult:
        """Load results from JSON file.

        Args:
            filepath: Path to results file.

        Returns:
            BenchmarkSuiteResult instance.
        """
        with open(filepath) as f:
            data = json.load(f)
        return BenchmarkSuiteResult.from_dict(data)


@dataclass
class ComparisonResult:
    """Comparison between two benchmark results.

    Attributes:
        name: Benchmark name.
        baseline_mean_us: Baseline mean time.
        current_mean_us: Current mean time.
        change_percent: Percentage change (positive = slower).
        is_regression: Whether this is a significant regression.
        significance: Statistical significance indicator.
    """

    name: str
    baseline_mean_us: float
    current_mean_us: float
    change_percent: float
    is_regression: bool
    significance: str  # "significant", "marginal", "none"

    @property
    def status_emoji(self) -> str:
        """Get status emoji for display."""
        if self.is_regression:
            return "🔴" if self.significance == "significant" else "🟡"
        if self.change_percent < -5:
            return "🟢"  # Significant improvement
        return "⚪"  # No significant change


def compare_results(
    baseline: str | Path | BenchmarkSuiteResult,
    current: str | Path | BenchmarkSuiteResult,
    regression_threshold: float = 10.0,
    marginal_threshold: float = 5.0,
) -> dict[str, ComparisonResult]:
    """Compare two benchmark results to detect regressions.

    Args:
        baseline: Baseline results (filepath or BenchmarkSuiteResult).
        current: Current results to compare.
        regression_threshold: Percent increase to flag as regression.
        marginal_threshold: Percent increase to flag as marginal.

    Returns:
        Dictionary of comparison results by benchmark name.
    """
    if isinstance(baseline, (str, Path)):
        baseline = BenchmarkSuite.load_results(baseline)
    if isinstance(current, (str, Path)):
        current = BenchmarkSuite.load_results(current)

    comparisons: dict[str, ComparisonResult] = {}

    # Compare all benchmarks present in current results
    for name, current_result in current.results.items():
        if name not in baseline.results:
            continue

        baseline_result = baseline.results[name]
        baseline_mean = baseline_result.mean_us
        current_mean = current_result.mean_us

        if baseline_mean > 0:
            change_percent = ((current_mean - baseline_mean) / baseline_mean) * 100
        else:
            change_percent = 0.0

        # Determine significance
        if change_percent >= regression_threshold:
            significance = "significant"
            is_regression = True
        elif change_percent >= marginal_threshold:
            significance = "marginal"
            is_regression = True
        else:
            significance = "none"
            is_regression = False

        comparisons[name] = ComparisonResult(
            name=name,
            baseline_mean_us=baseline_mean,
            current_mean_us=current_mean,
            change_percent=change_percent,
            is_regression=is_regression,
            significance=significance,
        )

    return comparisons


def format_comparison_table(
    comparisons: dict[str, ComparisonResult],
    show_all: bool = False,
) -> str:
    """Format comparison results as a table.

    Args:
        comparisons: Dictionary of comparison results.
        show_all: Show all benchmarks, not just regressions.

    Returns:
        Formatted table string.
    """
    lines = [
        "",
        "=" * 80,
        "PERFORMANCE COMPARISON",
        "=" * 80,
        f"{'Benchmark':<35} {'Baseline':>12} {'Current':>12} {'Change':>12} {'Status':>6}",
        "-" * 80,
    ]

    # Sort by change percentage (worst first)
    sorted_comparisons = sorted(
        comparisons.values(), key=lambda c: c.change_percent, reverse=True
    )

    for comp in sorted_comparisons:
        if not show_all and not comp.is_regression and comp.change_percent > -5:
            continue

        change_str = f"{comp.change_percent:+.1f}%"
        lines.append(
            f"{comp.name:<35} {comp.baseline_mean_us:>10.1f}µs "
            f"{comp.current_mean_us:>10.1f}µs {change_str:>12} {comp.status_emoji:>6}"
        )

    if not any(c.is_regression for c in comparisons.values()):
        lines.append("  ✅ No regressions detected")

    lines.extend(
        [
            "-" * 80,
            "Legend: 🔴 Significant regression (>10%) | 🟡 Marginal (>5%) | 🟢 Improved | ⚪ No change",
            "=" * 80,
            "",
        ]
    )

    return "\n".join(lines)


def format_results_table(results: BenchmarkSuiteResult) -> str:
    """Format benchmark results as a readable table.

    Args:
        results: Benchmark suite results.

    Returns:
        Formatted table string.
    """
    lines = [
        "",
        "=" * 90,
        f"BENCHMARK RESULTS: {results.suite_name}",
        f"Timestamp: {results.timestamp}",
        f"Git commit: {results.git_commit or 'N/A'}",
        f"Python: {results.python_version} | Platform: {results.platform_info}",
        "=" * 90,
        f"{'Benchmark':<35} {'Mean':>12} {'Median':>12} {'StdDev':>10} {'p95':>12} {'ops/s':>12}",
        "-" * 90,
    ]

    for name, result in sorted(results.results.items()):
        lines.append(
            f"{name:<35} {result.mean_us:>10.1f}µs {result.median_us:>10.1f}µs "
            f"{result.std_dev_us:>8.1f}µs {result.p95_us:>10.1f}µs {result.ops_per_sec:>10.0f}"
        )

    lines.extend(["=" * 90, ""])

    return "\n".join(lines)
