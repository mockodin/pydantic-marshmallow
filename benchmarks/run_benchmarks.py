#!/usr/bin/env python
"""CLI tool for running marshmallow-pydantic benchmarks.

Usage:
    # Run all benchmarks
    python -m benchmarks.run_benchmarks

    # Save results to file
    python -m benchmarks.run_benchmarks --save results/latest.json

    # Compare with baseline
    python -m benchmarks.run_benchmarks --compare results/baseline.json

    # Run specific suite
    python -m benchmarks.run_benchmarks --suite validation

    # Set as new baseline
    python -m benchmarks.run_benchmarks --save results/baseline.json --baseline
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from enum import Enum
from pathlib import Path
from typing import Literal

from marshmallow import EXCLUDE, Schema, fields as ma_fields, post_load, pre_load, validate
from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

from pydantic_marshmallow import PydanticSchema, schema_for


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.benchmark_framework import (  # noqa: E402
    BenchmarkSuite,
    compare_results,
    format_comparison_table,
    format_results_table,
)


# =============================================================================
# Pydantic Models for Benchmarks
# =============================================================================


class SimpleUser(BaseModel):
    """Simple model with basic fields."""

    name: str
    age: int
    email: str


class ValidatedUser(BaseModel):
    """Model with Pydantic validation constraints."""

    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: EmailStr
    score: float = Field(ge=0, le=100)


class UserWithFieldValidators(BaseModel):
    """Model with custom field validators."""

    name: str
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip().title()


class UserWithComputedField(BaseModel):
    """Model with computed field."""

    first: str
    last: str
    age: int

    @computed_field  # type: ignore[misc]
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class DateRange(BaseModel):
    """Model with model validator for cross-field validation."""

    start: str
    end: str

    @model_validator(mode="after")
    def check_dates(self) -> DateRange:
        if self.end < self.start:
            raise ValueError("end must be after start")
        return self


class Address(BaseModel):
    """Nested model for address."""

    street: str
    city: str
    country: str
    zip_code: str


class PersonWithAddress(BaseModel):
    """Model with nested address."""

    name: str
    email: str
    address: Address


class Level3(BaseModel):
    """Deeply nested level 3."""

    value: str
    count: int


class Level2(BaseModel):
    """Deeply nested level 2."""

    name: str
    items: list[Level3]


class Level1(BaseModel):
    """Deeply nested level 1."""

    title: str
    sections: list[Level2]


class DeepRoot(BaseModel):
    """Root model with 4-level nesting."""

    id: int
    data: Level1


class Status(str, Enum):
    """Status enum."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class TaskWithEnum(BaseModel):
    """Model with enum field."""

    name: str
    status: Status


class FlexibleModel(BaseModel):
    """Model with Union type."""

    value: int | str
    items: list[str | int]


class ProductWithAlias(BaseModel):
    """Model with field aliases."""

    product_name: str = Field(alias="productName")
    unit_price: float = Field(alias="unitPrice")


class DiscriminatedBase(BaseModel):
    """Base for discriminated union."""

    type: str


class CatModel(DiscriminatedBase):
    """Cat variant."""

    type: Literal["cat"] = "cat"
    meow_volume: int


class DogModel(DiscriminatedBase):
    """Dog variant."""

    type: Literal["dog"] = "dog"
    bark_volume: int


class PetContainer(BaseModel):
    """Container with discriminated union."""

    pet: CatModel | DogModel = Field(discriminator="type")


# =============================================================================
# Marshmallow Schemas for Comparison
# =============================================================================


class SimpleUserMarshmallow(Schema):
    """Native Marshmallow simple schema."""

    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)


class ValidatedUserMarshmallow(Schema):
    """Native Marshmallow with validation."""

    name = ma_fields.String(required=True, validate=validate.Length(min=1, max=100))
    age = ma_fields.Integer(required=True, validate=validate.Range(min=0, max=150))
    email = ma_fields.Email(required=True)
    score = ma_fields.Float(required=True, validate=validate.Range(min=0, max=100))


class AddressMarshmallow(Schema):
    """Native Marshmallow address schema."""

    street = ma_fields.String(required=True)
    city = ma_fields.String(required=True)
    country = ma_fields.String(required=True)
    zip_code = ma_fields.String(required=True)


