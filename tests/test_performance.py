"""Performance benchmarks comparing Pydantic-bridge vs native Marshmallow.

These benchmarks measure validation speed to demonstrate the performance
benefits of using Pydantic's Rust-based validation core.

Run with: pytest tests/test_performance.py -v --benchmark-only
Or without pytest-benchmark: pytest tests/test_performance.py -v
"""

import time
from datetime import datetime
from decimal import Decimal

# Try to import pytest-benchmark, but make tests work without it
try:
    import pytest_benchmark
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False

from marshmallow import Schema, fields as ma_fields, validate
from pydantic import BaseModel, EmailStr, Field

from pydantic_marshmallow import schema_for

# ============================================================================
# Test Models - Pydantic
# ============================================================================

class SimpleUserPydantic(BaseModel):
    """Simple user model for basic benchmarks."""
    name: str
    age: int
    email: str


class ValidatedUserPydantic(BaseModel):
    """User model with validation constraints."""
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: EmailStr
    score: float = Field(ge=0, le=100)


class ComplexUserPydantic(BaseModel):
    """Complex user model with nested structures."""
    id: int
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    age: int = Field(ge=0)
    balance: Decimal = Field(decimal_places=2)
    tags: list[str] = Field(default_factory=list)
    metadata: dict | None = None
    created_at: datetime


class AddressPydantic(BaseModel):
    """Address model for nesting tests."""
    street: str
    city: str
    country: str
    zip_code: str = Field(pattern=r"^\d{5}$")


class PersonWithAddressPydantic(BaseModel):
    """Person with nested address."""
    name: str
    email: EmailStr
    address: AddressPydantic


# ============================================================================
# Test Models - Native Marshmallow
# ============================================================================

class SimpleUserMarshmallow(Schema):
    """Simple user schema for basic benchmarks."""
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)


class ValidatedUserMarshmallow(Schema):
    """User schema with validation constraints."""
    name = ma_fields.String(required=True, validate=validate.Length(min=1, max=100))
    age = ma_fields.Integer(required=True, validate=validate.Range(min=0, max=150))
    email = ma_fields.Email(required=True)
    score = ma_fields.Float(required=True, validate=validate.Range(min=0, max=100))


class ComplexUserMarshmallow(Schema):
    """Complex user schema with nested structures."""
    id = ma_fields.Integer(required=True)
    username = ma_fields.String(required=True, validate=validate.Length(min=3, max=50))
    email = ma_fields.Email(required=True)
    age = ma_fields.Integer(required=True, validate=validate.Range(min=0))
    balance = ma_fields.Decimal(required=True, places=2)
    tags = ma_fields.List(ma_fields.String(), load_default=[])
    metadata = ma_fields.Dict(load_default=None, allow_none=True)
    created_at = ma_fields.DateTime(required=True)


class AddressMarshmallow(Schema):
    """Address schema for nesting tests."""
    street = ma_fields.String(required=True)
    city = ma_fields.String(required=True)
    country = ma_fields.String(required=True)
    zip_code = ma_fields.String(required=True, validate=validate.Regexp(r"^\d{5}$"))


class PersonWithAddressMarshmallow(Schema):
    """Person with nested address."""
    name = ma_fields.String(required=True)
    email = ma_fields.Email(required=True)
    address = ma_fields.Nested(AddressMarshmallow, required=True)


# ============================================================================
# Test Data
# ============================================================================

SIMPLE_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com"
}

VALIDATED_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
    "score": 95.5
}

COMPLEX_USER_DATA = {
    "id": 12345,
    "username": "alice_smith",
    "email": "alice@example.com",
    "age": 30,
    "balance": "1234.56",
    "tags": ["premium", "verified", "active"],
    "metadata": {"source": "signup", "campaign": "summer2024"},
    "created_at": "2024-01-15T10:30:00"
}

PERSON_WITH_ADDRESS_DATA = {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "address": {
        "street": "123 Main St",
        "city": "Boston",
        "country": "USA",
        "zip_code": "02101"
    }
}

# Generate batch data for throughput tests
BATCH_SIMPLE_DATA = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com"}
    for i in range(100)
]

BATCH_VALIDATED_DATA = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com", "score": 50 + (i % 50)}
    for i in range(100)
]


# ============================================================================
# Benchmark Helper
# ============================================================================

