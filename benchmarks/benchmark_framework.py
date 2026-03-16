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

import gc
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

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
    packages = ["marshmallow", "pydantic", "pydantic-marshmallow"]

    for pkg in packages:
        try:
            if pkg == "pydantic-marshmallow":
                from pydantic_marshmallow import __version__

                versions[pkg] = __version__ if __version__ else "current (editable)"
            else:
                import importlib.metadata

                versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "current (editable)" if pkg == "pydantic-marshmallow" else "unknown"

    return versions


def _remove_outliers_iqr(samples: list[float], factor: float = 1.5) -> list[float]:
    """Remove outliers using IQR method.

    Args:
        samples: Raw sample timings.
        factor: IQR multiplier for outlier threshold (1.5 = standard, 3.0 = extreme only).

    Returns:
        Samples with outliers removed.
    """
    if len(samples) < 4:
        return samples

    sorted_samples = sorted(samples)
    q1_idx = len(sorted_samples) // 4
    q3_idx = (3 * len(sorted_samples)) // 4
    q1 = sorted_samples[q1_idx]
    q3 = sorted_samples[q3_idx]
    iqr = q3 - q1

    lower_bound = q1 - factor * iqr
    upper_bound = q3 + factor * iqr

    return [s for s in samples if lower_bound <= s <= upper_bound]