class PersonWithAddressMarshmallow(Schema):
    """Native Marshmallow person with nested address."""

    name = ma_fields.String(required=True)
    email = ma_fields.String(required=True)
    address = ma_fields.Nested(AddressMarshmallow, required=True)


class Level3Marshmallow(Schema):
    value = ma_fields.String(required=True)
    count = ma_fields.Integer(required=True)


class Level2Marshmallow(Schema):
    name = ma_fields.String(required=True)
    items = ma_fields.Nested(Level3Marshmallow, many=True)


class Level1Marshmallow(Schema):
    title = ma_fields.String(required=True)
    sections = ma_fields.Nested(Level2Marshmallow, many=True)


class DeepRootMarshmallow(Schema):
    id = ma_fields.Integer(required=True)
    data = ma_fields.Nested(Level1Marshmallow)


class SimpleUserWithHooksMarshmallow(Schema):
    """Marshmallow with hooks."""

    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)

    @pre_load
    def normalize(self, data, **kwargs):
        data["email"] = data.get("email", "").lower()
        return data

    @post_load
    def mark_processed(self, data, **kwargs):
        data["_processed"] = True
        return data


# =============================================================================
# PydanticSchema with hooks
# =============================================================================


class SimpleUserWithHooksSchema(PydanticSchema[SimpleUser]):
    """PydanticSchema with hooks for comparison."""

    class Meta:
        model = SimpleUser

    @pre_load
    def normalize(self, data, **kwargs):
        data["email"] = data.get("email", "").lower()
        return data


# =============================================================================
# Test Data
# =============================================================================

SIMPLE_DATA = {"name": "Alice Smith", "age": 30, "email": "alice@example.com"}

VALIDATED_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
    "score": 95.5,
}

NESTED_DATA = {
    "name": "Alice",
    "email": "alice@example.com",
    "address": {
        "street": "123 Main St",
        "city": "Boston",
        "country": "USA",
        "zip_code": "02101",
    },
}

DEEP_NESTED_DATA = {
    "id": 1,
    "data": {
        "title": "Report",
        "sections": [
            {
                "name": "Section 1",
                "items": [
                    {"value": "Item 1.1", "count": 10},
                    {"value": "Item 1.2", "count": 20},
                ],
            },
            {
                "name": "Section 2",
                "items": [{"value": "Item 2.1", "count": 30}],
            },
        ],
    },
}

COMPUTED_DATA = {"first": "Alice", "last": "Smith", "age": 30}

ENUM_DATA = {"name": "Task 1", "status": "active"}

UNION_DATA = {"value": 42, "items": ["a", 1, "b", 2]}

ALIAS_DATA = {"productName": "Widget", "unitPrice": 9.99}

DISCRIMINATED_DATA_CAT = {"pet": {"type": "cat", "meow_volume": 5}}
DISCRIMINATED_DATA_DOG = {"pet": {"type": "dog", "bark_volume": 10}}

# Batch data
BATCH_100 = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com"}
    for i in range(100)
]

BATCH_1000 = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com"}
    for i in range(1000)
]

# Invalid data for error handling
INVALID_DATA = {"name": "", "age": "not-a-number", "email": "invalid"}


# =============================================================================
# Benchmark Suite Definitions
# =============================================================================


def create_core_suite() -> BenchmarkSuite:
    """Create core benchmark suite for basic operations."""
    suite = BenchmarkSuite("core_operations", iterations=1000, warmup=100)

    # Simple load - Bridge
    simple_bridge_schema = schema_for(SimpleUser)()

    @suite.add("simple_load_bridge")
    def bench_simple_bridge():
        simple_bridge_schema.load(SIMPLE_DATA)

    # Simple load - Marshmallow
    simple_ma_schema = SimpleUserMarshmallow()

    @suite.add("simple_load_marshmallow")
    def bench_simple_marshmallow():
        simple_ma_schema.load(SIMPLE_DATA)

    # Simple load - Raw Pydantic (baseline)
    @suite.add("simple_load_raw_pydantic")
    def bench_raw_pydantic():
        SimpleUser.model_validate(SIMPLE_DATA)

    # Validated load - Bridge
    validated_bridge_schema = schema_for(ValidatedUser)()

    @suite.add("validated_load_bridge")
    def bench_validated_bridge():
        validated_bridge_schema.load(VALIDATED_DATA)

    # Validated load - Marshmallow
    validated_ma_schema = ValidatedUserMarshmallow()

    @suite.add("validated_load_marshmallow")
    def bench_validated_marshmallow():
        validated_ma_schema.load(VALIDATED_DATA)

    # Validated load - Raw Pydantic
    @suite.add("validated_load_raw_pydantic")
    def bench_validated_raw_pydantic():
        ValidatedUser.model_validate(VALIDATED_DATA)

    # Simple dump - Bridge
    simple_user = SimpleUser(**SIMPLE_DATA)

    @suite.add("simple_dump_bridge")
    def bench_dump_bridge():
        simple_bridge_schema.dump(simple_user)

    # Simple dump - Marshmallow
    @suite.add("simple_dump_marshmallow")
    def bench_dump_marshmallow():
        simple_ma_schema.dump(SIMPLE_DATA)

    # Simple dump - Raw Pydantic
    @suite.add("simple_dump_raw_pydantic")
    def bench_dump_raw_pydantic():
        simple_user.model_dump()

    return suite