def timed_execution(func, iterations: int = 1000):
    """Execute function multiple times and return average time in microseconds."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1_000_000  # Convert to microseconds


# ============================================================================
# Performance Tests (work with or without pytest-benchmark)
# ============================================================================

class TestSimpleValidationPerformance:
    """Benchmark simple validation with no constraints."""

    def test_simple_pydantic_bridge(self):
        """Benchmark: Simple model via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)()

        # Warm up
        for _ in range(10):
            schema.load(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), iterations=1000)

        print(f"\nPydantic Bridge (simple): {avg_us:.2f} µs/op")
        assert avg_us < 1000  # Should complete in under 1ms

    def test_simple_native_marshmallow(self):
        """Benchmark: Simple model via native Marshmallow."""
        schema = SimpleUserMarshmallow()

        # Warm up
        for _ in range(10):
            schema.load(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), iterations=1000)

        print(f"\nNative Marshmallow (simple): {avg_us:.2f} µs/op")
        assert avg_us < 1000  # Should complete in under 1ms


class TestValidatedPerformance:
    """Benchmark validation with constraints."""

    def test_validated_pydantic_bridge(self):
        """Benchmark: Validated model via Pydantic bridge."""
        schema = schema_for(ValidatedUserPydantic)()

        # Warm up
        for _ in range(10):
            schema.load(VALIDATED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(VALIDATED_USER_DATA), iterations=1000)

        print(f"\nPydantic Bridge (validated): {avg_us:.2f} µs/op")
        assert avg_us < 1000

    def test_validated_native_marshmallow(self):
        """Benchmark: Validated model via native Marshmallow."""
        schema = ValidatedUserMarshmallow()

        # Warm up
        for _ in range(10):
            schema.load(VALIDATED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(VALIDATED_USER_DATA), iterations=1000)

        print(f"\nNative Marshmallow (validated): {avg_us:.2f} µs/op")
        assert avg_us < 1000


class TestComplexModelPerformance:
    """Benchmark complex models with multiple field types."""

    def test_complex_pydantic_bridge(self):
        """Benchmark: Complex model via Pydantic bridge."""
        schema = schema_for(ComplexUserPydantic)()

        # Warm up
        for _ in range(10):
            schema.load(COMPLEX_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(COMPLEX_USER_DATA), iterations=1000)

        print(f"\nPydantic Bridge (complex): {avg_us:.2f} µs/op")
        assert avg_us < 2000

    def test_complex_native_marshmallow(self):
        """Benchmark: Complex model via native Marshmallow."""
        schema = ComplexUserMarshmallow()

        # Warm up
        for _ in range(10):
            schema.load(COMPLEX_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(COMPLEX_USER_DATA), iterations=1000)

        print(f"\nNative Marshmallow (complex): {avg_us:.2f} µs/op")
        assert avg_us < 2000


class TestNestedModelPerformance:
    """Benchmark nested model validation."""

    def test_nested_pydantic_bridge(self):
        """Benchmark: Nested model via Pydantic bridge."""
        schema = schema_for(PersonWithAddressPydantic)()

        # Warm up
        for _ in range(10):
            schema.load(PERSON_WITH_ADDRESS_DATA)

        avg_us = timed_execution(lambda: schema.load(PERSON_WITH_ADDRESS_DATA), iterations=1000)

        print(f"\nPydantic Bridge (nested): {avg_us:.2f} µs/op")
        assert avg_us < 2000

    def test_nested_native_marshmallow(self):
        """Benchmark: Nested model via native Marshmallow."""
        schema = PersonWithAddressMarshmallow()

        # Warm up
        for _ in range(10):
            schema.load(PERSON_WITH_ADDRESS_DATA)

        avg_us = timed_execution(lambda: schema.load(PERSON_WITH_ADDRESS_DATA), iterations=1000)

        print(f"\nNative Marshmallow (nested): {avg_us:.2f} µs/op")
        assert avg_us < 2000


