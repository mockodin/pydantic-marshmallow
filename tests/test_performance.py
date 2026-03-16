"""Performance benchmarks comparing Pydantic-bridge vs native Marshmallow.

Benchmarks are organized into three tiers:

1. **Bridge Overhead** — Isolates the bridge's own Python overhead using
   equivalent types on both sides (str vs str). This measures what the
   bridge itself costs.

2. **Real-World** — Uses Pydantic-native types like EmailStr that have
   no exact Marshmallow equivalent. EmailStr uses the email-validator
   library (RFC 5321 compliance, ~46us) while Marshmallow's Email field
   uses a simple regex (~9us). These benchmarks show what users actually
   experience.

3. **Multi-Type** — Exercises specific type categories (scalars,
   constrained, datetime, decimal, collections, optionals, nested) to
   show where the bridge performs well vs where Pydantic's deeper
   validation adds cost.

Run with: pytest tests/test_performance.py -v
"""

import time
from datetime import date, datetime
from decimal import Decimal

from marshmallow import Schema, fields as ma_fields, validate
from pydantic import BaseModel, EmailStr, Field

from pydantic_marshmallow import schema_for

# ============================================================================
# Tier 1: Bridge Overhead Models (equivalent types on both sides)
# ============================================================================

# --- Pydantic ---

class SimpleUserPydantic(BaseModel):
    """Simple user model — no constraints."""
    name: str
    age: int
    email: str


class ConstrainedUserPydantic(BaseModel):
    """User with constraints but NO Pydantic-specific types (no EmailStr)."""
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: str = Field(min_length=5, max_length=254)
    score: float = Field(ge=0, le=100)


# --- Marshmallow ---

class SimpleUserMarshmallow(Schema):
    """Simple user schema — no constraints."""
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    email = ma_fields.String(required=True)


class ConstrainedUserMarshmallow(Schema):
    """User with constraints equivalent to ConstrainedUserPydantic."""
    name = ma_fields.String(required=True, validate=validate.Length(min=1, max=100))
    age = ma_fields.Integer(required=True, validate=validate.Range(min=0, max=150))
    email = ma_fields.String(required=True, validate=validate.Length(min=5, max=254))
    score = ma_fields.Float(required=True, validate=validate.Range(min=0, max=100))


# ============================================================================
# Tier 2: Real-World Models (Pydantic-native types like EmailStr)
# ============================================================================

# --- Pydantic ---

class ValidatedUserPydantic(BaseModel):
    """User model with EmailStr — shows real-world Pydantic validation cost."""
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: EmailStr
    score: float = Field(ge=0, le=100)


class ComplexUserPydantic(BaseModel):
    """Complex user with EmailStr, Decimal, datetime, collections."""
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
    """Person with nested address and EmailStr."""
    name: str
    email: EmailStr
    address: AddressPydantic


# --- Marshmallow ---

class ValidatedUserMarshmallow(Schema):
    """User with Email field — the native Marshmallow equivalent."""
    name = ma_fields.String(required=True, validate=validate.Length(min=1, max=100))
    age = ma_fields.Integer(required=True, validate=validate.Range(min=0, max=150))
    email = ma_fields.Email(required=True)
    score = ma_fields.Float(required=True, validate=validate.Range(min=0, max=100))


class ComplexUserMarshmallow(Schema):
    """Complex user schema — native Marshmallow equivalent."""
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
    """Person with nested address — native Marshmallow equivalent."""
    name = ma_fields.String(required=True)
    email = ma_fields.Email(required=True)
    address = ma_fields.Nested(AddressMarshmallow, required=True)


# ============================================================================
# Tier 3: Multi-Type Models (one per type category)
# ============================================================================

# --- Scalars ---

class ScalarsPydantic(BaseModel):
    """Pure scalar types — str, int, float, bool."""
    label: str
    count: int
    ratio: float
    active: bool


class ScalarsMarshmallow(Schema):
    label = ma_fields.String(required=True)
    count = ma_fields.Integer(required=True)
    ratio = ma_fields.Float(required=True)
    active = ma_fields.Boolean(required=True)


# --- DateTime ---

