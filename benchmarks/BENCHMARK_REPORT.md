# Benchmark Report

**Generated:** 2026-03-15T21:17:46.162161+00:00  
**Git commit:** `674b021`  
**Python:** 3.11.6  
**Platform:** Windows-10-10.0.26200-SP0  
**Packages:** marshmallow 4.2.2, pydantic 2.12.5, marshmallow-pydantic 1.0.2.dev16
**Docker tests:** 2/2 passed (py311-ma3-pd-latest, py311-ma4-pd-latest)

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
| Simple Dump | 0.6 | 1.8 | 0.6 | **3.0x faster** |
| Simple Load | 2.0 | 4.8 | 0.7 | **2.4x faster** |
| Validated Load | 42.8 | 7.9 | 38.9 | 5.4x slower* |

> *See [Known Outliers](#known-outliers) for explanation*

## nested_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Deep Nested Load | 4.2 | 29.0 | 2.6 | **6.9x faster** |
| Nested Load | 2.3 | 10.4 | 1.1 | **4.5x faster** |

## pydantic_features

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Computed Field Dump | 5.0 | 2.1 | 0.7 | 2.4x slower* |
| Discriminated Union | 2.3 | 2.5 | 1.0 | **1.1x faster** |
| Enum Fields | 1.9 | 3.7 | 0.7 | **1.9x faster** |
| Field Aliases | 1.8 | 4.0 | 0.6 | **2.2x faster** |
| Field Validators | 2.1 | 4.6 | 0.8 | **2.2x faster** |
| Model Validators | 1.9 | 4.2 | 0.7 | **2.2x faster** |
| Union Types | 2.2 | 6.1 | 0.9 | **2.8x faster** |

> *See [Known Outliers](#known-outliers) for explanation*

## hooks_comparison

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Hooks | 3.2 | 6.6 | 0.7 | **2.1x faster** |

## batch_operations

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Batch 100 | 164.8 | 420.9 | 31.2 | **2.6x faster** |
| Batch 1000 | 1634.3 | 4241.7 | 308.7 | **2.6x faster** |

## schema_options

| Benchmark | Median (µs) | Mean (µs) | StdDev | p95 (µs) | ops/s |
|-----------|------------|----------|--------|---------|-------|
| Partial Loading | 8.6 | 8.6 | 0.3 | 9.2 | 116,279 |
| Return Instance False | 2.6 | 2.5 | 0.1 | 2.7 | 384,621 |
| Return Instance True | 1.9 | 1.9 | 0.1 | 2.1 | 526,312 |
| Unknown Exclude | 2.2 | 2.2 | 0.1 | 2.3 | 454,554 |

## error_handling

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Validation Error | 7.4 | 8.7 | — | **1.2x faster** |

## type_coverage

| Benchmark | Bridge (µs) | Native MA (µs) | Raw Pydantic (µs) | Bridge vs Native MA |
|-----------|------------|-----------------|-------------------|---------------------|
| Collections | 2.5 | 18.8 | 1.1 | **7.5x faster** |
| Constrained | 2.1 | 7.2 | 0.8 | **3.4x faster** |
| Datetime | 2.0 | 4.8 | 0.8 | **2.4x faster** |
| Decimal | 2.3 | 5.5 | 1.0 | **2.4x faster** |
| Email Plain | 1.8 | 3.5 | — | **1.9x faster** |
| Email Validated | 42.3 | 4.6 | 38.7 | 9.2x slower* |
| Ip | 3.4 | 5.0 | 2.1 | **1.5x faster** |
| Kitchen Sink | 4.0 | 19.2 | 2.0 | **4.8x faster** |
| Optionals Full | 2.0 | 6.2 | 0.7 | **3.1x faster** |
| Optionals Sparse | 1.8 | 4.3 | 0.7 | **2.4x faster** |
| Scalars | 2.0 | 6.2 | 0.7 | **3.1x faster** |
| Url | 2.7 | 5.7 | 1.3 | **2.1x faster** |
| Uuid | 2.3 | 4.3 | 1.0 | **1.9x faster** |

> *See [Known Outliers](#known-outliers) for explanation*

---

## Known Outliers

| Benchmark | Bridge (µs) | Native MA (µs) | Why |
|-----------|------------|-----------------|-----|
| **Validated Load** | 42.8 | 7.9 | Uses `EmailStr` (RFC 5321) — see email_validated row. |
| **Email Validated** | 42.3 | 4.6 | Pydantic uses `email-validator` for RFC 5321 compliance; MA uses a regex. Bridge + raw Pydantic are nearly identical, confirming the cost is in Pydantic's validator, not the bridge. |
| **Computed Field Dump** | 5.0 | 2.1 | Same dump-path overhead, plus Pydantic `@computed_field` evaluation. |

---

## Key Insights

- **Load path is 1–8x faster** than native Marshmallow across all non-email scenarios
- **Nested/collection models** show the largest advantage (3–8x) because Pydantic's Rust engine handles nested validation in compiled code
- **Simple dump is ~3x faster** than native MA via fast-dump optimization; complex dumps (computed fields, hooks) are ~2x slower due to `model_dump()` + MA serialization overhead
- **Raw Pydantic** column shows the theoretical floor — bridge adds ~1.6µs of Marshmallow schema overhead on top of Pydantic's validation
- **Hook caching** (the load-path optimization) short-circuits Marshmallow hook machinery when no hooks are defined, saving ~0.5µs per load

---

*Run `python -m benchmarks.run_benchmarks --report` to regenerate this report.*
