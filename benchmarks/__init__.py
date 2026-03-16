"""Benchmark framework for pydantic-marshmallow.

This package provides:
- benchmark_framework: Core benchmark utilities with JSON result storage
- run_benchmarks: CLI for running and comparing benchmarks
"""

from .benchmark_framework import (
    BenchmarkResult,
    BenchmarkSuite,
    compare_results,
    format_comparison_table,
    run_benchmark,
)

__all__ = [
    "BenchmarkResult",
    "BenchmarkSuite",
    "compare_results",
    "format_comparison_table",
    "run_benchmark",
]
