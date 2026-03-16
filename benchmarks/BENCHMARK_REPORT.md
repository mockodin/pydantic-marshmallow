# Benchmark Report

**Generated:** 2026-03-16T13:51:51.070929+00:00  
**Git commit:** `e92355d`  
**Python:** 3.11.6  
**Platform:** Windows-10-10.0.26200-SP0  
**Packages:** marshmallow 3.26.2, pydantic 2.12.5, pydantic-marshmallow None

---

## Methodology

- Each benchmark runs **3 complete passes** (median of medians)
- **1000 iterations** per pass (500 for nested, 100 for batch)
- **IQR outlier removal** for stable statistics
- GC disabled during measurement
- All times in **microseconds (µs)**
- **Overhead Ratio** = Bridge / Raw Pydantic — host-invariant metric for cross-run comparison

## core_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Simple Dump | 0.6 | 1.9 | 0.6 | **3.2x faster** | 1.00x |
| Simple Load | 2.0 | 5.6 | 0.7 | **2.8x faster** | 2.86x |
| Validated Load | 42.8 | 9.5 | 38.8 | 4.5x slower* | 1.10x |

> *See [Known Outliers](#known-outliers) for explanation*

## nested_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Deep Nested Load | 4.2 | 31.7 | 2.8 | **7.5x faster** | 1.50x |
| Nested Load | 2.4 | 11.1 | 1.1 | **4.6x faster** | 2.18x |

## pydantic_features

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Computed Field Dump | 5.1 | 2.3 | 0.7 | 2.2x slower* | 7.29x |
| Discriminated Union | 2.3 | 2.6 | 1.0 | **1.1x faster** | 2.30x |
| Enum Fields | 1.9 | 4.1 | 0.7 | **2.2x faster** | 2.71x |
| Field Aliases | 1.8 | 4.3 | 0.6 | **2.4x faster** | 3.00x |
| Field Validators | 2.1 | 4.8 | 0.8 | **2.3x faster** | 2.62x |
| Model Validators | 1.9 | 4.4 | 0.7 | **2.3x faster** | 2.71x |
| Union Types | 2.2 | 6.7 | 0.9 | **3.0x faster** | 2.44x |

> *See [Known Outliers](#known-outliers) for explanation*

## hooks_comparison

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Hooks | 3.0 | 6.8 | 0.7 | **2.3x faster** | 4.29x |

## batch_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Batch 100 | 165.5 | 464.3 | 31.2 | **2.8x faster** | 5.30x |
| Batch 1000 | 1632.7 | 4724.4 | 308.7 | **2.9x faster** | 5.29x |

## schema_options

| Benchmark | Median (µs) | Mean (µs) | StdDev | p95 (µs) | ops/s |
|-----------|------------|----------|--------|---------|-------|
| Partial Loading | 8.6 | 8.6 | 0.2 | 9.1 | 116,279 |
| Return Instance False | 2.5 | 2.6 | 0.1 | 2.7 | 399,997 |
| Return Instance True | 1.9 | 2.0 | 0.1 | 2.1 | 526,312 |
| Unknown Exclude | 2.2 | 2.2 | 0.1 | 2.4 | 454,542 |

## error_handling

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Validation Error | 7.5 | 8.9 | — | **1.2x faster** | — |

## type_coverage

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Collections | 2.6 | 20.7 | 1.1 | **8.0x faster** | 2.36x |
| Constrained | 2.2 | 8.2 | 0.8 | **3.7x faster** | 2.75x |
| Datetime | 2.1 | 9.1 | 0.8 | **4.3x faster** | 2.62x |
| Decimal | 2.3 | 6.0 | 1.0 | **2.6x faster** | 2.30x |
| Email Plain | 1.9 | 3.8 | — | **2.0x faster** | — |
| Email Validated | 40.9 | 5.1 | 38.3 | 8.0x slower* | 1.07x |
| Ip | 3.4 | 5.4 | 2.1 | **1.6x faster** | 1.62x |
| Kitchen Sink | 4.1 | 24.0 | 2.1 | **5.9x faster** | 1.95x |
| Optionals Full | 2.1 | 6.8 | 0.8 | **3.2x faster** | 2.63x |
| Optionals Sparse | 1.9 | 4.6 | 0.7 | **2.4x faster** | 2.71x |
| Scalars | 2.0 | 6.9 | 0.7 | **3.4x faster** | 2.86x |
| Url | 2.8 | 5.9 | 1.4 | **2.1x faster** | 2.00x |
| Uuid | 2.4 | 4.6 | 1.1 | **1.9x faster** | 2.18x |

> *See [Known Outliers](#known-outliers) for explanation*

## feature_coverage

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs MA | Overhead Ratio |
|-----------|------------|-----------------|-------------------|--------------|----------------|
| Hybrid Dump | 0.9 | 0.6 | 0.6 | 1.5x slower* | 1.50x |
| Hybrid Load | 2.3 | 2.1 | 0.8 | 1.1x slower | 2.88x |
| Metadata Rich | 2.1 | 7.6 | 0.8 | **3.6x faster** | 2.62x |

> *See [Known Outliers](#known-outliers) for explanation*

## schema_construction

| Benchmark | Median (µs) | Mean (µs) | StdDev | p95 (µs) | ops/s |
|-----------|------------|----------|--------|---------|-------|
| Constrained | 29.5 | 29.7 | 1.0 | 31.8 | 33,898 |
| Kitchen Sink | 66.8 | 66.8 | 1.9 | 70.6 | 14,970 |
| Metadata Rich | 29.5 | 29.6 | 0.8 | 31.1 | 33,898 |
| Nested | 25.3 | 25.3 | 0.8 | 26.8 | 39,526 |
| Simple | 26.1 | 26.2 | 1.0 | 28.1 | 38,314 |

---

## Known Outliers

| Benchmark | Bridge (µs) | Native MA (µs) | Why |
|-----------|------------|-----------------|-----|
| **Validated Load** | 42.8 | 9.5 | Uses `EmailStr` (RFC 5321) — see email_validated row. |
| **Email Validated** | 40.9 | 5.1 | Pydantic uses `email-validator` for RFC 5321 compliance; MA uses a regex. Bridge + raw Pydantic are nearly identical, confirming the cost is in Pydantic's validator, not the bridge. |
| **Computed Field Dump** | 5.1 | 2.3 | Same dump-path overhead, plus Pydantic `@computed_field` evaluation. |
| **Hybrid Dump** | 0.9 | 0.6 | Dump path overhead: `model_dump()` + MA serialization (0.9µs vs 0.6µs). |

---

## Key Insights

- **Load path is 1–8x faster** than native Marshmallow across all non-email scenarios
- **Nested/collection models** show the largest advantage (3–8x) because Pydantic's Rust engine handles nested validation in compiled code
- **Simple dump is ~3x faster** than native MA via fast-dump optimization; complex dumps (computed fields, hooks) are ~2x slower due to `model_dump()` + MA serialization overhead
- **Raw Pydantic** column shows the theoretical floor — bridge adds ~1.5µs of Marshmallow schema overhead on top of Pydantic's validation
- **Hook caching** (the load-path optimization) short-circuits Marshmallow hook machinery when no hooks are defined, saving ~1.5µs per load

---

## Cross-Run Stability (Overhead Ratios)

Absolute timings vary with host load, CPU frequency, and thermals. The **Overhead Ratio** (Bridge µs ÷ Raw Pydantic µs) cancels out host variance because both measurements experience the same conditions. Compare this column across runs to detect real regressions vs noise.

| Benchmark | Overhead Ratio | Bridge Overhead (µs) |
|-----------|----------------|----------------------|
| Computed Field Dump | 7.29x | +4.4 |
| Batch 100 | 5.30x | +134.3 |
| Batch 1000 | 5.29x | +1324.0 |
| Hooks | 4.29x | +2.3 |
| Field Aliases | 3.00x | +1.2 |
| Hybrid Load | 2.88x | +1.5 |
| Simple Load | 2.86x | +1.3 |
| Scalars | 2.86x | +1.3 |
| Constrained | 2.75x | +1.4 |
| Model Validators | 2.71x | +1.2 |
| Enum Fields | 2.71x | +1.2 |
| Optionals Sparse | 2.71x | +1.2 |
| Optionals Full | 2.63x | +1.3 |
| Field Validators | 2.62x | +1.3 |
| Datetime | 2.62x | +1.3 |
| Metadata Rich | 2.62x | +1.3 |
| Union Types | 2.44x | +1.3 |
| Collections | 2.36x | +1.5 |
| Decimal | 2.30x | +1.3 |
| Discriminated Union | 2.30x | +1.3 |
| Uuid | 2.18x | +1.3 |
| Nested Load | 2.18x | +1.3 |
| Url | 2.00x | +1.4 |
| Kitchen Sink | 1.95x | +2.0 |
| Ip | 1.62x | +1.3 |
| Deep Nested Load | 1.50x | +1.4 |
| Hybrid Dump | 1.50x | +0.3 |
| Validated Load | 1.10x | +4.0 |
| Email Validated | 1.07x | +2.6 |
| Simple Dump | 1.00x | +0.0 |

> **Average overhead ratio: 2.69x** — if this changes significantly between runs on different hosts, it indicates a real performance change, not host variance.

---

*Run `python -m benchmarks.run_benchmarks --report` to regenerate this report.*
