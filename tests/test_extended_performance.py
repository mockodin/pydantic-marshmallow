"""Extended performance benchmarks for marshmallow-pydantic.

Covers additional scenarios:
- With hooks (pre_load, post_load)
- With validators (field and schema)
- return_instance comparisons
- Computed fields in dump
- Error handling performance
- Large batch processing
- Deep nesting
- Partial loading
- Raw Pydantic baseline
"""

import time
from typing import List

from marshmallow import Schema, fields as ma_fields, post_load, pre_load, validate, validates
from pydantic import BaseModel, computed_field, field_validator

from pydantic_marshmallow import PydanticSchema, schema_for

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


def benchmark_comparison(name: str, pydantic_fn, marshmallow_fn, iterations: int = 1000):
    """Run benchmark and print comparison."""
    p_time = timed_execution(pydantic_fn, iterations)
    m_time = timed_execution(marshmallow_fn, iterations)
    ratio = m_time / p_time if p_time > 0 else 0

    print(f"\n{name}:")
    print(f"  Bridge:      {p_time:.2f} µs/op")
    print(f"  Marshmallow: {m_time:.2f} µs/op")
    print(f"  Ratio:       {ratio:.2f}x {'(faster)' if ratio > 1 else '(slower)'}")

    return p_time, m_time


# ============================================================================
# Models - Pydantic
# ============================================================================

class SimpleUser(BaseModel):
    name: str
    age: int
    email: str


class UserWithComputedField(BaseModel):
    first: str
    last: str
    age: int

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class UserWithPydanticValidators(BaseModel):
    name: str
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip().title()


class DeeplyNestedLevel3(BaseModel):
    value: str
    count: int


class DeeplyNestedLevel2(BaseModel):
    name: str
    items: List[DeeplyNestedLevel3]


class DeeplyNestedLevel1(BaseModel):
    title: str
    sections: List[DeeplyNestedLevel2]


class DeeplyNestedRoot(BaseModel):
    id: int
    data: DeeplyNestedLevel1


# ============================================================================
# Models - Marshmallow
# ============================================================================

class SimpleUserMarshmallow(Schema):
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)


class UserWithHooksMarshmallow(Schema):
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)

    @pre_load
    def normalize(self, data, **kwargs):
        data["email"] = data.get("email", "").lower()
        return data

    @post_load
    def make_user(self, data, **kwargs):
        data["processed"] = True
        return data


class UserWithValidatorsMarshmallow(Schema):
    name = ma_fields.String(required=True)
    email = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)

    @validates("email")
    def validate_email(self, value, **kwargs):
        if "@" not in value:
            raise validate.ValidationError("Invalid email")


class DeeplyNestedLevel3Marshmallow(Schema):
    value = ma_fields.String(required=True)
    count = ma_fields.Integer(required=True)


class DeeplyNestedLevel2Marshmallow(Schema):
    name = ma_fields.String(required=True)
    items = ma_fields.Nested(DeeplyNestedLevel3Marshmallow, many=True)


class DeeplyNestedLevel1Marshmallow(Schema):
    title = ma_fields.String(required=True)
    sections = ma_fields.Nested(DeeplyNestedLevel2Marshmallow, many=True)


class DeeplyNestedRootMarshmallow(Schema):
    id = ma_fields.Integer(required=True)
    data = ma_fields.Nested(DeeplyNestedLevel1Marshmallow)


# ============================================================================
# PydanticSchema with hooks
# ============================================================================

class UserWithHooksSchema(PydanticSchema[SimpleUser]):
    class Meta:
        model = SimpleUser

    @pre_load
    def normalize(self, data, **kwargs):
        data["email"] = data.get("email", "").lower()
        return data

    @post_load
    def process(self, data, **kwargs):
        return data


class UserWithValidatorsSchema(PydanticSchema[SimpleUser]):
    class Meta:
        model = SimpleUser

    @validates("name")
    def validate_name(self, value, **kwargs):
        if len(value) < 1:
            raise ValueError("Name required")