class DateTimePydantic(BaseModel):
    """Temporal types — datetime, date."""
    name: str
    created_at: datetime
    birth_date: date


class DateTimeMarshmallow(Schema):
    name = ma_fields.String(required=True)
    created_at = ma_fields.DateTime(required=True)
    birth_date = ma_fields.Date(required=True)


# --- Decimal ---

class DecimalPydantic(BaseModel):
    """Decimal fields with precision."""
    name: str
    price: Decimal = Field(decimal_places=2)
    tax_rate: Decimal = Field(decimal_places=4)


class DecimalMarshmallow(Schema):
    name = ma_fields.String(required=True)
    price = ma_fields.Decimal(required=True, places=2)
    tax_rate = ma_fields.Decimal(required=True, places=4)


# --- Collections ---

class CollectionsPydantic(BaseModel):
    """List and dict types."""
    tags: list[str]
    scores: list[int]
    metadata: dict[str, str]


class CollectionsMarshmallow(Schema):
    tags = ma_fields.List(ma_fields.String(), required=True)
    scores = ma_fields.List(ma_fields.Integer(), required=True)
    metadata = ma_fields.Dict(keys=ma_fields.String(), values=ma_fields.String(), required=True)


# --- Optionals ---

class OptionalsPydantic(BaseModel):
    """Fields with Optional/None types."""
    name: str
    nickname: str | None = None
    age: int | None = None
    active: bool


class OptionalsMarshmallow(Schema):
    name = ma_fields.String(required=True)
    nickname = ma_fields.String(load_default=None, allow_none=True)
    age = ma_fields.Integer(load_default=None, allow_none=True)
    active = ma_fields.Boolean(required=True)


# --- Nested (equivalent on both sides — no EmailStr) ---

class InnerPydantic(BaseModel):
    street: str
    city: str
    zip_code: str = Field(pattern=r"^\d{5}$")


class NestedPydantic(BaseModel):
    """Two-level nesting with equivalent constraints."""
    name: str
    age: int
    address: InnerPydantic


class InnerMarshmallow(Schema):
    street = ma_fields.String(required=True)
    city = ma_fields.String(required=True)
    zip_code = ma_fields.String(required=True, validate=validate.Regexp(r"^\d{5}$"))


class NestedMarshmallow(Schema):
    name = ma_fields.String(required=True)
    age = ma_fields.Integer(required=True)
    address = ma_fields.Nested(InnerMarshmallow, required=True)


# --- Kitchen Sink (many types combined, NO EmailStr) ---

class KitchenSinkPydantic(BaseModel):
    """Combines scalars, constraints, datetime, decimal, collections, optionals, nested."""
    id: int
    name: str = Field(min_length=1, max_length=100)
    score: float = Field(ge=0, le=100)
    active: bool
    created_at: datetime
    birth_date: date
    balance: Decimal = Field(decimal_places=2)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    nickname: str | None = None
    address: InnerPydantic


class KitchenSinkMarshmallow(Schema):
    id = ma_fields.Integer(required=True)
    name = ma_fields.String(required=True, validate=validate.Length(min=1, max=100))
    score = ma_fields.Float(required=True, validate=validate.Range(min=0, max=100))
    active = ma_fields.Boolean(required=True)
    created_at = ma_fields.DateTime(required=True)
    birth_date = ma_fields.Date(required=True)
    balance = ma_fields.Decimal(required=True, places=2)
    tags = ma_fields.List(ma_fields.String(), load_default=[])
    metadata = ma_fields.Dict(keys=ma_fields.String(), values=ma_fields.String(), load_default={})
    nickname = ma_fields.String(load_default=None, allow_none=True)
    address = ma_fields.Nested(InnerMarshmallow, required=True)


# ============================================================================
# Test Data — Static dicts (one per model)
# ============================================================================

SIMPLE_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
}

CONSTRAINED_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
    "score": 95.5,
}

VALIDATED_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
    "score": 95.5,
}

COMPLEX_USER_DATA = {
    "id": 12345,
    "username": "alice_smith",
    "email": "alice@example.com",
    "age": 30,
    "balance": "1234.56",
    "tags": ["premium", "verified", "active"],
    "metadata": {"source": "signup", "campaign": "summer2024"},
    "created_at": "2024-01-15T10:30:00",
}

