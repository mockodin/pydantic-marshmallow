"""Shared test fixtures for marshmallow-pydantic tests.

This module provides reusable models, schemas, and test data to eliminate
duplication across test files. Import fixtures and models from here rather
than redefining them in each test file.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import pytest
from marshmallow import post_load, pre_load, validates, validates_schema
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from pydantic_marshmallow import PydanticSchema, schema_for

# =============================================================================
# Shared Pydantic Models - Basic
# =============================================================================

class SimpleUser(BaseModel):
    """Basic user model for simple tests."""
    name: str
    age: int
    email: str


class ValidatedUser(BaseModel):
    """User model with validation constraints."""
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: EmailStr
    score: float = Field(ge=0, le=100, default=0.0)


class UserWithDefaults(BaseModel):
    """User model with optional fields and defaults."""
    name: str
    email: str | None = None
    age: int = 0
    active: bool = True


class UserWithComputed(BaseModel):
    """User model with computed fields."""
    first_name: str
    last_name: str
    age: int

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserWithValidators(BaseModel):
    """User model with field validators."""
    email: str
    username: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip().lower()


# =============================================================================
# Shared Pydantic Models - Nested
# =============================================================================

class Address(BaseModel):
    """Address model for nesting tests."""
    street: str
    city: str
    country: str = "USA"
    zip_code: str = Field(default="00000", pattern=r"^\d{5}$")


class Person(BaseModel):
    """Person with nested address."""
    name: str
    email: EmailStr
    address: Address


class Item(BaseModel):
    """Item model for collection tests."""
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0, default=1)


class Order(BaseModel):
    """Order with nested items collection."""
    customer: str
    items: list[Item]
    total: float | None = None


# =============================================================================
# Shared Pydantic Models - Special Types
# =============================================================================

class Status(str, Enum):
    """Status enum for enum tests."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class EntityWithTypes(BaseModel):
    """Model with various field types."""
    id: UUID
    count: int
    amount: Decimal
    created_at: datetime
    event_date: date
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Status = Status.PENDING


# =============================================================================
# Shared Pydantic Models - Config Variants
# =============================================================================

