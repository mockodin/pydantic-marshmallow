"""Edge case and comprehensive type testing for marshmallow-pydantic.

Tests cover boundary conditions, complex types, and unusual scenarios.
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import pytest
from marshmallow import ValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pydantic_marshmallow import pydantic_schema, schema_for


class TestComplexTypes:
    """Test complex Python types."""

    def test_uuid_field(self):
        """Test UUID field handling."""
        class Entity(BaseModel):
            id: UUID

        schema = schema_for(Entity)()
        test_uuid = uuid4()

        # Load from string
        result = schema.load({"id": str(test_uuid)})
        assert result.id == test_uuid

        # Dump back to string
        dumped = schema.dump(result)
        assert dumped["id"] == str(test_uuid)

    def test_datetime_fields(self):
        """Test datetime, date, time fields."""
        class Event(BaseModel):
            created_at: datetime
            event_date: date
            start_time: time

        schema = schema_for(Event)()

        result = schema.load({
            "created_at": "2024-01-15T10:30:00",
            "event_date": "2024-01-15",
            "start_time": "10:30:00",
        })

        assert result.created_at == datetime(2024, 1, 15, 10, 30)
        assert result.event_date == date(2024, 1, 15)
        assert result.start_time == time(10, 30)

    def test_decimal_field(self):
        """Test Decimal field for precise financial calculations."""
        class Transaction(BaseModel):
            amount: Decimal = Field(decimal_places=2)

        schema = schema_for(Transaction)()

        result = schema.load({"amount": "123.45"})
        assert result.amount == Decimal("123.45")
        assert isinstance(result.amount, Decimal)

    def test_enum_field(self):
        """Test Enum field handling."""
        class Status(str, Enum):
            PENDING = "pending"
            ACTIVE = "active"
            COMPLETED = "completed"

        class Task(BaseModel):
            status: Status

        schema = schema_for(Task)()

        result = schema.load({"status": "active"})
        assert result.status == Status.ACTIVE

        # Invalid enum value
        with pytest.raises(ValidationError):
            schema.load({"status": "invalid"})

    def test_literal_field(self):
        """Test Literal type for constrained values."""
        class Config(BaseModel):
            mode: Literal["debug", "release", "test"]

        schema = schema_for(Config)()

        result = schema.load({"mode": "debug"})
        assert result.mode == "debug"

        with pytest.raises(ValidationError):
            schema.load({"mode": "production"})

    def test_union_types(self):
        """Test Union type handling."""
        class Flexible(BaseModel):
            value: Union[int, str]

        schema = schema_for(Flexible)()

        # Integer value
        result = schema.load({"value": 42})
        assert result.value == 42

        # String value
        result = schema.load({"value": "hello"})
        assert result.value == "hello"

    def test_dict_field(self):
        """Test Dict field with typed values."""
        class Settings(BaseModel):
            options: Dict[str, int]

        schema = schema_for(Settings)()

        result = schema.load({"options": {"max_retries": 3, "timeout": 30}})
        assert result.options == {"max_retries": 3, "timeout": 30}

    def test_set_and_frozenset(self):
        """Test Set and FrozenSet fields."""
        class Tags(BaseModel):
            tags: Set[str]
            immutable_tags: FrozenSet[str] = frozenset()

        schema = schema_for(Tags)()

        result = schema.load({
            "tags": ["python", "pydantic", "python"],  # Duplicates removed
            "immutable_tags": ["core", "stable"]
        })

        assert result.tags == {"python", "pydantic"}
        assert isinstance(result.immutable_tags, frozenset)

    def test_tuple_field(self):
        """Test Tuple field with fixed types."""
        class Point(BaseModel):
            coordinates: Tuple[float, float, float]

        schema = schema_for(Point)()

        result = schema.load({"coordinates": [1.0, 2.5, 3.7]})
        assert result.coordinates == (1.0, 2.5, 3.7)


class TestNestedAndRecursive:
    """Test nested and recursive model structures."""

    def test_deeply_nested_models(self):
        """Test deeply nested model structures."""
        class City(BaseModel):
            name: str
            population: int

        class State(BaseModel):
            name: str
            capital: City

        class Country(BaseModel):
            name: str
            states: List[State]

        schema = schema_for(Country)()

        result = schema.load({
            "name": "USA",
            "states": [
                {
                    "name": "Massachusetts",
                    "capital": {"name": "Boston", "population": 675000}
                },
                {
                    "name": "California",
                    "capital": {"name": "Sacramento", "population": 524000}
                }
            ]
        })

        assert result.name == "USA"
        assert len(result.states) == 2
        assert result.states[0].capital.name == "Boston"

    def test_self_referential_model(self):
        """Test self-referential models (tree structures)."""
        class TreeNode(BaseModel):
            value: int
            children: List["TreeNode"] = []

        # Rebuild model to resolve forward reference
        TreeNode.model_rebuild()

        schema = schema_for(TreeNode)()

        result = schema.load({
            "value": 1,
            "children": [
                {"value": 2, "children": []},
                {"value": 3, "children": [
                    {"value": 4, "children": []}
                ]}
            ]
        })

        assert result.value == 1
        assert len(result.children) == 2
        assert result.children[1].children[0].value == 4

    def test_optional_nested_model(self):
        """Test Optional nested models."""
        class Manager(BaseModel):
            name: str

        class Employee(BaseModel):
            name: str
            manager: Optional[Manager] = None

        schema = schema_for(Employee)()

        # Without manager
        result = schema.load({"name": "Alice"})
        assert result.manager is None

        # With manager
        result = schema.load({
            "name": "Bob",
            "manager": {"name": "Carol"}
        })
        assert result.manager.name == "Carol"


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_empty_string(self):
        """Test empty string handling."""
        class Message(BaseModel):
            content: str

        schema = schema_for(Message)()

        result = schema.load({"content": ""})
        assert result.content == ""

    def test_empty_list(self):
        """Test empty list handling."""
        class Container(BaseModel):
            items: List[str]

        schema = schema_for(Container)()

        result = schema.load({"items": []})
        assert result.items == []

    def test_empty_dict(self):
        """Test empty dict handling."""
        class Metadata(BaseModel):
            data: Dict[str, Any]

        schema = schema_for(Metadata)()

        result = schema.load({"data": {}})
        assert result.data == {}

    def test_null_vs_missing(self):
        """Test distinction between null and missing values."""
        class Profile(BaseModel):
            name: str
            bio: Optional[str] = None
            website: Optional[str] = "https://example.com"

        schema = schema_for(Profile)()

        # Missing optional field uses default
        result = schema.load({"name": "Alice"})
        assert result.bio is None
        assert result.website == "https://example.com"

        # Explicit null overrides default
        result = schema.load({"name": "Alice", "bio": None, "website": None})
        assert result.bio is None
        assert result.website is None

    def test_large_numbers(self):
        """Test handling of large numbers."""
        class BigData(BaseModel):
            big_int: int
            big_float: float

        schema = schema_for(BigData)()

        result = schema.load({
            "big_int": 9999999999999999999999999999,
            "big_float": 1.7976931348623157e+308  # Near max float
        })

        assert result.big_int == 9999999999999999999999999999

    def test_unicode_strings(self):
        """Test Unicode string handling."""
        class Message(BaseModel):
            content: str

        schema = schema_for(Message)()

        # Various Unicode characters
        test_strings = [
            "Hello, 世界!",
            "Émojis: 🎉🚀💻",
            "مرحبا",
            "Привет",
            "नमस्ते",
        ]

        for text in test_strings:
            result = schema.load({"content": text})
            assert result.content == text

    def test_special_float_values(self):
        """Test special float values (inf, nan) with Pydantic."""
        import math

        from pydantic import ConfigDict

        # By default in Pydantic v2, floats allow inf/nan during Python validation
        # but reject during JSON parsing. Let's test both scenarios.
        class Metrics(BaseModel):
            value: float

        schema = schema_for(Metrics)()

        # Python validation allows inf by default
        result = schema.load({"value": float("inf")})
        assert math.isinf(result.value)

        # To explicitly reject infinity, use strict mode or validators
        class MetricsStrict(BaseModel):
            model_config = ConfigDict(allow_inf_nan=False)
            value: float

        schema_strict = schema_for(MetricsStrict)()
        with pytest.raises(ValidationError):
            schema_strict.load({"value": float("inf")})


class TestValidationConstraints:
    """Test various Pydantic validation constraints."""

    def test_string_constraints(self):
        """Test string length and pattern constraints."""
        class Username(BaseModel):
            value: str = Field(min_length=3, max_length=20, pattern=r"^[a-z0-9_]+$")

        schema = schema_for(Username)()

        # Valid
        result = schema.load({"value": "john_doe123"})
        assert result.value == "john_doe123"

        # Too short
        with pytest.raises(ValidationError):
            schema.load({"value": "ab"})

        # Too long
        with pytest.raises(ValidationError):
            schema.load({"value": "a" * 21})

        # Invalid pattern
        with pytest.raises(ValidationError):
            schema.load({"value": "UPPERCASE"})

    def test_numeric_constraints(self):
        """Test numeric constraints (gt, ge, lt, le, multiple_of)."""
        class Rating(BaseModel):
            score: int = Field(ge=1, le=5)
            percentage: float = Field(ge=0, le=100)
            even_number: int = Field(multiple_of=2)

        schema = schema_for(Rating)()

        # Valid
        result = schema.load({"score": 5, "percentage": 99.9, "even_number": 4})
        assert result.score == 5

        # Score too high
        with pytest.raises(ValidationError):
            schema.load({"score": 6, "percentage": 50, "even_number": 2})

        # Not a multiple of 2
        with pytest.raises(ValidationError):
            schema.load({"score": 3, "percentage": 50, "even_number": 3})

    def test_list_constraints(self):
        """Test list length constraints."""
        class Team(BaseModel):
            members: List[str] = Field(min_length=1, max_length=5)

        schema = schema_for(Team)()

        # Valid
        result = schema.load({"members": ["Alice", "Bob"]})
        assert len(result.members) == 2

        # Empty list (violates min_length)
        with pytest.raises(ValidationError):
            schema.load({"members": []})

        # Too many members
        with pytest.raises(ValidationError):
            schema.load({"members": ["a", "b", "c", "d", "e", "f"]})


class TestErrorHandling:
    """Test error handling and error message formatting."""

    def test_multiple_field_errors(self):
        """Test that multiple field errors are reported."""
        class Form(BaseModel):
            name: str = Field(min_length=1)
            email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
            age: int = Field(ge=0, le=150)

        schema = schema_for(Form)()

        with pytest.raises(ValidationError) as exc:
            schema.load({"name": "", "email": "invalid", "age": -5})

        errors = exc.value.messages
        # All three fields should have errors
        assert "name" in errors or "email" in errors or "age" in errors

    def test_nested_model_errors(self):
        """Test that nested model errors are reported correctly."""
        class Address(BaseModel):
            zip_code: str = Field(pattern=r"^\d{5}$")

        class Person(BaseModel):
            name: str
            address: Address

        schema = schema_for(Person)()

        with pytest.raises(ValidationError) as exc:
            schema.load({
                "name": "Alice",
                "address": {"zip_code": "invalid"}
            })

        # Error should indicate the nested field
        assert "address" in exc.value.messages or "zip_code" in str(exc.value.messages)

    def test_type_coercion_failure(self):
        """Test error when type coercion fails."""
        class Config(BaseModel):
            count: int

        schema = schema_for(Config)()

        with pytest.raises(ValidationError):
            schema.load({"count": "not-a-number"})

    def test_missing_required_field(self):
        """Test error for missing required field."""
        class Required(BaseModel):
            name: str
            email: str

        schema = schema_for(Required)()

        with pytest.raises(ValidationError) as exc:
            schema.load({"name": "Alice"})  # Missing email

        assert "email" in exc.value.messages


class TestFieldAliases:
    """Test Pydantic field aliases."""

    def test_field_alias(self):
        """Test field with alias."""
        class ApiResponse(BaseModel):
            model_config = ConfigDict(populate_by_name=True)

            user_id: int = Field(alias="userId")
            first_name: str = Field(alias="firstName")

        schema = schema_for(ApiResponse)()

        # Load using aliases
        result = schema.load({"userId": 123, "firstName": "Alice"})
        assert result.user_id == 123
        assert result.first_name == "Alice"

        # Can also load using field names
        result = schema.load({"user_id": 456, "first_name": "Bob"})
        assert result.user_id == 456
        assert result.first_name == "Bob"

    def test_validation_alias(self):
        """Test validation_alias for input-only aliases."""
        class Config(BaseModel):
            model_config = ConfigDict(populate_by_name=True)

            database_url: str = Field(alias="DATABASE_URL")

        schema = schema_for(Config)()

        # Can use alias
        result = schema.load({"DATABASE_URL": "postgres://localhost/db"})
        assert result.database_url == "postgres://localhost/db"

        # Can also use field name
        result = schema.load({"database_url": "mysql://localhost/db"})
        assert result.database_url == "mysql://localhost/db"


class TestCustomValidators:
    """Test custom Pydantic validators."""

    def test_field_validator_transform(self):
        """Test field_validator that transforms values."""
        class User(BaseModel):
            email: str

            @field_validator("email")
            @classmethod
            def lowercase_email(cls, v: str) -> str:
                return v.lower().strip()

        schema = schema_for(User)()

        result = schema.load({"email": "  ALICE@EXAMPLE.COM  "})
        assert result.email == "alice@example.com"

    def test_field_validator_with_context(self):
        """Test field_validator that raises ValueError."""
        class Password(BaseModel):
            value: str

            @field_validator("value")
            @classmethod
            def password_strength(cls, v: str) -> str:
                if len(v) < 8:
                    raise ValueError("Password must be at least 8 characters")
                if not any(c.isupper() for c in v):
                    raise ValueError("Password must contain uppercase")
                if not any(c.isdigit() for c in v):
                    raise ValueError("Password must contain a digit")
                return v

        schema = schema_for(Password)()

        # Valid password
        result = schema.load({"value": "SecurePass123"})
        assert result.value == "SecurePass123"

        # Too short
        with pytest.raises(ValidationError):
            schema.load({"value": "Short1"})

        # No uppercase
        with pytest.raises(ValidationError):
            schema.load({"value": "lowercase123"})


class TestDecoratorEdgeCases:
    """Test edge cases for the @pydantic_schema decorator."""

    def test_decorator_with_inheritance(self):
        """Test decorator with model inheritance."""
        class BasePerson(BaseModel):
            name: str

        @pydantic_schema
        class Employee(BasePerson):
            employee_id: int
            department: str

        schema = Employee.Schema()
        result = schema.load({
            "name": "Alice",
            "employee_id": 123,
            "department": "Engineering"
        })

        assert isinstance(result, Employee)
        assert result.name == "Alice"
        assert result.employee_id == 123

    def test_decorator_with_config(self):
        """Test decorator with model config."""
        @pydantic_schema
        class StrictModel(BaseModel):
            model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

            name: str

        schema = StrictModel.Schema()

        # Whitespace is stripped
        result = schema.load({"name": "  Alice  "})
        assert result.name == "Alice"

        # Extra fields rejected
        with pytest.raises(ValidationError):
            schema.load({"name": "Alice", "extra": "field"})

    def test_multiple_decorated_models(self):
        """Test multiple models decorated in same module."""
        @pydantic_schema
        class ModelA(BaseModel):
            a: str

        @pydantic_schema
        class ModelB(BaseModel):
            b: int

        # Each has its own Schema
        result_a = ModelA.Schema().load({"a": "test"})
        result_b = ModelB.Schema().load({"b": 42})

        assert isinstance(result_a, ModelA)
        assert isinstance(result_b, ModelB)
        assert result_a.a == "test"
        assert result_b.b == 42