PERSON_WITH_ADDRESS_DATA = {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "address": {
        "street": "123 Main St",
        "city": "Boston",
        "country": "USA",
        "zip_code": "02101",
    },
}

SCALARS_DATA = {
    "label": "test-item",
    "count": 42,
    "ratio": 3.14,
    "active": True,
}

DATETIME_DATA = {
    "name": "Alice Smith",
    "created_at": "2024-01-15T10:30:00",
    "birth_date": "1994-06-15",
}

DECIMAL_DATA = {
    "name": "Widget",
    "price": "19.99",
    "tax_rate": "0.0825",
}

COLLECTIONS_DATA = {
    "tags": ["python", "marshmallow", "pydantic"],
    "scores": [95, 87, 92, 78, 100],
    "metadata": {"env": "prod", "region": "us-east", "tier": "premium"},
}

OPTIONALS_DATA = {
    "name": "Alice Smith",
    "nickname": None,
    "age": 30,
    "active": True,
}

OPTIONALS_SPARSE_DATA = {
    "name": "Bob Jones",
    "active": False,
}

NESTED_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "address": {
        "street": "123 Main St",
        "city": "Boston",
        "zip_code": "02101",
    },
}

KITCHEN_SINK_DATA = {
    "id": 99,
    "name": "Alice Smith",
    "score": 95.5,
    "active": True,
    "created_at": "2024-01-15T10:30:00",
    "birth_date": "1994-06-15",
    "balance": "1234.56",
    "tags": ["premium", "verified"],
    "metadata": {"source": "signup"},
    "nickname": "Ali",
    "address": {
        "street": "123 Main St",
        "city": "Boston",
        "zip_code": "02101",
    },
}

# Batch data for throughput tests
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
# Tier 1: Bridge Overhead Tests (equivalent types — isolates bridge cost)
# ============================================================================