# ============================================================================
# Test Data
# ============================================================================

SIMPLE_USER_DATA = {"name": "Alice Smith", "age": 30, "email": "alice@example.com"}

COMPUTED_FIELD_DATA = {"first": "Alice", "last": "Smith", "age": 30}

DEEPLY_NESTED_DATA = {
    "id": 1,
    "data": {
        "title": "Report",
        "sections": [
            {
                "name": "Section 1",
                "items": [
                    {"value": "Item 1.1", "count": 10},
                    {"value": "Item 1.2", "count": 20},
                ]
            },
            {
                "name": "Section 2",
                "items": [
                    {"value": "Item 2.1", "count": 30},
                ]
            }
        ]
    }
}

# Large batch
LARGE_BATCH_DATA = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com"}
    for i in range(1000)
]

# Invalid data for error handling benchmarks
INVALID_DATA = {"name": "", "age": "not-a-number", "email": "invalid"}


# ============================================================================
# Performance Tests
# ============================================================================

class TestRawPydanticBaseline:
    """Benchmark raw Pydantic (no Marshmallow) as baseline."""

    def test_raw_pydantic_simple(self):
        """Benchmark: Raw Pydantic model_validate."""
        avg_us = timed_execution(lambda: SimpleUser.model_validate(SIMPLE_USER_DATA), 1000)
        print(f"\nRaw Pydantic (simple): {avg_us:.2f} µs/op")
        assert avg_us < 100  # Very fast

    def test_raw_pydantic_with_validators(self):
        """Benchmark: Raw Pydantic with field validators."""
        data = {"name": " alice ", "email": "ALICE@EXAMPLE.COM"}
        avg_us = timed_execution(
            lambda: UserWithPydanticValidators.model_validate(data), 1000
        )
        print(f"\nRaw Pydantic (with validators): {avg_us:.2f} µs/op")
        assert avg_us < 200


class TestHooksPerformance:
    """Benchmark with pre_load and post_load hooks."""

    def test_with_hooks_bridge(self):
        """Benchmark: Bridge with hooks."""
        schema = UserWithHooksSchema()
        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        print(f"\nBridge (with hooks): {avg_us:.2f} µs/op")
        assert avg_us < 200

    def test_with_hooks_marshmallow(self):
        """Benchmark: Native Marshmallow with hooks."""
        schema = UserWithHooksMarshmallow()
        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        print(f"\nMarshmallow (with hooks): {avg_us:.2f} µs/op")
        assert avg_us < 200

    def test_hooks_comparison(self):
        """Compare hooks performance."""
        bridge_schema = UserWithHooksSchema()
        ma_schema = UserWithHooksMarshmallow()

        benchmark_comparison(
            "With Hooks",
            lambda: bridge_schema.load(SIMPLE_USER_DATA),
            lambda: ma_schema.load(SIMPLE_USER_DATA),
        )


class TestValidatorsPerformance:
    """Benchmark with field validators."""

    def test_with_validators_bridge(self):
        """Benchmark: Bridge with Marshmallow validators."""
        schema = UserWithValidatorsSchema()
        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        print(f"\nBridge (with validators): {avg_us:.2f} µs/op")
        assert avg_us < 200

    def test_with_validators_marshmallow(self):
        """Benchmark: Native Marshmallow with validators."""
        schema = UserWithValidatorsMarshmallow()
        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        print(f"\nMarshmallow (with validators): {avg_us:.2f} µs/op")
        assert avg_us < 200