class StrictModel(BaseModel):
    """Model with strict configuration (forbid extra)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    value: int


class FlexibleModel(BaseModel):
    """Model with flexible configuration (allow extra)."""
    model_config = ConfigDict(extra="allow")
    name: str


class IgnoreExtraModel(BaseModel):
    """Model that ignores extra fields."""
    model_config = ConfigDict(extra="ignore")
    name: str


class AliasedModel(BaseModel):
    """Model with field aliases."""
    model_config = ConfigDict(populate_by_name=True)
    user_name: str = Field(alias="userName")
    email_address: str = Field(alias="emailAddress")


# =============================================================================
# Shared Pydantic Models - Validation
# =============================================================================

class PasswordForm(BaseModel):
    """Password form for cross-field validation tests."""
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


class DateRange(BaseModel):
    """Date range for model validator tests."""
    start: date
    end: date

    @model_validator(mode="after")
    def check_dates(self):
        if self.end < self.start:
            raise ValueError("end must be after start")
        return self


# =============================================================================
# Test Data Constants
# =============================================================================

SIMPLE_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
}

VALIDATED_USER_DATA = {
    "name": "Alice Smith",
    "age": 30,
    "email": "alice@example.com",
    "score": 95.5,
}

ADDRESS_DATA = {
    "street": "123 Main St",
    "city": "Boston",
    "country": "USA",
    "zip_code": "02101",
}

PERSON_DATA = {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "address": ADDRESS_DATA,
}

ITEM_DATA = {"name": "Widget", "price": 9.99, "quantity": 2}

ORDER_DATA = {
    "customer": "Alice",
    "items": [
        {"name": "Widget", "price": 10.0, "quantity": 2},
        {"name": "Gadget", "price": 25.0, "quantity": 1},
    ],
}

INVALID_USER_DATA = {
    "name": "",  # min_length violation
    "age": -5,  # ge=0 violation
    "email": "invalid-email",  # email format violation
}

# Batch data for performance tests
BATCH_USERS = [
    {"name": f"User {i}", "age": 20 + (i % 50), "email": f"user{i}@example.com"}
    for i in range(100)
]


# =============================================================================
# Schema Fixtures
# =============================================================================

@pytest.fixture
def simple_user_schema():
    """Pre-built schema for SimpleUser."""
    return schema_for(SimpleUser)()


@pytest.fixture
def validated_user_schema():
    """Pre-built schema for ValidatedUser."""
    return schema_for(ValidatedUser)()


@pytest.fixture
def person_schema():
    """Pre-built schema for Person with nested Address."""
    return schema_for(Person)()


@pytest.fixture
def order_schema():
    """Pre-built schema for Order with nested Items."""
    return schema_for(Order)()


# =============================================================================
# Factory Fixtures
# =============================================================================

@pytest.fixture
def schema_factory():
    """Factory to create schemas for any Pydantic model."""
    def _create(model_class, **schema_kwargs):
        return schema_for(model_class)(**schema_kwargs)
    return _create


@pytest.fixture
def user_data_factory():
    """Factory to create user data with customizations."""
    def _create(**overrides):
        data = SIMPLE_USER_DATA.copy()
        data.update(overrides)
        return data
    return _create


@pytest.fixture
def item_data_factory():
    """Factory to create item data with customizations."""
    def _create(**overrides):
        data = ITEM_DATA.copy()
        data.update(overrides)
        return data
    return _create


# =============================================================================
# Schema with Hooks (for hook tests)
# =============================================================================

class UserSchemaWithPreLoad(PydanticSchema[SimpleUser]):
    """Schema with pre_load hook for transformation tests."""
    class Meta:
        model = SimpleUser

    @pre_load
    def normalize_data(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        if "email" in data:
            data["email"] = data["email"].lower().strip()
        if "name" in data:
            data["name"] = data["name"].strip()
        return data


class UserSchemaWithPostLoad(PydanticSchema[SimpleUser]):
    """Schema with post_load hook for modification tests."""
    class Meta:
        model = SimpleUser

    @post_load
    def add_metadata(self, data: SimpleUser, **kwargs) -> SimpleUser:
        return data


class UserSchemaWithValidates(PydanticSchema[SimpleUser]):
    """Schema with @validates decorator for field validation tests."""
    class Meta:
        model = SimpleUser

    @validates("name")
    def validate_name_not_admin(self, value, **kwargs):
        if value.lower() == "admin":
            raise ValidationError("Cannot use 'admin' as name")


class PasswordSchemaWithValidatesSchema(PydanticSchema[PasswordForm]):
    """Schema with @validates_schema for cross-field validation tests."""
    class Meta:
        model = PasswordForm

    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError({"_schema": ["Passwords must match"]})


@pytest.fixture
def user_schema_with_pre_load():
    """Schema with pre_load hook."""
    return UserSchemaWithPreLoad()


@pytest.fixture
def user_schema_with_post_load():
    """Schema with post_load hook."""
    return UserSchemaWithPostLoad()


@pytest.fixture
def user_schema_with_validates():
    """Schema with @validates decorator."""
    return UserSchemaWithValidates()


@pytest.fixture
def password_schema_with_validates_schema():
    """Schema with @validates_schema decorator."""
    return PasswordSchemaWithValidatesSchema()


# =============================================================================
# Assertion Helpers
# =============================================================================

def assert_validation_error_contains(exc_info, *fields):
    """Assert that validation error contains specific fields."""
    errors = exc_info.value.messages
    for field in fields:
        assert field in errors, f"Expected error for '{field}', got errors for: {list(errors.keys())}"


def assert_model_instance(result, model_class, **expected_values):
    """Assert result is a model instance with expected values."""
    assert isinstance(result, model_class), f"Expected {model_class.__name__}, got {type(result).__name__}"
    for key, value in expected_values.items():
        actual = getattr(result, key)
        assert actual == value, f"Expected {key}={value}, got {actual}"