class TestSimpleValidationPerformance:
    """Benchmark simple validation with no constraints (Tier 1: Overhead)."""

    def test_simple_pydantic_bridge(self):
        """Benchmark: Simple model via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)()
        for _ in range(10):
            schema.load(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), iterations=1000)
        print(f"\nPydantic Bridge (simple): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_simple_native_marshmallow(self):
        """Benchmark: Simple model via native Marshmallow."""
        schema = SimpleUserMarshmallow()
        for _ in range(10):
            schema.load(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(SIMPLE_USER_DATA), iterations=1000)
        print(f"\nNative Marshmallow (simple): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestConstrainedPerformance:
    """Benchmark constrained fields with equivalent types on both sides (Tier 1: Overhead)."""

    def test_constrained_pydantic_bridge(self):
        """Benchmark: Constrained model via Pydantic bridge (no EmailStr)."""
        schema = schema_for(ConstrainedUserPydantic)()
        for _ in range(10):
            schema.load(CONSTRAINED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(CONSTRAINED_USER_DATA), iterations=1000)
        print(f"\nPydantic Bridge (constrained, no EmailStr): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_constrained_native_marshmallow(self):
        """Benchmark: Constrained model via native Marshmallow."""
        schema = ConstrainedUserMarshmallow()
        for _ in range(10):
            schema.load(CONSTRAINED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(CONSTRAINED_USER_DATA), iterations=1000)
        print(f"\nNative Marshmallow (constrained): {avg_us:.2f} us/op")
        assert avg_us < 1000


# ============================================================================
# Tier 2: Real-World Tests (Pydantic-native types like EmailStr)
# ============================================================================

class TestValidatedPerformance:
    """Benchmark with EmailStr — real-world Pydantic validation cost (Tier 2: Real-World)."""

    def test_validated_pydantic_bridge(self):
        """Benchmark: Validated model via Pydantic bridge (includes EmailStr)."""
        schema = schema_for(ValidatedUserPydantic)()
        for _ in range(10):
            schema.load(VALIDATED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(VALIDATED_USER_DATA), iterations=1000)
        print(f"\nPydantic Bridge (validated+EmailStr): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_validated_native_marshmallow(self):
        """Benchmark: Validated model via native Marshmallow (Email regex)."""
        schema = ValidatedUserMarshmallow()
        for _ in range(10):
            schema.load(VALIDATED_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(VALIDATED_USER_DATA), iterations=1000)
        print(f"\nNative Marshmallow (validated+Email): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestComplexModelPerformance:
    """Benchmark complex models with EmailStr (Tier 2: Real-World)."""

    def test_complex_pydantic_bridge(self):
        """Benchmark: Complex model via Pydantic bridge."""
        schema = schema_for(ComplexUserPydantic)()
        for _ in range(10):
            schema.load(COMPLEX_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(COMPLEX_USER_DATA), iterations=1000)
        print(f"\nPydantic Bridge (complex+EmailStr): {avg_us:.2f} us/op")
        assert avg_us < 2000

    def test_complex_native_marshmallow(self):
        """Benchmark: Complex model via native Marshmallow."""
        schema = ComplexUserMarshmallow()
        for _ in range(10):
            schema.load(COMPLEX_USER_DATA)

        avg_us = timed_execution(lambda: schema.load(COMPLEX_USER_DATA), iterations=1000)
        print(f"\nNative Marshmallow (complex+Email): {avg_us:.2f} us/op")
        assert avg_us < 2000


class TestNestedModelPerformance:
    """Benchmark nested models with EmailStr (Tier 2: Real-World)."""

    def test_nested_pydantic_bridge(self):
        """Benchmark: Nested model via Pydantic bridge."""
        schema = schema_for(PersonWithAddressPydantic)()
        for _ in range(10):
            schema.load(PERSON_WITH_ADDRESS_DATA)

        avg_us = timed_execution(lambda: schema.load(PERSON_WITH_ADDRESS_DATA), iterations=1000)
        print(f"\nPydantic Bridge (nested+EmailStr): {avg_us:.2f} us/op")
        assert avg_us < 2000

    def test_nested_native_marshmallow(self):
        """Benchmark: Nested model via native Marshmallow."""
        schema = PersonWithAddressMarshmallow()
        for _ in range(10):
            schema.load(PERSON_WITH_ADDRESS_DATA)

        avg_us = timed_execution(lambda: schema.load(PERSON_WITH_ADDRESS_DATA), iterations=1000)
        print(f"\nNative Marshmallow (nested+Email): {avg_us:.2f} us/op")
        assert avg_us < 2000


# ============================================================================
# Tier 3: Multi-Type Tests (per-category type coverage)
# ============================================================================

class TestScalarPerformance:
    """Benchmark pure scalar types: str, int, float, bool (Tier 3: Multi-Type)."""

    def test_scalars_pydantic_bridge(self):
        schema = schema_for(ScalarsPydantic)()
        for _ in range(10):
            schema.load(SCALARS_DATA)

        avg_us = timed_execution(lambda: schema.load(SCALARS_DATA), iterations=1000)
        print(f"\nPydantic Bridge (scalars): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_scalars_native_marshmallow(self):
        schema = ScalarsMarshmallow()
        for _ in range(10):
            schema.load(SCALARS_DATA)

        avg_us = timed_execution(lambda: schema.load(SCALARS_DATA), iterations=1000)
        print(f"\nNative Marshmallow (scalars): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestDateTimePerformance:
    """Benchmark datetime and date types (Tier 3: Multi-Type)."""

    def test_datetime_pydantic_bridge(self):
        schema = schema_for(DateTimePydantic)()
        for _ in range(10):
            schema.load(DATETIME_DATA)

        avg_us = timed_execution(lambda: schema.load(DATETIME_DATA), iterations=1000)
        print(f"\nPydantic Bridge (datetime): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_datetime_native_marshmallow(self):
        schema = DateTimeMarshmallow()
        for _ in range(10):
            schema.load(DATETIME_DATA)

        avg_us = timed_execution(lambda: schema.load(DATETIME_DATA), iterations=1000)
        print(f"\nNative Marshmallow (datetime): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestDecimalPerformance:
    """Benchmark Decimal fields (Tier 3: Multi-Type)."""

    def test_decimal_pydantic_bridge(self):
        schema = schema_for(DecimalPydantic)()
        for _ in range(10):
            schema.load(DECIMAL_DATA)

        avg_us = timed_execution(lambda: schema.load(DECIMAL_DATA), iterations=1000)
        print(f"\nPydantic Bridge (decimal): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_decimal_native_marshmallow(self):
        schema = DecimalMarshmallow()
        for _ in range(10):
            schema.load(DECIMAL_DATA)

        avg_us = timed_execution(lambda: schema.load(DECIMAL_DATA), iterations=1000)
        print(f"\nNative Marshmallow (decimal): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestCollectionPerformance:
    """Benchmark list and dict types (Tier 3: Multi-Type)."""

    def test_collections_pydantic_bridge(self):
        schema = schema_for(CollectionsPydantic)()
        for _ in range(10):
            schema.load(COLLECTIONS_DATA)

        avg_us = timed_execution(lambda: schema.load(COLLECTIONS_DATA), iterations=1000)
        print(f"\nPydantic Bridge (collections): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_collections_native_marshmallow(self):
        schema = CollectionsMarshmallow()
        for _ in range(10):
            schema.load(COLLECTIONS_DATA)

        avg_us = timed_execution(lambda: schema.load(COLLECTIONS_DATA), iterations=1000)
        print(f"\nNative Marshmallow (collections): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestOptionalPerformance:
    """Benchmark optional/nullable types (Tier 3: Multi-Type)."""

    def test_optionals_full_pydantic_bridge(self):
        """All optional fields populated."""
        schema = schema_for(OptionalsPydantic)()
        for _ in range(10):
            schema.load(OPTIONALS_DATA)

        avg_us = timed_execution(lambda: schema.load(OPTIONALS_DATA), iterations=1000)
        print(f"\nPydantic Bridge (optionals, full): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_optionals_sparse_pydantic_bridge(self):
        """Optional fields omitted — tests default handling."""
        schema = schema_for(OptionalsPydantic)()
        for _ in range(10):
            schema.load(OPTIONALS_SPARSE_DATA)

        avg_us = timed_execution(lambda: schema.load(OPTIONALS_SPARSE_DATA), iterations=1000)
        print(f"\nPydantic Bridge (optionals, sparse): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_optionals_full_native_marshmallow(self):
        schema = OptionalsMarshmallow()
        for _ in range(10):
            schema.load(OPTIONALS_DATA)

        avg_us = timed_execution(lambda: schema.load(OPTIONALS_DATA), iterations=1000)
        print(f"\nNative Marshmallow (optionals, full): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_optionals_sparse_native_marshmallow(self):
        schema = OptionalsMarshmallow()
        for _ in range(10):
            schema.load(OPTIONALS_SPARSE_DATA)

        avg_us = timed_execution(lambda: schema.load(OPTIONALS_SPARSE_DATA), iterations=1000)
        print(f"\nNative Marshmallow (optionals, sparse): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestNestedEquivalentPerformance:
    """Benchmark 2-level nesting with equivalent types — no EmailStr (Tier 3: Multi-Type)."""

    def test_nested_equiv_pydantic_bridge(self):
        schema = schema_for(NestedPydantic)()
        for _ in range(10):
            schema.load(NESTED_DATA)

        avg_us = timed_execution(lambda: schema.load(NESTED_DATA), iterations=1000)
        print(f"\nPydantic Bridge (nested, no EmailStr): {avg_us:.2f} us/op")
        assert avg_us < 1000

    def test_nested_equiv_native_marshmallow(self):
        schema = NestedMarshmallow()
        for _ in range(10):
            schema.load(NESTED_DATA)

        avg_us = timed_execution(lambda: schema.load(NESTED_DATA), iterations=1000)
        print(f"\nNative Marshmallow (nested equiv): {avg_us:.2f} us/op")
        assert avg_us < 1000


class TestKitchenSinkPerformance:
    """Benchmark all type categories combined — no EmailStr (Tier 3: Multi-Type)."""

    def test_kitchen_sink_pydantic_bridge(self):
        schema = schema_for(KitchenSinkPydantic)()
        for _ in range(10):
            schema.load(KITCHEN_SINK_DATA)

        avg_us = timed_execution(lambda: schema.load(KITCHEN_SINK_DATA), iterations=1000)
        print(f"\nPydantic Bridge (kitchen sink): {avg_us:.2f} us/op")
        assert avg_us < 2000

    def test_kitchen_sink_native_marshmallow(self):
        schema = KitchenSinkMarshmallow()
        for _ in range(10):
            schema.load(KITCHEN_SINK_DATA)

        avg_us = timed_execution(lambda: schema.load(KITCHEN_SINK_DATA), iterations=1000)
        print(f"\nNative Marshmallow (kitchen sink): {avg_us:.2f} us/op")
        assert avg_us < 2000


# ============================================================================
# Batch + Dump Tests
# ============================================================================

class TestBatchPerformance:
    """Benchmark batch processing with many=True."""

    def test_batch_pydantic_bridge(self):
        """Benchmark: Batch loading via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)(many=True)
        for _ in range(5):
            schema.load(BATCH_SIMPLE_DATA)

        avg_us = timed_execution(lambda: schema.load(BATCH_SIMPLE_DATA), iterations=100)
        per_item = avg_us / len(BATCH_SIMPLE_DATA)
        print(f"\nPydantic Bridge (batch 100): {avg_us:.2f} us total, {per_item:.2f} us/item")
        assert per_item < 100

    def test_batch_native_marshmallow(self):
        """Benchmark: Batch loading via native Marshmallow."""
        schema = SimpleUserMarshmallow(many=True)
        for _ in range(5):
            schema.load(BATCH_SIMPLE_DATA)

        avg_us = timed_execution(lambda: schema.load(BATCH_SIMPLE_DATA), iterations=100)
        per_item = avg_us / len(BATCH_SIMPLE_DATA)
        print(f"\nNative Marshmallow (batch 100): {avg_us:.2f} us total, {per_item:.2f} us/item")
        assert per_item < 100


