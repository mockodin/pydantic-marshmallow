# Benchmark Report

**Generated:** 2026-03-16T12:47:20.607467+00:00  
**Git commit:** `a9ebe50`  
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

## core_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Simple Dump | 0.6 | 1.9 | 0.6 | **3.2x faster** |
| Simple Load | 2.1 | 5.2 | 0.7 | **2.5x faster** |
| Validated Load | 42.7 | 8.9 | 38.6 | 4.8x slower* |

> *See [Known Outliers](#known-outliers) for explanation*

## nested_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Deep Nested Load | 4.1 | 32.5 | 2.7 | **7.9x faster** |
| Nested Load | 2.3 | 11.7 | 1.1 | **5.1x faster** |

## pydantic_features

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Computed Field Dump | 5.1 | 2.2 | 0.7 | 2.3x slower* |
| Discriminated Union | 2.3 | 2.6 | 1.0 | **1.1x faster** |
| Enum Fields | 1.9 | 4.0 | 0.7 | **2.1x faster** |
| Field Aliases | 1.8 | 4.3 | 0.6 | **2.4x faster** |
| Field Validators | 2.1 | 4.7 | 0.8 | **2.2x faster** |
| Model Validators | 1.9 | 4.4 | 0.7 | **2.3x faster** |
| Union Types | 2.2 | 6.6 | 0.9 | **3.0x faster** |

> *See [Known Outliers](#known-outliers) for explanation*

## hooks_comparison

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Hooks | 3.0 | 6.8 | 0.7 | **2.3x faster** |

## batch_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Batch 100 | 166.5 | 506.8 | 31.6 | **3.0x faster** |
| Batch 1000 | 1641.8 | 5019.1 | 310.8 | **3.1x faster** |

## schema_options

| Benchmark | Median (µs) | Mean (µs) | StdDev | p95 (µs) | ops/s |
|-----------|------------|----------|--------|---------|-------|
| Partial Loading | 8.6 | 8.6 | 0.3 | 9.2 | 116,279 |
| Return Instance False | 2.6 | 2.6 | 0.1 | 2.9 | 384,612 |
| Return Instance True | 2.0 | 2.0 | 0.1 | 2.1 | 499,996 |
| Unknown Exclude | 2.2 | 2.2 | 0.1 | 2.4 | 454,542 |

## error_handling

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Validation Error | 7.4 | 8.7 | — | **1.2x faster** |

## type_coverage

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Collections | 2.5 | 21.1 | 1.1 | **8.4x faster** |
| Constrained | 2.1 | 8.3 | 0.8 | **4.0x faster** |
| Datetime | 2.1 | 9.3 | 0.8 | **4.4x faster** |
| Decimal | 2.4 | 6.2 | 1.0 | **2.6x faster** |
| Email Plain | 1.9 | 3.8 | — | **2.0x faster** |
| Email Validated | 41.7 | 5.4 | 38.2 | 7.7x slower* |
| Ip | 3.4 | 5.4 | 2.1 | **1.6x faster** |
| Kitchen Sink | 4.1 | 24.3 | 2.0 | **5.9x faster** |
| Optionals Full | 2.0 | 13.4 | 0.8 | **6.7x faster** |
| Optionals Sparse | 1.9 | 4.5 | 0.7 | **2.4x faster** |
| Scalars | 2.0 | 6.8 | 0.7 | **3.4x faster** |
| Url | 2.7 | 6.1 | 1.4 | **2.3x faster** |
| Uuid | 2.4 | 4.5 | 1.1 | **1.9x faster** |

> *See [Known Outliers](#known-outliers) for explanation*

---

## Known Outliers

| Benchmark | Bridge (µs) | Native MA (µs) | Why |
|-----------|------------|-----------------|-----|
| **Validated Load** | 42.7 | 8.9 | Uses `EmailStr` (RFC 5321) — see email_validated row. |
| **Email Validated** | 41.7 | 5.4 | Pydantic uses `email-validator` for RFC 5321 compliance; MA uses a regex. Bridge + raw Pydantic are nearly identical, confirming the cost is in Pydantic's validator, not the bridge. |
| **Computed Field Dump** | 5.1 | 2.2 | Same dump-path overhead, plus Pydantic `@computed_field` evaluation. |

---

## Key Insights

- **Load path is 1–8x faster** than native Marshmallow across all non-email scenarios
- **Nested/collection models** show the largest advantage (3–8x) because Pydantic's Rust engine handles nested validation in compiled code
- **Simple dump is ~3x faster** than native MA via fast-dump optimization; complex dumps (computed fields, hooks) are ~2x slower due to `model_dump()` + MA serialization overhead
- **Raw Pydantic** column shows the theoretical floor — bridge adds ~1.6µs of Marshmallow schema overhead on top of Pydantic's validation
- **Hook caching** (the load-path optimization) short-circuits Marshmallow hook machinery when no hooks are defined, saving ~1.6µs per load

---

*Run `python -m benchmarks.run_benchmarks --report` to regenerate this report.*