def create_nested_suite() -> BenchmarkSuite:
    """Create benchmark suite for nested model operations."""
    suite = BenchmarkSuite("nested_operations", iterations=500, warmup=50)

    # Nested - Bridge
    nested_bridge_schema = schema_for(PersonWithAddress)()

    @suite.add("nested_load_bridge")
    def bench_nested_bridge():
        nested_bridge_schema.load(NESTED_DATA)

    # Nested - Marshmallow
    nested_ma_schema = PersonWithAddressMarshmallow()

    @suite.add("nested_load_marshmallow")
    def bench_nested_marshmallow():
        nested_ma_schema.load(NESTED_DATA)

    # Nested - Raw Pydantic
    @suite.add("nested_load_raw_pydantic")
    def bench_nested_raw_pydantic():
        PersonWithAddress.model_validate(NESTED_DATA)

    # Deep nested (4 levels) - Bridge
    deep_bridge_schema = schema_for(DeepRoot)()

    @suite.add("deep_nested_load_bridge")
    def bench_deep_bridge():
        deep_bridge_schema.load(DEEP_NESTED_DATA)

    # Deep nested - Marshmallow
    deep_ma_schema = DeepRootMarshmallow()

    @suite.add("deep_nested_load_marshmallow")
    def bench_deep_marshmallow():
        deep_ma_schema.load(DEEP_NESTED_DATA)

    # Deep nested - Raw Pydantic
    @suite.add("deep_nested_load_raw_pydantic")
    def bench_deep_raw_pydantic():
        DeepRoot.model_validate(DEEP_NESTED_DATA)

    return suite


def create_features_suite() -> BenchmarkSuite:
    """Create benchmark suite for Pydantic-specific features."""
    suite = BenchmarkSuite("pydantic_features", iterations=1000, warmup=100)

    # Field validators - Bridge
    validator_schema = schema_for(UserWithFieldValidators)()
    validator_data = {"name": "  alice  ", "email": "  ALICE@EXAMPLE.COM  "}

    @suite.add("field_validators_bridge")
    def bench_field_validators():
        validator_schema.load(validator_data)

    # Field validators - Raw Pydantic
    @suite.add("field_validators_raw_pydantic")
    def bench_field_validators_pydantic():
        UserWithFieldValidators.model_validate(validator_data)

    # Computed fields - Bridge
    computed_schema = schema_for(UserWithComputedField)()
    computed_model = UserWithComputedField(**COMPUTED_DATA)

    @suite.add("computed_field_dump_bridge")
    def bench_computed_dump():
        computed_schema.dump(computed_model)

    @suite.add("computed_field_dump_bridge_excluded")
    def bench_computed_excluded():
        computed_schema.dump(computed_model, include_computed=False)

    # Computed fields - Raw Pydantic
    @suite.add("computed_field_dump_raw_pydantic")
    def bench_computed_dump_pydantic():
        computed_model.model_dump()

    # Model validators - Bridge
    model_validator_schema = schema_for(DateRange)()
    date_data = {"start": "2024-01-01", "end": "2024-12-31"}

    @suite.add("model_validators_bridge")
    def bench_model_validators():
        model_validator_schema.load(date_data)

    # Model validators - Raw Pydantic
    @suite.add("model_validators_raw_pydantic")
    def bench_model_validators_pydantic():
        DateRange.model_validate(date_data)

    # Enum fields - Bridge
    enum_schema = schema_for(TaskWithEnum)()

    @suite.add("enum_fields_bridge")
    def bench_enum():
        enum_schema.load(ENUM_DATA)

    # Enum fields - Raw Pydantic
    @suite.add("enum_fields_raw_pydantic")
    def bench_enum_pydantic():
        TaskWithEnum.model_validate(ENUM_DATA)

    # Union types - Bridge
    union_schema = schema_for(FlexibleModel)()

    @suite.add("union_types_bridge")
    def bench_union():
        union_schema.load(UNION_DATA)

    # Union types - Raw Pydantic
    @suite.add("union_types_raw_pydantic")
    def bench_union_pydantic():
        FlexibleModel.model_validate(UNION_DATA)

    # Field aliases - Bridge
    alias_schema = schema_for(ProductWithAlias)()

    @suite.add("field_aliases_bridge")
    def bench_aliases():
        alias_schema.load(ALIAS_DATA)

    # Field aliases - Raw Pydantic
    @suite.add("field_aliases_raw_pydantic")
    def bench_aliases_pydantic():
        ProductWithAlias.model_validate(ALIAS_DATA)

    # Discriminated unions - Bridge
    discriminated_schema = schema_for(PetContainer)()

    @suite.add("discriminated_union_bridge")
    def bench_discriminated_cat():
        discriminated_schema.load(DISCRIMINATED_DATA_CAT)

    # Discriminated unions - Raw Pydantic
    @suite.add("discriminated_union_raw_pydantic")
    def bench_discriminated_pydantic():
        PetContainer.model_validate(DISCRIMINATED_DATA_CAT)

    return suite


