#!/usr/bin/env python
"""CLI tool for running pydantic-marshmallow benchmarks.

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
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal

from marshmallow import (
    EXCLUDE,
    Schema,
    fields as ma_fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)
from marshmallow.exceptions import ValidationError as MaValidationError
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    IPvAnyAddress,
    computed_field,
    field_validator,
    model_validator,
)

from pydantic_marshmallow import PydanticSchema, schema_for

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.benchmark_framework import (
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
# Type Coverage Pydantic Models
# =============================================================================


class ScalarModel(BaseModel):
    """All scalar types."""

    s: str
    i: int
    f: float
    b: bool


class DateTimeModel(BaseModel):
    """Temporal types."""

    dt: datetime
    d: date
    t: time


class DecimalModel(BaseModel):
    """Decimal/numeric precision types."""

    price: Decimal
    tax_rate: Decimal
    quantity: int


class IdentifierModel(BaseModel):
    """UUID and identifier types."""

    id: uuid.UUID
    name: str


class EmailModel(BaseModel):
    """EmailStr (RFC 5321 via email-validator)."""

    email: EmailStr
    name: str


class EmailPlainModel(BaseModel):
    """Plain str email (no validation) — for fair comparison."""

    email: str
    name: str


class UrlModel(BaseModel):
    """URL type."""

    homepage: HttpUrl
    name: str


class IpModel(BaseModel):
    """IP address type."""

    address: IPvAnyAddress
    label: str


class CollectionModel(BaseModel):
    """Collection types."""

    tags: list[str]
    scores: list[int]
    metadata: dict[str, str]
    unique_ids: list[int]


class OptionalModel(BaseModel):
    """Optional/nullable types."""

    required_name: str
    optional_name: str | None = None
    optional_age: int | None = None
    optional_score: float | None = None


class ConstrainedModel(BaseModel):
    """Constrained fields (Pydantic validators)."""

    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=150)
    score: float = Field(ge=0.0, le=100.0)
    code: str = Field(pattern=r"^[A-Z]{3}-\d{4}$")


class KitchenSinkModel(BaseModel):
    """All types combined."""

    name: str
    age: int
    score: float
    active: bool
    created: datetime
    birthday: date
    price: Decimal
    id: uuid.UUID
    tags: list[str]
    metadata: dict[str, str]
    nickname: str | None = None


# =============================================================================
# Type Coverage Marshmallow Schemas
# =============================================================================


class ScalarMarshmallow(Schema):
    s = ma_fields.String(required=True)
    i = ma_fields.Integer(required=True)
    f = ma_fields.Float(required=True)
    b = ma_fields.Boolean(required=True)


class DateTimeMarshmallow(Schema):
    dt = ma_fields.DateTime(required=True)
    d = ma_fields.Date(required=True)
    t = ma_fields.Time(required=True)


class DecimalMarshmallow(Schema):
    price = ma_fields.Decimal(required=True)
    tax_rate = ma_fields.Decimal(required=True)
    quantity = ma_fields.Integer(required=True)


class IdentifierMarshmallow(Schema):
    id = ma_fields.UUID(required=True)
    name = ma_fields.String(required=True)


class EmailMarshmallow(Schema):
    """Uses ma_fields.Email (regex)."""

    email = ma_fields.Email(required=True)
    name = ma_fields.String(required=True)


class EmailPlainMarshmallow(Schema):
    """Uses plain String — fair comparison with EmailPlainModel."""

    email = ma_fields.String(required=True)
    name = ma_fields.String(required=True)


class UrlMarshmallow(Schema):
    homepage = ma_fields.URL(required=True)
    name = ma_fields.String(required=True)


class IpMarshmallow(Schema):
    address = ma_fields.IP(required=True)
    label = ma_fields.String(required=True)


class CollectionMarshmallow(Schema):
    tags = ma_fields.List(ma_fields.String(), required=True)
    scores = ma_fields.List(ma_fields.Integer(), required=True)
    metadata = ma_fields.Dict(keys=ma_fields.String(), values=ma_fields.String(), required=True)
    unique_ids = ma_fields.List(ma_fields.Integer(), required=True)


class OptionalMarshmallow(Schema):
    required_name = ma_fields.String(required=True)
    optional_name = ma_fields.String(allow_none=True, load_default=None)
    optional_age = ma_fields.Integer(allow_none=True, load_default=None)
    optional_score = ma_fields.Float(allow_none=True, load_default=None)


class ConstrainedMarshmallow(Schema):
    """Equivalent constraints via Marshmallow validators."""

    name = ma_fields.String(
        required=True, validate=validate.Length(min=1, max=50)
    )
    age = ma_fields.Integer(
        required=True, validate=validate.Range(min=0, max=150)
    )
    score = ma_fields.Float(
        required=True, validate=validate.Range(min=0.0, max=100.0)
    )
    code = ma_fields.String(
        required=True, validate=validate.Regexp(r"^[A-Z]{3}-\d{4}$")
    )


class KitchenSinkMarshmallow(Schema):
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    score = ma_fields.Float(required=True)
    active = ma_fields.Boolean(required=True)
    created = ma_fields.DateTime(required=True)
    birthday = ma_fields.Date(required=True)
    price = ma_fields.Decimal(required=True)
    id = ma_fields.UUID(required=True)
    tags = ma_fields.List(ma_fields.String(), required=True)
    metadata = ma_fields.Dict(keys=ma_fields.String(), values=ma_fields.String(), required=True)
    nickname = ma_fields.String(allow_none=True, load_default=None)


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


class UserWithFieldValidatorsMarshmallow(Schema):
    """Marshmallow equivalent of UserWithFieldValidators."""

    name = ma_fields.String(required=True)
    email = ma_fields.String(required=True)

    @pre_load
    def normalize_fields(self, data, **kwargs):
        if "email" in data:
            data["email"] = data["email"].lower().strip()
        if "name" in data:
            data["name"] = data["name"].strip().title()
        return data


class ComputedFieldMarshmallow(Schema):
    """Marshmallow equivalent of UserWithComputedField (dump only)."""

    first = ma_fields.String(required=True)
    last = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    full_name = ma_fields.Method("get_full_name")

    def get_full_name(self, obj):
        if isinstance(obj, dict):
            return f"{obj['first']} {obj['last']}"
        return f"{obj.first} {obj.last}"


class DateRangeMarshmallow(Schema):
    """Marshmallow equivalent of DateRange (cross-field validation)."""

    start = ma_fields.String(required=True)
    end = ma_fields.String(required=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        if data.get("end", "") < data.get("start", ""):
            raise MaValidationError("end must be after start")


class TaskWithEnumMarshmallow(Schema):
    """Marshmallow equivalent of TaskWithEnum."""

    name = ma_fields.String(required=True)
    status = ma_fields.String(
        required=True,
        validate=validate.OneOf(["pending", "active", "completed"]),
    )


class FlexibleModelMarshmallow(Schema):
    """Marshmallow equivalent of FlexibleModel (Union → Raw)."""

    value = ma_fields.Raw(required=True)
    items = ma_fields.List(ma_fields.Raw(), required=True)


class ProductWithAliasMarshmallow(Schema):
    """Marshmallow equivalent of ProductWithAlias."""

    product_name = ma_fields.String(required=True, data_key="productName")
    unit_price = ma_fields.Float(required=True, data_key="unitPrice")


class PetContainerMarshmallow(Schema):
    """Marshmallow approximation of discriminated union (Raw field)."""

    pet = ma_fields.Raw(required=True)


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
# Type Coverage Test Data
# =============================================================================

SCALAR_DATA = {"s": "hello", "i": 42, "f": 3.14, "b": True}

DATETIME_DATA = {
    "dt": "2024-06-15T10:30:00",
    "d": "2024-06-15",
    "t": "10:30:00",
}

DECIMAL_DATA = {"price": "29.99", "tax_rate": "0.0825", "quantity": 5}

IDENTIFIER_DATA = {"id": "550e8400-e29b-41d4-a716-446655440000", "name": "Widget"}

EMAIL_VALIDATED_DATA = {"email": "alice@example.com", "name": "Alice"}

URL_DATA = {"homepage": "https://example.com/profile", "name": "Alice"}

IP_DATA = {"address": "192.168.1.1", "label": "router"}

COLLECTION_DATA = {
    "tags": ["python", "marshmallow", "pydantic"],
    "scores": [95, 87, 92, 78],
    "metadata": {"env": "prod", "region": "us-east"},
    "unique_ids": [1, 2, 3, 4, 5],
}

OPTIONAL_FULL_DATA = {
    "required_name": "Alice",
    "optional_name": "Ali",
    "optional_age": 30,
    "optional_score": 95.5,
}

OPTIONAL_SPARSE_DATA = {"required_name": "Bob"}

CONSTRAINED_DATA = {
    "name": "Alice",
    "age": 30,
    "score": 95.5,
    "code": "ABC-1234",
}

KITCHEN_SINK_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "score": 95.5,
    "active": True,
    "created": "2024-06-15T10:30:00",
    "birthday": "1994-03-22",
    "price": "29.99",
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "tags": ["python", "dev"],
    "metadata": {"role": "admin"},
    "nickname": None,
}


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

    # --- Field validators ---
    validator_schema = schema_for(UserWithFieldValidators)()
    validator_ma = UserWithFieldValidatorsMarshmallow()
    validator_data = {"name": "  alice  ", "email": "  ALICE@EXAMPLE.COM  "}

    @suite.add("field_validators_bridge")
    def bench_field_validators():
        validator_schema.load(validator_data)

    @suite.add("field_validators_marshmallow")
    def bench_field_validators_ma():
        validator_ma.load(validator_data)

    @suite.add("field_validators_raw_pydantic")
    def bench_field_validators_pydantic():
        UserWithFieldValidators.model_validate(validator_data)

    # --- Computed fields (dump) ---
    computed_schema = schema_for(UserWithComputedField)()
    computed_ma = ComputedFieldMarshmallow()
    computed_model = UserWithComputedField(**COMPUTED_DATA)

    @suite.add("computed_field_dump_bridge")
    def bench_computed_dump():
        computed_schema.dump(computed_model)

    @suite.add("computed_field_dump_marshmallow")
    def bench_computed_dump_ma():
        computed_ma.dump(COMPUTED_DATA)

    @suite.add("computed_field_dump_raw_pydantic")
    def bench_computed_dump_pydantic():
        computed_model.model_dump()

    # --- Model validators (cross-field) ---
    model_validator_schema = schema_for(DateRange)()
    model_validator_ma = DateRangeMarshmallow()
    date_data = {"start": "2024-01-01", "end": "2024-12-31"}

    @suite.add("model_validators_bridge")
    def bench_model_validators():
        model_validator_schema.load(date_data)

    @suite.add("model_validators_marshmallow")
    def bench_model_validators_ma():
        model_validator_ma.load(date_data)

    @suite.add("model_validators_raw_pydantic")
    def bench_model_validators_pydantic():
        DateRange.model_validate(date_data)

    # --- Enum fields ---
    enum_schema = schema_for(TaskWithEnum)()
    enum_ma = TaskWithEnumMarshmallow()

    @suite.add("enum_fields_bridge")
    def bench_enum():
        enum_schema.load(ENUM_DATA)

    @suite.add("enum_fields_marshmallow")
    def bench_enum_ma():
        enum_ma.load(ENUM_DATA)

    @suite.add("enum_fields_raw_pydantic")
    def bench_enum_pydantic():
        TaskWithEnum.model_validate(ENUM_DATA)

    # --- Union types ---
    union_schema = schema_for(FlexibleModel)()
    union_ma = FlexibleModelMarshmallow()

    @suite.add("union_types_bridge")
    def bench_union():
        union_schema.load(UNION_DATA)

    @suite.add("union_types_marshmallow")
    def bench_union_ma():
        union_ma.load(UNION_DATA)

    @suite.add("union_types_raw_pydantic")
    def bench_union_pydantic():
        FlexibleModel.model_validate(UNION_DATA)

    # --- Field aliases ---
    alias_schema = schema_for(ProductWithAlias)()
    alias_ma = ProductWithAliasMarshmallow()

    @suite.add("field_aliases_bridge")
    def bench_aliases():
        alias_schema.load(ALIAS_DATA)

    @suite.add("field_aliases_marshmallow")
    def bench_aliases_ma():
        alias_ma.load(ALIAS_DATA)

    @suite.add("field_aliases_raw_pydantic")
    def bench_aliases_pydantic():
        ProductWithAlias.model_validate(ALIAS_DATA)

    # --- Discriminated unions ---
    discriminated_schema = schema_for(PetContainer)()
    discriminated_ma = PetContainerMarshmallow()

    @suite.add("discriminated_union_bridge")
    def bench_discriminated_cat():
        discriminated_schema.load(DISCRIMINATED_DATA_CAT)

    @suite.add("discriminated_union_marshmallow")
    def bench_discriminated_ma():
        discriminated_ma.load(DISCRIMINATED_DATA_CAT)

    @suite.add("discriminated_union_raw_pydantic")
    def bench_discriminated_pydantic():
        PetContainer.model_validate(DISCRIMINATED_DATA_CAT)

    return suite


def create_hooks_suite() -> BenchmarkSuite:
    """Create benchmark suite for hooks comparison."""
    suite = BenchmarkSuite("hooks_comparison", iterations=1000, warmup=100)

    # Bridge with hooks
    bridge_hooks_schema = SimpleUserWithHooksSchema()

    @suite.add("hooks_bridge")
    def bench_bridge_hooks():
        bridge_hooks_schema.load(SIMPLE_DATA)

    # Marshmallow with hooks
    ma_hooks_schema = SimpleUserWithHooksMarshmallow()

    @suite.add("hooks_marshmallow")
    def bench_ma_hooks():
        ma_hooks_schema.load(SIMPLE_DATA)

    # Raw Pydantic (no hooks — shows the validation floor)
    @suite.add("hooks_raw_pydantic")
    def bench_raw_pydantic():
        SimpleUser.model_validate(SIMPLE_DATA)

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


def create_type_coverage_suite() -> BenchmarkSuite:
    """Create benchmark suite covering all supported type categories."""
    suite = BenchmarkSuite("type_coverage", iterations=1000, warmup=100)

    # --- Scalars ---
    scalar_bridge = schema_for(ScalarModel)()
    scalar_ma = ScalarMarshmallow()

    @suite.add("scalars_bridge")
    def bench_scalars_bridge():
        scalar_bridge.load(SCALAR_DATA)

    @suite.add("scalars_marshmallow")
    def bench_scalars_ma():
        scalar_ma.load(SCALAR_DATA)

    @suite.add("scalars_raw_pydantic")
    def bench_scalars_pydantic():
        ScalarModel.model_validate(SCALAR_DATA)

    # --- DateTime ---
    datetime_bridge = schema_for(DateTimeModel)()
    datetime_ma = DateTimeMarshmallow()

    @suite.add("datetime_bridge")
    def bench_datetime_bridge():
        datetime_bridge.load(DATETIME_DATA)

    @suite.add("datetime_marshmallow")
    def bench_datetime_ma():
        datetime_ma.load(DATETIME_DATA)

    @suite.add("datetime_raw_pydantic")
    def bench_datetime_pydantic():
        DateTimeModel.model_validate(DATETIME_DATA)

    # --- Decimal ---
    decimal_bridge = schema_for(DecimalModel)()
    decimal_ma = DecimalMarshmallow()

    @suite.add("decimal_bridge")
    def bench_decimal_bridge():
        decimal_bridge.load(DECIMAL_DATA)

    @suite.add("decimal_marshmallow")
    def bench_decimal_ma():
        decimal_ma.load(DECIMAL_DATA)

    @suite.add("decimal_raw_pydantic")
    def bench_decimal_pydantic():
        DecimalModel.model_validate(DECIMAL_DATA)

    # --- Identifiers (UUID) ---
    id_bridge = schema_for(IdentifierModel)()
    id_ma = IdentifierMarshmallow()

    @suite.add("uuid_bridge")
    def bench_uuid_bridge():
        id_bridge.load(IDENTIFIER_DATA)

    @suite.add("uuid_marshmallow")
    def bench_uuid_ma():
        id_ma.load(IDENTIFIER_DATA)

    @suite.add("uuid_raw_pydantic")
    def bench_uuid_pydantic():
        IdentifierModel.model_validate(IDENTIFIER_DATA)

    # --- Email (RFC 5321 vs regex) ---
    email_bridge = schema_for(EmailModel)()
    email_ma = EmailMarshmallow()

    @suite.add("email_validated_bridge")
    def bench_email_bridge():
        email_bridge.load(EMAIL_VALIDATED_DATA)

    @suite.add("email_validated_marshmallow")
    def bench_email_ma():
        email_ma.load(EMAIL_VALIDATED_DATA)

    @suite.add("email_validated_raw_pydantic")
    def bench_email_pydantic():
        EmailModel.model_validate(EMAIL_VALIDATED_DATA)

    # --- Email (plain str vs str — fair comparison) ---
    email_plain_bridge = schema_for(EmailPlainModel)()
    email_plain_ma = EmailPlainMarshmallow()

    @suite.add("email_plain_bridge")
    def bench_email_plain_bridge():
        email_plain_bridge.load(EMAIL_VALIDATED_DATA)

    @suite.add("email_plain_marshmallow")
    def bench_email_plain_ma():
        email_plain_ma.load(EMAIL_VALIDATED_DATA)

    # --- URL ---
    url_bridge = schema_for(UrlModel)()
    url_ma = UrlMarshmallow()

    @suite.add("url_bridge")
    def bench_url_bridge():
        url_bridge.load(URL_DATA)

    @suite.add("url_marshmallow")
    def bench_url_ma():
        url_ma.load(URL_DATA)

    @suite.add("url_raw_pydantic")
    def bench_url_pydantic():
        UrlModel.model_validate(URL_DATA)

    # --- IP Address ---
    ip_bridge = schema_for(IpModel)()
    ip_ma = IpMarshmallow()

    @suite.add("ip_bridge")
    def bench_ip_bridge():
        ip_bridge.load(IP_DATA)

    @suite.add("ip_marshmallow")
    def bench_ip_ma():
        ip_ma.load(IP_DATA)

    @suite.add("ip_raw_pydantic")
    def bench_ip_pydantic():
        IpModel.model_validate(IP_DATA)

    # --- Collections ---
    coll_bridge = schema_for(CollectionModel)()
    coll_ma = CollectionMarshmallow()

    @suite.add("collections_bridge")
    def bench_coll_bridge():
        coll_bridge.load(COLLECTION_DATA)

    @suite.add("collections_marshmallow")
    def bench_coll_ma():
        coll_ma.load(COLLECTION_DATA)

    @suite.add("collections_raw_pydantic")
    def bench_coll_pydantic():
        CollectionModel.model_validate(COLLECTION_DATA)

    # --- Optionals (full data) ---
    opt_bridge = schema_for(OptionalModel)()
    opt_ma = OptionalMarshmallow()

    @suite.add("optionals_full_bridge")
    def bench_opt_full_bridge():
        opt_bridge.load(OPTIONAL_FULL_DATA)

    @suite.add("optionals_full_marshmallow")
    def bench_opt_full_ma():
        opt_ma.load(OPTIONAL_FULL_DATA)

    @suite.add("optionals_full_raw_pydantic")
    def bench_opt_full_pydantic():
        OptionalModel.model_validate(OPTIONAL_FULL_DATA)

    # --- Optionals (sparse data) ---
    @suite.add("optionals_sparse_bridge")
    def bench_opt_sparse_bridge():
        opt_bridge.load(OPTIONAL_SPARSE_DATA)

    @suite.add("optionals_sparse_marshmallow")
    def bench_opt_sparse_ma():
        opt_ma.load(OPTIONAL_SPARSE_DATA)

    @suite.add("optionals_sparse_raw_pydantic")
    def bench_opt_sparse_pydantic():
        OptionalModel.model_validate(OPTIONAL_SPARSE_DATA)

    # --- Constrained (Pydantic Rust vs MA Python validators) ---
    constr_bridge = schema_for(ConstrainedModel)()
    constr_ma = ConstrainedMarshmallow()

    @suite.add("constrained_bridge")
    def bench_constr_bridge():
        constr_bridge.load(CONSTRAINED_DATA)

    @suite.add("constrained_marshmallow")
    def bench_constr_ma():
        constr_ma.load(CONSTRAINED_DATA)

    @suite.add("constrained_raw_pydantic")
    def bench_constr_pydantic():
        ConstrainedModel.model_validate(CONSTRAINED_DATA)

    # --- Kitchen Sink (all types combined) ---
    ks_bridge = schema_for(KitchenSinkModel)()
    ks_ma = KitchenSinkMarshmallow()

    @suite.add("kitchen_sink_bridge")
    def bench_ks_bridge():
        ks_bridge.load(KITCHEN_SINK_DATA)

    @suite.add("kitchen_sink_marshmallow")
    def bench_ks_ma():
        ks_ma.load(KITCHEN_SINK_DATA)

    @suite.add("kitchen_sink_raw_pydantic")
    def bench_ks_pydantic():
        KitchenSinkModel.model_validate(KITCHEN_SINK_DATA)

    return suite


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run benchmarks from command line."""
    parser = argparse.ArgumentParser(
        description="Run pydantic-marshmallow benchmarks",
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
        choices=["core", "nested", "features", "hooks", "batch", "options", "error", "types", "all"],
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
    parser.add_argument(
        "--report",
        type=str,
        nargs="?",
        const="benchmarks/BENCHMARK_REPORT.md",
        help="Generate markdown report (default: benchmarks/BENCHMARK_REPORT.md)",
    )
    parser.add_argument(
        "--docker-status",
        type=str,
        default=None,
        help="Docker test status string to include in report header",
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
        "types": create_type_coverage_suite,
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

    # Generate markdown report
    if args.report:
        from benchmarks.benchmark_framework import format_markdown_report

        report_path = Path(args.report)
        report = format_markdown_report(
            all_results, docker_status=args.docker_status
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