class TestReturnInstancePerformance:
    """Benchmark return_instance=True vs False."""

    def test_return_instance_true(self):
        """Benchmark: return_instance=True (default)."""
        schema = schema_for(SimpleUser)()
        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        print(f"\nreturn_instance=True: {avg_us:.2f} µs/op")
        assert avg_us < 200

    def test_return_instance_false(self):
        """Benchmark: return_instance=False."""
        schema = schema_for(SimpleUser)()
        avg_us = timed_execution(
            lambda: schema.load(SIMPLE_USER_DATA, return_instance=False), 1000
        )
        print(f"\nreturn_instance=False: {avg_us:.2f} µs/op")
        assert avg_us < 200

    def test_return_instance_comparison(self):
        """Compare return_instance modes."""
        schema = schema_for(SimpleUser)()

        t_instance = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), 1000)
        t_dict = timed_execution(
            lambda: schema.load(SIMPLE_USER_DATA, return_instance=False), 1000
        )

        print("\nreturn_instance comparison:")
        print(f"  True (model):  {t_instance:.2f} µs/op")
        print(f"  False (dict):  {t_dict:.2f} µs/op")
        print(f"  Difference:    {abs(t_instance - t_dict):.2f} µs")


class TestComputedFieldPerformance:
    """Benchmark computed field in dump."""

    def test_dump_with_computed(self):
        """Benchmark: dump with computed field."""
        schema = schema_for(UserWithComputedField)()
        user = UserWithComputedField(**COMPUTED_FIELD_DATA)

        avg_us = timed_execution(lambda: schema.dump(user), 1000)
        print(f"\nDump (with computed): {avg_us:.2f} µs/op")
        assert avg_us < 500

    def test_dump_without_computed(self):
        """Benchmark: dump without computed field."""
        schema = schema_for(UserWithComputedField)()
        user = UserWithComputedField(**COMPUTED_FIELD_DATA)

        avg_us = timed_execution(
            lambda: schema.dump(user, include_computed=False), 1000
        )
        print(f"\nDump (without computed): {avg_us:.2f} µs/op")
        assert avg_us < 500


class TestDeepNestingPerformance:
    """Benchmark deeply nested models (4 levels)."""

    def test_deep_nesting_bridge(self):
        """Benchmark: Bridge with 4-level nesting."""
        schema = schema_for(DeeplyNestedRoot)()
        avg_us = timed_execution(lambda: schema.load(DEEPLY_NESTED_DATA), 500)
        print(f"\nBridge (4-level nesting): {avg_us:.2f} µs/op")
        assert avg_us < 2000

    def test_deep_nesting_marshmallow(self):
        """Benchmark: Marshmallow with 4-level nesting."""
        schema = DeeplyNestedRootMarshmallow()
        avg_us = timed_execution(lambda: schema.load(DEEPLY_NESTED_DATA), 500)
        print(f"\nMarshmallow (4-level nesting): {avg_us:.2f} µs/op")
        assert avg_us < 2000


class TestLargeBatchPerformance:
    """Benchmark large batch processing (1000 items)."""

    def test_large_batch_bridge(self):
        """Benchmark: Bridge with 1000 items."""
        schema = schema_for(SimpleUser)(many=True)

        # Fewer iterations due to batch size
        avg_us = timed_execution(lambda: schema.load(LARGE_BATCH_DATA), 10)
        per_item = avg_us / len(LARGE_BATCH_DATA)

        print("\nBridge (1000 batch):")
        print(f"  Total: {avg_us:.2f} µs")
        print(f"  Per item: {per_item:.2f} µs")
        assert per_item < 100

    def test_large_batch_marshmallow(self):
        """Benchmark: Marshmallow with 1000 items."""
        schema = SimpleUserMarshmallow(many=True)

        avg_us = timed_execution(lambda: schema.load(LARGE_BATCH_DATA), 10)
        per_item = avg_us / len(LARGE_BATCH_DATA)

        print("\nMarshmallow (1000 batch):")
        print(f"  Total: {avg_us:.2f} µs")
        print(f"  Per item: {per_item:.2f} µs")
        assert per_item < 100


class TestPartialLoadingPerformance:
    """Benchmark partial loading."""

    def test_partial_loading(self):
        """Benchmark: partial=True loading."""
        schema = schema_for(SimpleUser)()
        partial_data = {"name": "Alice"}

        avg_us = timed_execution(
            lambda: schema.load(partial_data, partial=True), 1000
        )
        print(f"\nPartial loading: {avg_us:.2f} µs/op")
        assert avg_us < 200