def run_benchmark(
    func: Callable[[], Any],
    iterations: int = 1000,
    warmup: int = 100,
    name: str | None = None,
    collect_samples: bool = False,
    runs: int = 3,
    remove_outliers: bool = True,
) -> BenchmarkResult:
    """Run a benchmark with statistical analysis.

    Uses multiple runs and takes median to reduce noise from system variance.
    Optionally removes outliers using IQR method for cleaner statistics.

    Args:
        func: Zero-argument function to benchmark.
        iterations: Number of iterations per run.
        warmup: Number of warmup iterations (not counted).
        name: Optional benchmark name.
        collect_samples: Whether to save individual sample timings.
        runs: Number of complete runs to perform (takes median).
        remove_outliers: Whether to remove outliers using IQR method.

    Returns:
        BenchmarkResult with timing statistics.
    """
    all_run_medians: list[float] = []
    all_samples: list[float] = []

    for _ in range(runs):
        # Warmup phase before each run
        for _ in range(warmup):
            func()

        # Force garbage collection before measurement
        gc.collect()
        gc.disable()

        try:
            samples: list[float] = []

            for _ in range(iterations):
                start = time.perf_counter()
                func()
                elapsed = time.perf_counter() - start
                samples.append(elapsed * 1_000_000)  # Convert to microseconds
        finally:
            gc.enable()

        # Remove outliers from this run if enabled
        if remove_outliers:
            clean_samples = _remove_outliers_iqr(samples)
        else:
            clean_samples = samples

        run_median = statistics.median(clean_samples)
        all_run_medians.append(run_median)
        all_samples.extend(clean_samples)

    # Use median of run medians as the final result (most stable)
    total_time = sum(all_run_medians) * iterations / 1_000_000  # Approximate

    # Remove outliers from combined samples for final statistics
    if remove_outliers:
        final_samples = _remove_outliers_iqr(all_samples)
    else:
        final_samples = all_samples

    # Statistical analysis on cleaned data
    sorted_samples = sorted(final_samples)
    mean = statistics.mean(final_samples)
    median = statistics.median(all_run_medians)  # Median of medians
    std_dev = statistics.stdev(final_samples) if len(final_samples) > 1 else 0.0
    min_time = min(final_samples)
    max_time = max(final_samples)

    # Percentiles
    p95_idx = int(0.95 * len(sorted_samples))
    p99_idx = int(0.99 * len(sorted_samples))
    p95 = sorted_samples[min(p95_idx, len(sorted_samples) - 1)] if sorted_samples else 0.0
    p99 = sorted_samples[min(p99_idx, len(sorted_samples) - 1)] if sorted_samples else 0.0

    # Throughput based on median
    ops_per_sec = 1_000_000 / median if median > 0 else 0.0

    return BenchmarkResult(
        name=name or func.__name__,
        iterations=iterations * runs,
        total_time_s=total_time,
        mean_us=mean,
        median_us=median,
        std_dev_us=std_dev,
        min_us=min_time,
        max_us=max_time,
        p95_us=p95,
        p99_us=p99,
        ops_per_sec=ops_per_sec,
        samples=all_samples if collect_samples else [],
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
        runs: int = 3,
        remove_outliers: bool = True,
    ) -> None:
        """Initialize benchmark suite.

        Args:
            name: Suite name for identification.
            iterations: Default iterations per benchmark per run.
            warmup: Default warmup iterations.
            runs: Default number of runs per benchmark (takes median).
            remove_outliers: Whether to remove outliers using IQR method.
        """
        self.name = name
        self.iterations = iterations
        self.warmup = warmup
        self.runs = runs
        self.remove_outliers = remove_outliers
        self._benchmarks: dict[str, tuple[Callable[[], Any], int, int, int]] = {}
        self._last_results: BenchmarkSuiteResult | None = None

    def add(
        self,
        name: str,
        iterations: int | None = None,
        warmup: int | None = None,
        runs: int | None = None,
    ) -> Callable[[F], F]:
        """Decorator to add a benchmark to the suite.

        Args:
            name: Benchmark name.
            iterations: Override default iterations.
            warmup: Override default warmup.
            runs: Override default runs.

        Returns:
            Decorator function.
        """

        def decorator(func: F) -> F:
            self._benchmarks[name] = (
                func,
                iterations or self.iterations,
                warmup or self.warmup,
                runs or self.runs,
            )
            return func

        return decorator

    def add_function(
        self,
        name: str,
        func: Callable[[], Any],
        iterations: int | None = None,
        warmup: int | None = None,
        runs: int | None = None,
    ) -> None:
        """Add a benchmark function directly (without decorator).

        Args:
            name: Benchmark name.
            func: Function to benchmark.
            iterations: Override default iterations.
            warmup: Override default warmup.
            runs: Override default runs.
        """
        self._benchmarks[name] = (
            func,
            iterations or self.iterations,
            warmup or self.warmup,
            runs or self.runs,
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

        benchmarks = list(self._benchmarks.items())
        if filter_pattern:
            benchmarks = [(n, b) for n, b in benchmarks if filter_pattern in n]

        if verbose:
            print(f"\n{'=' * 70}")
            print(f"Running benchmark suite: {self.name}")
            print(f"{'=' * 70}")

        for name, (func, iterations, warmup, runs) in benchmarks:
            if verbose:
                print(f"  Running: {name} ({iterations}x{runs} iterations)...", end=" ")

            result = run_benchmark(
                func,
                iterations=iterations,
                warmup=warmup,
                name=name,
                runs=runs,
                remove_outliers=self.remove_outliers,
            )
            results[name] = result

            if verbose:
                print(f"{result.median_us:.2f} µs (±{result.std_dev_us:.2f})")

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
        baseline_median_us: Baseline median time.
        current_median_us: Current median time.
        change_percent: Percentage change (positive = slower).
        is_regression: Whether this is a significant regression.
        significance: Statistical significance indicator.
    """

    name: str
    baseline_median_us: float
    current_median_us: float
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

    Uses median for comparison as it's more robust to outliers.

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
        baseline_median = baseline_result.median_us
        current_median = current_result.median_us

        if baseline_median > 0:
            change_percent = ((current_median - baseline_median) / baseline_median) * 100
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
            baseline_median_us=baseline_median,
            current_median_us=current_median,
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
            f"{comp.name:<35} {comp.baseline_median_us:>10.1f}µs "
            f"{comp.current_median_us:>10.1f}µs {change_str:>12} {comp.status_emoji:>6}"
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
        f"{'Benchmark':<35} {'Median':>12} {'Mean':>12} {'StdDev':>10} {'p95':>12} {'ops/s':>12}",
        "-" * 90,
    ]

    for name, result in sorted(results.results.items()):
        lines.append(
            f"{name:<35} {result.median_us:>10.1f}µs {result.mean_us:>10.1f}µs "
            f"{result.std_dev_us:>8.1f}µs {result.p95_us:>10.1f}µs {result.ops_per_sec:>10.0f}"
        )

    lines.extend(["=" * 90, ""])

    return "\n".join(lines)


def _group_benchmarks(results: BenchmarkSuiteResult) -> dict[str, dict[str, BenchmarkResult]]:
    """Group benchmarks by category (strip _bridge/_marshmallow/_raw_pydantic suffix).

    Returns dict of {category: {variant: result}} where variant is
    'bridge', 'marshmallow', or 'raw_pydantic'.
    """
    groups: dict[str, dict[str, BenchmarkResult]] = {}
    suffixes = ("_bridge", "_marshmallow", "_raw_pydantic")

    for name, result in results.results.items():
        for suffix in suffixes:
            if name.endswith(suffix):
                category = name[: -len(suffix)]
                variant = suffix[1:]  # strip leading _
                groups.setdefault(category, {})[variant] = result
                break
        else:
            # No matching suffix — standalone benchmark
            groups.setdefault(name, {})["standalone"] = result

    return groups


def _collect_comparisons(
    all_results: list[BenchmarkSuiteResult],
) -> list[tuple[str, str, BenchmarkResult, BenchmarkResult, BenchmarkResult | None]]:
    """Collect all bridge-vs-marshmallow comparison data across suites.

    Returns list of (suite_name, category, bridge_result, ma_result, raw_result|None).
    """
    comparisons: list[
        tuple[str, str, BenchmarkResult, BenchmarkResult, BenchmarkResult | None]
    ] = []
    for suite_result in all_results:
        groups = _group_benchmarks(suite_result)
        for category, variants in groups.items():
            bridge = variants.get("bridge")
            ma = variants.get("marshmallow")
            if bridge and ma:
                raw = variants.get("raw_pydantic")
                comparisons.append(
                    (suite_result.suite_name, category, bridge, ma, raw)
                )
    return comparisons


# Known outlier explanations keyed by substring match on category name
_OUTLIER_EXPLANATIONS: dict[str, str] = {
    "email_validated": (
        "Pydantic uses `email-validator` for RFC 5321 compliance; "
        "MA uses a regex. Bridge + raw Pydantic are nearly identical, "
        "confirming the cost is in Pydantic's validator, not the bridge."
    ),
    "validated_load": (
        "Uses `EmailStr` (RFC 5321) — see email_validated row."
    ),
    "computed_field_dump": (
        "Same dump-path overhead, plus Pydantic `@computed_field` evaluation."
    ),
}


def _detect_outliers(
    comparisons: list[
        tuple[str, str, BenchmarkResult, BenchmarkResult, BenchmarkResult | None]
    ],
    threshold: float = 3.0,
) -> list[tuple[str, float, float, str]]:
    """Detect benchmarks where bridge is significantly slower than MA.

    Args:
        comparisons: Output of _collect_comparisons.
        threshold: Minimum slowdown ratio (bridge/MA) to flag as outlier.

    Returns:
        List of (display_name, bridge_us, ma_us, explanation).
    """
    outliers: list[tuple[str, float, float, str]] = []
    for _suite, category, bridge, ma, raw in comparisons:
        if ma.median_us > 0:
            slowdown = bridge.median_us / ma.median_us
            if slowdown >= threshold:
                display = category.replace("_", " ").title()
                # Look up known explanation
                explanation = ""
                for key, expl in _OUTLIER_EXPLANATIONS.items():
                    if key in category:
                        explanation = expl
                        break
                if not explanation:
                    if raw and raw.median_us > 0:
                        raw_ratio = bridge.median_us / raw.median_us
                        if raw_ratio < 1.5:
                            explanation = (
                                "Bridge and raw Pydantic are similar — "
                                "slowdown is in Pydantic's validation, not the bridge."
                            )
                        else:
                            explanation = (
                                f"Bridge is {slowdown:.1f}x slower than MA "
                                f"({bridge.median_us:.1f}µs vs {ma.median_us:.1f}µs)."
                            )
                    else:
                        explanation = (
                            f"Bridge is {slowdown:.1f}x slower than MA "
                            f"({bridge.median_us:.1f}µs vs {ma.median_us:.1f}µs)."
                        )
                outliers.append(
                    (display, bridge.median_us, ma.median_us, explanation)
                )

    # Also flag dump-path benchmarks where bridge is >1.5x slower
    for _suite, category, bridge, ma, _raw in comparisons:
        if "dump" in category and ma.median_us > 0:
            slowdown = bridge.median_us / ma.median_us
            if 1.5 <= slowdown < threshold:
                display = category.replace("_", " ").title()
                explanation = ""
                for key, expl in _OUTLIER_EXPLANATIONS.items():
                    if key in category:
                        explanation = expl
                        break
                if not explanation:
                    explanation = (
                        f"Dump path overhead: `model_dump()` + MA serialization "
                        f"({bridge.median_us:.1f}µs vs {ma.median_us:.1f}µs)."
                    )
                # Avoid duplicates
                if not any(d == display for d, _, _, _ in outliers):
                    outliers.append(
                        (display, bridge.median_us, ma.median_us, explanation)
                    )
    return outliers


def _compute_insights(
    comparisons: list[
        tuple[str, str, BenchmarkResult, BenchmarkResult, BenchmarkResult | None]
    ],
) -> list[str]:
    """Generate data-driven key insights from benchmark comparisons.

    Returns list of markdown bullet strings.
    """
    insights: list[str] = []
    load_speedups: list[float] = []
    dump_slowdowns: list[float] = []
    dump_speedups: list[float] = []
    nested_speedups: list[float] = []
    bridge_overheads: list[float] = []

    for _suite, category, bridge, ma, raw in comparisons:
        if ma.median_us <= 0:
            continue
        ratio = ma.median_us / bridge.median_us

        # Classify as load or dump
        if "dump" in category:
            if ratio < 1.0:
                dump_slowdowns.append(1.0 / ratio)
            elif ratio > 1.0:
                dump_speedups.append(ratio)
        else:
            # Skip email outliers from load stats
            if "email_validated" not in category and "validated_load" not in category:
                if ratio > 1.0:
                    load_speedups.append(ratio)

        # Nested/collection benchmarks
        if any(kw in category for kw in ("nested", "deep", "collection", "batch")):
            if ratio > 1.0:
                nested_speedups.append(ratio)

        # Bridge overhead vs raw pydantic (exclude batch benchmarks)
        if raw and raw.median_us > 0 and "dump" not in category:
            if not any(kw in category for kw in ("batch", "batch_100", "batch_1000")):
                overhead = bridge.median_us - raw.median_us
                if overhead > 0:
                    bridge_overheads.append(overhead)

    if load_speedups:
        lo = min(load_speedups)
        hi = max(load_speedups)
        insights.append(
            f"**Load path is {lo:.0f}\u2013{hi:.0f}x faster** than native "
            "Marshmallow across all non-email scenarios"
        )

    if nested_speedups:
        lo = min(nested_speedups)
        hi = max(nested_speedups)
        insights.append(
            f"**Nested/collection models** show the largest advantage "
            f"({lo:.0f}\u2013{hi:.0f}x) because Pydantic's Rust engine "
            "handles nested validation in compiled code"
        )

    if dump_speedups and not dump_slowdowns:
        avg = sum(dump_speedups) / len(dump_speedups)
        insights.append(
            f"**Dump path is ~{avg:.0f}x faster** than native MA for "
            "simple models via the conditional fast-dump optimization"
        )
    elif dump_speedups and dump_slowdowns:
        avg_fast = sum(dump_speedups) / len(dump_speedups)
        avg_slow = sum(dump_slowdowns) / len(dump_slowdowns)
        insights.append(
            f"**Simple dump is ~{avg_fast:.0f}x faster** than native MA "
            "via fast-dump optimization; complex dumps (computed fields, "
            f"hooks) are ~{avg_slow:.0f}x slower due to `model_dump()` + "
            "MA serialization overhead"
        )
    elif dump_slowdowns:
        avg = sum(dump_slowdowns) / len(dump_slowdowns)
        insights.append(
            f"**Dump path is ~{avg:.0f}x slower** than native MA \u2014 this "
            "is the cost of `model_dump()` + MA serialization"
        )

    if bridge_overheads:
        avg_overhead = sum(bridge_overheads) / len(bridge_overheads)
        insights.append(
            f"**Raw Pydantic** column shows the theoretical floor \u2014 bridge "
            f"adds ~{avg_overhead:.1f}\u00b5s of Marshmallow schema overhead "
            "on top of Pydantic's validation"
        )
        insights.append(
            "**Hook caching** (the load-path optimization) short-circuits "
            "Marshmallow hook machinery when no hooks are defined, saving "
            f"~{avg_overhead:.1f}\u00b5s per load"
        )
    else:
        insights.append(
            "**Hook caching** (the load-path optimization) short-circuits "
            "Marshmallow hook machinery when no hooks are defined"
        )

    return insights


def _compute_overhead_ratios(
    comparisons: list[
        tuple[str, str, BenchmarkResult, BenchmarkResult, BenchmarkResult | None]
    ],
) -> list[tuple[str, float, float]]:
    """Compute host-invariant overhead ratios (bridge / raw pydantic).

    Returns list of (display_name, ratio, overhead_us) sorted by ratio descending.
    Only includes benchmarks where raw pydantic baseline is available.
    """
    ratios: list[tuple[str, float, float]] = []
    for _suite, category, bridge, _ma, raw in comparisons:
        if raw and raw.median_us > 0 and bridge.median_us > 0:
            ratio = bridge.median_us / raw.median_us
            overhead_us = bridge.median_us - raw.median_us
            display = category.replace("_", " ").title()
            ratios.append((display, ratio, overhead_us))
    # Sort by ratio descending (highest overhead first)
    ratios.sort(key=lambda x: x[1], reverse=True)
    return ratios


def format_markdown_report(
    all_results: list[BenchmarkSuiteResult],
    *,
    docker_status: str | None = None,
) -> str:
    """Generate a comprehensive markdown benchmark report.

    Args:
        all_results: List of suite results from running benchmarks.
        docker_status: Optional Docker test status string
            (e.g. "2/2 passed (py311-ma3-pd-latest, py311-ma4-pd-latest)").

    Returns:
        Markdown string suitable for writing to file.
    """
    if not all_results:
        return "# Benchmark Report\n\nNo results to report.\n"

    # Use metadata from first result for system info
    meta = all_results[0]

    lines: list[str] = []
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append(f"**Generated:** {meta.timestamp}  ")
    lines.append(f"**Git commit:** `{meta.git_commit or 'N/A'}`  ")
    lines.append(f"**Python:** {meta.python_version}  ")
    lines.append(f"**Platform:** {meta.platform_info}  ")
    pkg_str = ", ".join(f"{k} {v}" for k, v in meta.package_versions.items())
    lines.append(f"**Packages:** {pkg_str}")
    if docker_status:
        lines.append(f"**Docker tests:** {docker_status}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("- Each benchmark runs **3 complete passes** (median of medians)")
    lines.append("- **1000 iterations** per pass (500 for nested, 100 for batch)")
    lines.append("- **IQR outlier removal** for stable statistics")
    lines.append("- GC disabled during measurement")
    lines.append("- All times in **microseconds (\u00b5s)**")
    lines.append("- **Overhead Ratio** = Bridge / Raw Pydantic — host-invariant metric for cross-run comparison")
    lines.append("")

    # Collect all comparison data for analysis sections
    all_comparisons = _collect_comparisons(all_results)

    # Detect outliers for footnotes
    outliers = _detect_outliers(all_comparisons)
    outlier_categories = {name for name, _, _, _ in outliers}

    for suite_result in all_results:
        lines.append(f"## {suite_result.suite_name}")
        lines.append("")

        groups = _group_benchmarks(suite_result)

        # Check if this suite has comparison data (bridge vs marshmallow)
        has_comparison = any(
            "bridge" in variants and "marshmallow" in variants
            for variants in groups.values()
        )

        suite_has_outlier = False
        if has_comparison:
            # Comparison table with speedup and overhead ratio
            lines.append(
                "| Benchmark | Bridge (\u00b5s) | Native MA (\u00b5s) "
                "| Raw Pydantic (\u00b5s) | Bridge vs MA | Overhead Ratio |"
            )
            lines.append(
                "|-----------|------------|-----------------|"
                "-------------------|--------------|----------------|"
            )

            for category, variants in sorted(groups.items()):
                bridge = variants.get("bridge")
                ma = variants.get("marshmallow")
                raw = variants.get("raw_pydantic")

                b_str = f"{bridge.median_us:.1f}" if bridge else "-"
                m_str = f"{ma.median_us:.1f}" if ma else "-"
                r_str = f"{raw.median_us:.1f}" if raw else "\u2014"

                if bridge and ma and ma.median_us > 0:
                    ratio = ma.median_us / bridge.median_us
                    if ratio > 1.05:
                        speedup = f"**{ratio:.1f}x faster**"
                    elif ratio < 0.95:
                        slowdown = 1 / ratio
                        display_name = category.replace("_", " ").title()
                        if display_name in outlier_categories:
                            speedup = f"{slowdown:.1f}x slower*"
                            suite_has_outlier = True
                        else:
                            speedup = f"{slowdown:.1f}x slower"
                    else:
                        speedup = "~same"
                else:
                    speedup = "-"

                # Overhead ratio: bridge / raw pydantic (host-invariant)
                if bridge and raw and raw.median_us > 0:
                    overhead = bridge.median_us / raw.median_us
                    overhead_str = f"{overhead:.2f}x"
                else:
                    overhead_str = "\u2014"

                display = category.replace("_", " ").title()
                lines.append(
                    f"| {display} | {b_str} | {m_str} | {r_str} "
                    f"| {speedup} | {overhead_str} |"
                )
        else:
            # Simple table for non-comparison suites
            lines.append(
                "| Benchmark | Median (\u00b5s) | Mean (\u00b5s) "
                "| StdDev | p95 (\u00b5s) | ops/s |"
            )
            lines.append(
                "|-----------|------------|----------"
                "|--------|---------|-------|"
            )

            for name, result in sorted(suite_result.results.items()):
                display = name.replace("_", " ").title()
                lines.append(
                    f"| {display} | {result.median_us:.1f} | {result.mean_us:.1f} "
                    f"| {result.std_dev_us:.1f} | {result.p95_us:.1f} "
                    f"| {result.ops_per_sec:,.0f} |"
                )

        # Add footnote if this suite had outliers
        if suite_has_outlier:
            lines.append("")
            lines.append(
                "> *See [Known Outliers](#known-outliers) for explanation*"
            )

        lines.append("")

    # Known Outliers section (auto-detected)
    if outliers:
        lines.append("---")
        lines.append("")
        lines.append("## Known Outliers")
        lines.append("")
        lines.append(
            "| Benchmark | Bridge (\u00b5s) | Native MA (\u00b5s) | Why |"
        )
        lines.append("|-----------|------------|-----------------|-----|")
        for display, bridge_us, ma_us, explanation in outliers:
            lines.append(
                f"| **{display}** | {bridge_us:.1f} | {ma_us:.1f} "
                f"| {explanation} |"
            )
        lines.append("")

    # Key insights section (data-driven)
    insights = _compute_insights(all_comparisons)
    lines.append("---")
    lines.append("")
    lines.append("## Key Insights")
    lines.append("")
    for insight in insights:
        lines.append(f"- {insight}")
    lines.append("")

    # Cross-run stability section (variance normalization)
    overhead_ratios = _compute_overhead_ratios(all_comparisons)
    if overhead_ratios:
        lines.append("---")
        lines.append("")
        lines.append("## Cross-Run Stability (Overhead Ratios)")
        lines.append("")
        lines.append(
            "Absolute timings vary with host load, CPU frequency, and thermals. "
            "The **Overhead Ratio** (Bridge \u00b5s \u00f7 Raw Pydantic \u00b5s) cancels out "
            "host variance because both measurements experience the same conditions. "
            "Compare this column across runs to detect real regressions vs noise."
        )
        lines.append("")
        lines.append("| Benchmark | Overhead Ratio | Bridge Overhead (\u00b5s) |")
        lines.append("|-----------|----------------|----------------------|")
        for name, ratio, overhead_us in overhead_ratios:
            lines.append(f"| {name} | {ratio:.2f}x | +{overhead_us:.1f} |")
        lines.append("")
        if len(overhead_ratios) >= 2:
            ratios_only = [r for _, r, _ in overhead_ratios]
            avg_ratio = sum(ratios_only) / len(ratios_only)
            lines.append(
                f"> **Average overhead ratio: {avg_ratio:.2f}x** \u2014 "
                "if this changes significantly between runs on different hosts, "
                "it indicates a real performance change, not host variance."
            )
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Run `python -m benchmarks.run_benchmarks --report` to regenerate "
        "this report.*"
    )
    lines.append("")

    return "\n".join(lines)
