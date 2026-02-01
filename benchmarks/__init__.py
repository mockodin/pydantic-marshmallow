"""Benchmark framework for marshmallow-pydantic.

This package provides:
- benchmark_framework: Core benchmark utilities with JSON result storage
- run_benchmarks: CLI for running and comparing benchmarks
"""

from .benchmark_framework import (
    BenchmarkResult,
    BenchmarkSuite,
    run_benchmark,
    compare_results,
    format_comparison_table,
)

__all__ = [
    "BenchmarkResult",
    "BenchmarkSuite",
    "run_benchmark",
    "compare_results",
    "format_comparison_table",
]