class TestErrorHandlingPerformance:
    """Benchmark error handling (validation failures)."""

    def test_validation_failure_bridge(self):
        """Benchmark: Bridge validation failure."""
        schema = schema_for(SimpleUser)()

        def load_and_catch():
            try:
                schema.load(INVALID_DATA)
            except Exception:
                pass

        avg_us = timed_execution(load_and_catch, 500)
        print(f"\nBridge (validation failure): {avg_us:.2f} µs/op")
        assert avg_us < 500

    def test_validation_failure_marshmallow(self):
        """Benchmark: Marshmallow validation failure."""
        schema = SimpleUserMarshmallow()

        def load_and_catch():
            try:
                schema.load(INVALID_DATA)
            except Exception:
                pass

        avg_us = timed_execution(load_and_catch, 500)
        print(f"\nMarshmallow (validation failure): {avg_us:.2f} µs/op")
        assert avg_us < 500


class TestComprehensiveSummary:
    """Generate comprehensive benchmark summary."""

    def test_comprehensive_summary(self):
        """Print comprehensive performance comparison."""
        results = {}

        # Raw Pydantic baseline
        results["Raw Pydantic"] = {
            "bridge": timed_execution(lambda: SimpleUser.model_validate(SIMPLE_USER_DATA), 1000),
            "marshmallow": None,  # N/A
        }

        # Simple load
        bridge_simple = schema_for(SimpleUser)()
        ma_simple = SimpleUserMarshmallow()
        results["Simple Load"] = {
            "bridge": timed_execution(lambda: bridge_simple.load(SIMPLE_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: ma_simple.load(SIMPLE_USER_DATA), 1000),
        }

        # With hooks
        bridge_hooks = UserWithHooksSchema()
        ma_hooks = UserWithHooksMarshmallow()
        results["With Hooks"] = {
            "bridge": timed_execution(lambda: bridge_hooks.load(SIMPLE_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: ma_hooks.load(SIMPLE_USER_DATA), 1000),
        }

        # With validators
        bridge_val = UserWithValidatorsSchema()
        ma_val = UserWithValidatorsMarshmallow()
        results["With Validators"] = {
            "bridge": timed_execution(lambda: bridge_val.load(SIMPLE_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: ma_val.load(SIMPLE_USER_DATA), 1000),
        }

        # Deep nesting
        bridge_nested = schema_for(DeeplyNestedRoot)()
        ma_nested = DeeplyNestedRootMarshmallow()
        results["Deep Nested (4 levels)"] = {
            "bridge": timed_execution(lambda: bridge_nested.load(DEEPLY_NESTED_DATA), 500),
            "marshmallow": timed_execution(lambda: ma_nested.load(DEEPLY_NESTED_DATA), 500),
        }

        # Print summary
        print("\n" + "=" * 80)
        print("COMPREHENSIVE PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"{'Scenario':<25} {'Raw Pydantic':<15} {'Bridge':<15} {'Marshmallow':<15} {'Speedup':<10}")
        print("-" * 80)

        pydantic_baseline = results["Raw Pydantic"]["bridge"]

        for scenario, times in results.items():
            bridge = times["bridge"]
            marshmallow = times["marshmallow"]

            if marshmallow:
                speedup = marshmallow / bridge if bridge > 0 else 0
                symbol = "🚀" if speedup > 1 else "⚠️"
                print(f"{scenario:<25} {'-':<15} {bridge:<15.1f} {marshmallow:<15.1f} {speedup:.2f}x {symbol}")
            else:
                overhead = bridge / pydantic_baseline if pydantic_baseline > 0 else 0
                print(f"{scenario:<25} {bridge:<15.1f} {'-':<15} {'-':<15} (baseline)")

        print("=" * 80)
        print(f"Pydantic baseline: {pydantic_baseline:.1f} µs/op")
        print("Speedup > 1.0x means Bridge is faster than Marshmallow")
        print("=" * 80 + "\n")

        assert True  # Informational test