def create_hooks_suite() -> BenchmarkSuite:
    """Create benchmark suite for hooks comparison."""
    suite = BenchmarkSuite("hooks_comparison", iterations=1000, warmup=100)

    # Bridge with hooks
    bridge_hooks_schema = SimpleUserWithHooksSchema()

    @suite.add("bridge_with_hooks")
    def bench_bridge_hooks():
        bridge_hooks_schema.load(SIMPLE_DATA)

    # Marshmallow with hooks
    ma_hooks_schema = SimpleUserWithHooksMarshmallow()

    @suite.add("marshmallow_with_hooks")
    def bench_ma_hooks():
        ma_hooks_schema.load(SIMPLE_DATA)

    # Bridge without hooks (for comparison)
    bridge_no_hooks = schema_for(SimpleUser)()

    @suite.add("bridge_no_hooks")
    def bench_bridge_no_hooks():
        bridge_no_hooks.load(SIMPLE_DATA)

    return suite


def create_batch_suite() -> BenchmarkSuite:
    """Create benchmark suite for batch operations."""
    from pydantic import TypeAdapter

    suite = BenchmarkSuite("batch_operations", iterations=100, warmup=10)

    # Batch 100 - Bridge
    bridge_batch_schema = schema_for(SimpleUser)(many=True)

    @suite.add("batch_100_bridge")
    def bench_batch_100_bridge():
        bridge_batch_schema.load(BATCH_100)

    # Batch 100 - Marshmallow
    ma_batch_schema = SimpleUserMarshmallow(many=True)

    @suite.add("batch_100_marshmallow")
    def bench_batch_100_marshmallow():
        ma_batch_schema.load(BATCH_100)

    # Batch 100 - Raw Pydantic (TypeAdapter)
    list_adapter = TypeAdapter(list[SimpleUser])

    @suite.add("batch_100_raw_pydantic")
    def bench_batch_100_pydantic():
        list_adapter.validate_python(BATCH_100)

    # Batch 1000 - Bridge
    @suite.add("batch_1000_bridge", iterations=20)
    def bench_batch_1000_bridge():
        bridge_batch_schema.load(BATCH_1000)

    # Batch 1000 - Marshmallow
    @suite.add("batch_1000_marshmallow", iterations=20)
    def bench_batch_1000_marshmallow():
        ma_batch_schema.load(BATCH_1000)

    # Batch 1000 - Raw Pydantic
    @suite.add("batch_1000_raw_pydantic", iterations=20)
    def bench_batch_1000_pydantic():
        list_adapter.validate_python(BATCH_1000)

    return suite