class TestBatchPerformance:
    """Benchmark batch processing with many=True."""

    def test_batch_pydantic_bridge(self):
        """Benchmark: Batch loading via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)(many=True)

        # Warm up
        for _ in range(5):
            schema.load(BATCH_SIMPLE_DATA)

        avg_us = timed_execution(lambda: schema.load(BATCH_SIMPLE_DATA), iterations=100)

        per_item = avg_us / len(BATCH_SIMPLE_DATA)
        print(f"\nPydantic Bridge (batch 100): {avg_us:.2f} µs total, {per_item:.2f} µs/item")
        assert per_item < 100

    def test_batch_native_marshmallow(self):
        """Benchmark: Batch loading via native Marshmallow."""
        schema = SimpleUserMarshmallow(many=True)

        # Warm up
        for _ in range(5):
            schema.load(BATCH_SIMPLE_DATA)

        avg_us = timed_execution(lambda: schema.load(BATCH_SIMPLE_DATA), iterations=100)

        per_item = avg_us / len(BATCH_SIMPLE_DATA)
        print(f"\nNative Marshmallow (batch 100): {avg_us:.2f} µs total, {per_item:.2f} µs/item")
        assert per_item < 100


class TestDumpPerformance:
    """Benchmark serialization (dump) performance."""

    def test_dump_pydantic_bridge(self):
        """Benchmark: Dump via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)()
        user = SimpleUserPydantic(**SIMPLE_USER_DATA)

        # Warm up
        for _ in range(10):
            schema.dump(user)

        avg_us = timed_execution(lambda: schema.dump(user), iterations=1000)

        print(f"\nPydantic Bridge dump: {avg_us:.2f} µs/op")
        assert avg_us < 500

    def test_dump_native_marshmallow(self):
        """Benchmark: Dump via native Marshmallow."""
        schema = SimpleUserMarshmallow()

        # Warm up
        for _ in range(10):
            schema.dump(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.dump(SIMPLE_USER_DATA), iterations=1000)

        print(f"\nNative Marshmallow dump: {avg_us:.2f} µs/op")
        assert avg_us < 500


class TestComparisonSummary:
    """Generate a comparison summary of all benchmarks."""

    def test_print_comparison_summary(self):
        """Print a formatted comparison of Pydantic bridge vs native Marshmallow."""
        results = {}

        # Simple
        pydantic_schema = schema_for(SimpleUserPydantic)()
        marshmallow_schema = SimpleUserMarshmallow()

        results["Simple Load"] = {
            "pydantic": timed_execution(lambda: pydantic_schema.load(SIMPLE_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: marshmallow_schema.load(SIMPLE_USER_DATA), 1000),
        }

        # Validated
        pydantic_schema = schema_for(ValidatedUserPydantic)()
        marshmallow_schema = ValidatedUserMarshmallow()

        results["Validated Load"] = {
            "pydantic": timed_execution(lambda: pydantic_schema.load(VALIDATED_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: marshmallow_schema.load(VALIDATED_USER_DATA), 1000),
        }

        # Complex
        pydantic_schema = schema_for(ComplexUserPydantic)()
        marshmallow_schema = ComplexUserMarshmallow()

        results["Complex Load"] = {
            "pydantic": timed_execution(lambda: pydantic_schema.load(COMPLEX_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: marshmallow_schema.load(COMPLEX_USER_DATA), 1000),
        }

        # Nested
        pydantic_schema = schema_for(PersonWithAddressPydantic)()
        marshmallow_schema = PersonWithAddressMarshmallow()

        results["Nested Load"] = {
            "pydantic": timed_execution(lambda: pydantic_schema.load(PERSON_WITH_ADDRESS_DATA), 1000),
            "marshmallow": timed_execution(lambda: marshmallow_schema.load(PERSON_WITH_ADDRESS_DATA), 1000),
        }

        # Print summary
        print("\n" + "=" * 70)
        print("PERFORMANCE COMPARISON: Pydantic Bridge vs Native Marshmallow")
        print("=" * 70)
        print(f"{'Operation':<20} {'Pydantic (µs)':<15} {'Marshmallow (µs)':<17} {'Speedup':<10}")
        print("-" * 70)

        for op, times in results.items():
            speedup = times["marshmallow"] / times["pydantic"] if times["pydantic"] > 0 else 0
            faster = "🚀" if speedup > 1 else "⚠️"
            print(f"{op:<20} {times['pydantic']:<15.2f} {times['marshmallow']:<17.2f} {speedup:.2f}x {faster}")

        print("=" * 70)
        print("Note: Speedup > 1.0x means Pydantic bridge is faster")
        print("=" * 70 + "\n")

        # No assertion - this is informational
        assert True