class TestDumpPerformance:
    """Benchmark serialization (dump) performance."""

    def test_dump_pydantic_bridge(self):
        """Benchmark: Dump via Pydantic bridge."""
        schema = schema_for(SimpleUserPydantic)()
        user = SimpleUserPydantic(**SIMPLE_USER_DATA)
        for _ in range(10):
            schema.dump(user)

        avg_us = timed_execution(lambda: schema.dump(user), iterations=1000)
        print(f"\nPydantic Bridge dump: {avg_us:.2f} us/op")
        assert avg_us < 500

    def test_dump_native_marshmallow(self):
        """Benchmark: Dump via native Marshmallow."""
        schema = SimpleUserMarshmallow()
        for _ in range(10):
            schema.dump(SIMPLE_USER_DATA)

        avg_us = timed_execution(lambda: schema.dump(SIMPLE_USER_DATA), iterations=1000)
        print(f"\nNative Marshmallow dump: {avg_us:.2f} us/op")
        assert avg_us < 500


# ============================================================================
# Comparison Summary
# ============================================================================

class TestComparisonSummary:
    """Generate a tiered comparison summary of all benchmarks."""

    def test_print_comparison_summary(self):
        """Print a formatted comparison of Pydantic bridge vs native Marshmallow."""
        overhead_results = {}
        realworld_results = {}
        multitype_results = {}

        # --- Tier 1: Bridge Overhead ---
        p = schema_for(SimpleUserPydantic)()
        m = SimpleUserMarshmallow()
        overhead_results["Simple (str/int)"] = {
            "bridge": timed_execution(lambda: p.load(SIMPLE_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(SIMPLE_USER_DATA), 1000),
        }

        p = schema_for(ConstrainedUserPydantic)()
        m = ConstrainedUserMarshmallow()
        overhead_results["Constrained (no EmailStr)"] = {
            "bridge": timed_execution(lambda: p.load(CONSTRAINED_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(CONSTRAINED_USER_DATA), 1000),
        }

        # --- Tier 2: Real-World ---
        p = schema_for(ValidatedUserPydantic)()
        m = ValidatedUserMarshmallow()
        realworld_results["Validated (EmailStr)"] = {
            "bridge": timed_execution(lambda: p.load(VALIDATED_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(VALIDATED_USER_DATA), 1000),
        }

        p = schema_for(ComplexUserPydantic)()
        m = ComplexUserMarshmallow()
        realworld_results["Complex (EmailStr+Decimal)"] = {
            "bridge": timed_execution(lambda: p.load(COMPLEX_USER_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(COMPLEX_USER_DATA), 1000),
        }

        p = schema_for(PersonWithAddressPydantic)()
        m = PersonWithAddressMarshmallow()
        realworld_results["Nested (EmailStr)"] = {
            "bridge": timed_execution(lambda: p.load(PERSON_WITH_ADDRESS_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(PERSON_WITH_ADDRESS_DATA), 1000),
        }

        # --- Tier 3: Multi-Type ---
        p = schema_for(ScalarsPydantic)()
        m = ScalarsMarshmallow()
        multitype_results["Scalars"] = {
            "bridge": timed_execution(lambda: p.load(SCALARS_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(SCALARS_DATA), 1000),
        }

        p = schema_for(DateTimePydantic)()
        m = DateTimeMarshmallow()
        multitype_results["DateTime"] = {
            "bridge": timed_execution(lambda: p.load(DATETIME_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(DATETIME_DATA), 1000),
        }

        p = schema_for(DecimalPydantic)()
        m = DecimalMarshmallow()
        multitype_results["Decimal"] = {
            "bridge": timed_execution(lambda: p.load(DECIMAL_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(DECIMAL_DATA), 1000),
        }

        p = schema_for(CollectionsPydantic)()
        m = CollectionsMarshmallow()
        multitype_results["Collections"] = {
            "bridge": timed_execution(lambda: p.load(COLLECTIONS_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(COLLECTIONS_DATA), 1000),
        }

        p = schema_for(OptionalsPydantic)()
        m = OptionalsMarshmallow()
        multitype_results["Optionals (full)"] = {
            "bridge": timed_execution(lambda: p.load(OPTIONALS_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(OPTIONALS_DATA), 1000),
        }

        p = schema_for(NestedPydantic)()
        m = NestedMarshmallow()
        multitype_results["Nested (equiv)"] = {
            "bridge": timed_execution(lambda: p.load(NESTED_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(NESTED_DATA), 1000),
        }

        p = schema_for(KitchenSinkPydantic)()
        m = KitchenSinkMarshmallow()
        multitype_results["Kitchen Sink"] = {
            "bridge": timed_execution(lambda: p.load(KITCHEN_SINK_DATA), 1000),
            "marshmallow": timed_execution(lambda: m.load(KITCHEN_SINK_DATA), 1000),
        }

        # --- Print ---
        header = f"{'Operation':<28} {'Bridge (us)':<14} {'MA (us)':<14} {'Ratio':<10}"
        sep = "-" * 70

        def print_section(title, results):
            print(f"\n  {title}")
            print(f"  {sep}")
            for op, t in results.items():
                ratio = t["marshmallow"] / t["bridge"] if t["bridge"] > 0 else 0
                marker = ">>" if ratio > 1 else ">!" if ratio > 0.8 else "!!"
                print(f"  {op:<28} {t['bridge']:<14.1f} {t['marshmallow']:<14.1f} {ratio:.2f}x {marker}")

        print("\n" + "=" * 70)
        print("PERFORMANCE COMPARISON: Pydantic Bridge vs Native Marshmallow")
        print("=" * 70)
        print(f"  {header}")

        print_section("TIER 1: Bridge Overhead (equivalent types)", overhead_results)
        print_section("TIER 2: Real-World (Pydantic-native types)", realworld_results)
        print_section("TIER 3: Per-Type Breakdown", multitype_results)

        print("\n" + "=" * 70)
        print("  >> = Bridge faster | >! = Within 20% | !! = Bridge slower")
        print("  Ratio > 1.0 means Bridge is faster than native Marshmallow")
        print("")
        print("  NOTE: Tier 2 'Real-World' benchmarks use EmailStr (RFC 5321")
        print("  via email-validator, ~46us) vs Marshmallow Email (regex, ~9us).")
        print("  The cost is in Pydantic's stricter validation, NOT the bridge.")
        print("=" * 70 + "\n")

        assert True