def create_options_suite() -> BenchmarkSuite:
    """Create benchmark suite for schema options."""
    suite = BenchmarkSuite("schema_options", iterations=1000, warmup=100)

    # return_instance=True (default)
    schema = schema_for(SimpleUser)()

    @suite.add("return_instance_true")
    def bench_return_true():
        schema.load(SIMPLE_DATA)

    # return_instance=False
    @suite.add("return_instance_false")
    def bench_return_false():
        schema.load(SIMPLE_DATA, return_instance=False)

    # Partial loading
    partial_data = {"name": "Alice"}

    @suite.add("partial_loading")
    def bench_partial():
        schema.load(partial_data, partial=True)

    # Unknown fields (EXCLUDE)
    schema_exclude = schema_for(SimpleUser)(unknown=EXCLUDE)
    data_with_unknown = {**SIMPLE_DATA, "extra": "ignored", "another": 123}

    @suite.add("unknown_exclude")
    def bench_unknown_exclude():
        schema_exclude.load(data_with_unknown)

    return suite


def create_error_suite() -> BenchmarkSuite:
    """Create benchmark suite for error handling."""
    suite = BenchmarkSuite("error_handling", iterations=500, warmup=50)

    # Bridge validation error
    bridge_schema = schema_for(SimpleUser)()

    @suite.add("validation_error_bridge")
    def bench_error_bridge():
        with contextlib.suppress(Exception):
            bridge_schema.load(INVALID_DATA)

    # Marshmallow validation error
    ma_schema = SimpleUserMarshmallow()

    @suite.add("validation_error_marshmallow")
    def bench_error_marshmallow():
        with contextlib.suppress(Exception):
            ma_schema.load(INVALID_DATA)

    return suite


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run benchmarks from command line."""
    parser = argparse.ArgumentParser(
        description="Run marshmallow-pydantic benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmarks.run_benchmarks
  python -m benchmarks.run_benchmarks --suite core nested
  python -m benchmarks.run_benchmarks --save results/latest.json
  python -m benchmarks.run_benchmarks --compare results/baseline.json
  python -m benchmarks.run_benchmarks --save results/baseline.json --baseline
        """,
    )

    parser.add_argument(
        "--suite",
        nargs="+",
        choices=["core", "nested", "features", "hooks", "batch", "options", "error", "all"],
        default=["all"],
        help="Benchmark suites to run (default: all)",
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--compare",
        type=str,
        help="Compare with baseline JSON file",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Mark saved results as baseline (copies to baseline.json)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="Only run benchmarks containing this string",
    )

    args = parser.parse_args()

    # Determine which suites to run
    suite_creators = {
        "core": create_core_suite,
        "nested": create_nested_suite,
        "features": create_features_suite,
        "hooks": create_hooks_suite,
        "batch": create_batch_suite,
        "options": create_options_suite,
        "error": create_error_suite,
    }

    if "all" in args.suite:
        suites_to_run = list(suite_creators.keys())
    else:
        suites_to_run = args.suite

    # Run benchmarks
    all_results = []
    for suite_name in suites_to_run:
        suite = suite_creators[suite_name]()
        results = suite.run(verbose=not args.quiet, filter_pattern=args.filter)
        all_results.append(results)

        if not args.quiet:
            print(format_results_table(results))

        # Save individual suite results
        if args.save:
            save_path = Path(args.save)
            suite_path = save_path.parent / f"{suite_name}_{save_path.name}"
            suite.save_results(suite_path)
            print(f"Saved {suite_name} results to: {suite_path}")

    # Compare with baseline if provided
    if args.compare:
        baseline_path = Path(args.compare)
        for results in all_results:
            suite_baseline = baseline_path.parent / f"{results.suite_name}_{baseline_path.name}"
            if suite_baseline.exists():
                comparisons = compare_results(suite_baseline, results)
                print(format_comparison_table(comparisons, show_all=True))

                # Check for regressions
                regressions = [c for c in comparisons.values() if c.is_regression]
                if regressions:
                    print(f"⚠️ Found {len(regressions)} regressions in {results.suite_name}")

    # Handle baseline flag
    if args.baseline and args.save:
        from shutil import copy

        save_path = Path(args.save)
        baseline_dir = save_path.parent
        for suite_name in suites_to_run:
            src = baseline_dir / f"{suite_name}_{save_path.name}"
            dst = baseline_dir / f"{suite_name}_baseline.json"
            if src.exists():
                copy(src, dst)
                print(f"Set baseline: {dst}")


if __name__ == "__main__":
    main()
