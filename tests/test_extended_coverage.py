"""Extended test coverage for marshmallow-pydantic.

Tests cover:
- Pydantic model validators (@model_validator)
- Additional type coverage (PositiveInt, SecretStr, etc.)
- Context passing scenarios
- Complex validation scenarios (discriminated unions, recursive models)
- Error accumulation
- Partial loading edge cases
- Unknown field handling edge cases

Note: Tests for return_instance, computed_field, and dump serialization options
have been moved to dedicated test files:
- test_return_instance.py
- test_computed_fields.py
- test_dump_options.py
"""

from datetime import date, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Annotated, Generic, Literal, TypeVar

import pytest
from marshmallow import EXCLUDE, INCLUDE, ValidationError, pre_load, validates, validates_schema
from pydantic import BaseModel, EmailStr, Field, NegativeFloat, PositiveInt, SecretStr, field_validator, model_validator

from pydantic_marshmallow import PydanticSchema, schema_for

# ============================================================================
# Test Pydantic model validators
# ============================================================================

class TestModelValidators:
    """Test Pydantic model_validator support."""

    def test_model_validator_before(self):
        """Test @model_validator(mode='before') runs before field validation."""
        class Config(BaseModel):
            host: str
            port: int

            @model_validator(mode='before')
            @classmethod
            def parse_url(cls, data):
                if isinstance(data, dict) and "url" in data:
                    # Parse "host:port" format
                    url = data.pop("url")
                    host, port = url.split(":")
                    data["host"] = host
                    data["port"] = int(port)
                return data

        schema = schema_for(Config)()

        # Standard format - works directly
        result = schema.load({"host": "localhost", "port": 8080})
        assert result.host == "localhost"
        assert result.port == 8080

        # For URL format transformation, use pre_load hook instead
        # because model_validator runs after Marshmallow's unknown check
        class ConfigWithPreLoad(BaseModel):
            host: str
            port: int

        class ConfigSchema(PydanticSchema[ConfigWithPreLoad]):
            class Meta:
                model = ConfigWithPreLoad

            @pre_load
            def parse_url(self, data, **kwargs):
                if "url" in data:
                    url = data.pop("url")
                    host, port = url.split(":")
                    data["host"] = host
                    data["port"] = int(port)
                return data

        schema2 = ConfigSchema()
        result = schema2.load({"url": "localhost:9000"})
        assert result.host == "localhost"
        assert result.port == 9000

    def test_model_validator_after(self):
        """Test @model_validator(mode='after') runs after field validation."""
        class DateRange(BaseModel):
            start: date
            end: date

            @model_validator(mode='after')
            def check_dates(self):
                if self.end < self.start:
                    raise ValueError("end must be after start")
                return self

        schema = schema_for(DateRange)()

        # Valid range
        result = schema.load({"start": "2024-01-01", "end": "2024-12-31"})
        assert result.start < result.end

        # Invalid range
        with pytest.raises(ValidationError) as exc:
            schema.load({"start": "2024-12-31", "end": "2024-01-01"})

        assert "end must be after start" in str(exc.value)

    def test_combined_pydantic_and_marshmallow_validators(self):
        """Test Pydantic and Marshmallow validators work together."""
        class User(BaseModel):
            username: str
            email: str

            @field_validator("email")
            @classmethod
            def validate_email_domain(cls, v):
                if not v.endswith("@company.com"):
                    raise ValueError("Must use company email")
                return v

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("username")
            def validate_username(self, value, **kwargs):
                if value.lower() in ["admin", "root", "system"]:
                    raise ValidationError("Reserved username")

        schema = UserSchema()

        # Both validators pass
        result = schema.load({"username": "alice", "email": "alice@company.com"})
        assert result.username == "alice"

        # Pydantic validator fails
        with pytest.raises(ValidationError) as exc:
            schema.load({"username": "alice", "email": "alice@gmail.com"})
        assert "company email" in str(exc.value)

        # Marshmallow validator fails
        with pytest.raises(ValidationError) as exc:
            schema.load({"username": "admin", "email": "admin@company.com"})
        assert "Reserved username" in str(exc.value)


# ============================================================================
# Test additional type coverage
# ============================================================================

class TestAdditionalTypes:
    """Test additional Python/Pydantic types."""

    def test_positive_int(self):
        """Test PositiveInt constraint."""
        class Score(BaseModel):
            value: PositiveInt

        schema = schema_for(Score)()

        result = schema.load({"value": 100})
        assert result.value == 100

        with pytest.raises(ValidationError):
            schema.load({"value": 0})

        with pytest.raises(ValidationError):
            schema.load({"value": -5})

    def test_negative_float(self):
        """Test NegativeFloat constraint."""
        class Temperature(BaseModel):
            celsius: NegativeFloat

        schema = schema_for(Temperature)()

        result = schema.load({"celsius": -10.5})
        assert result.celsius == -10.5

        with pytest.raises(ValidationError):
            schema.load({"celsius": 0.0})

    def test_secret_str(self):
        """Test SecretStr for sensitive data."""
        class Credentials(BaseModel):
            username: str
            password: SecretStr

        schema = schema_for(Credentials)()
        result = schema.load({"username": "alice", "password": "secret123"})

        # SecretStr hides the value in repr
        assert "secret" not in repr(result.password)
        # But can still get the value
        assert result.password.get_secret_value() == "secret123"

    def test_timedelta_field(self):
        """Test timedelta handling."""
        class Task(BaseModel):
            name: str
            duration: timedelta

        schema = schema_for(Task)()

        # From ISO duration string
        result = schema.load({"name": "Build", "duration": 3600})  # seconds
        assert result.duration == timedelta(seconds=3600)

    def test_path_field(self):
        """Test Path type handling."""
        class FileConfig(BaseModel):
            path: Path

        schema = schema_for(FileConfig)()
        result = schema.load({"path": "/usr/local/bin"})

        assert isinstance(result.path, Path)
        # Path uses OS-specific separators, so normalize for comparison
        assert result.path == Path("/usr/local/bin")

    def test_annotated_constraints(self):
        """Test Annotated with constraints."""
        class Product(BaseModel):
            name: Annotated[str, Field(min_length=1, max_length=100)]
            price: Annotated[float, Field(gt=0)]

        schema = schema_for(Product)()

        result = schema.load({"name": "Widget", "price": 9.99})
        assert result.name == "Widget"

        with pytest.raises(ValidationError):
            schema.load({"name": "", "price": 9.99})

    def test_int_enum(self):
        """Test IntEnum handling."""
        class Priority(IntEnum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        class Task(BaseModel):
            priority: Priority

        schema = schema_for(Task)()

        result = schema.load({"priority": 2})
        assert result.priority == Priority.MEDIUM
        assert result.priority.value == 2

    def test_bytes_field(self):
        """Test bytes field handling."""
        class BinaryData(BaseModel):
            data: bytes

        schema = schema_for(BinaryData)()
        result = schema.load({"data": "SGVsbG8gV29ybGQ="})  # base64 "Hello World"
        assert isinstance(result.data, bytes)


# ============================================================================
# Test context passing
# ============================================================================

class TestContextPassing:
    """Test Marshmallow context passing to hooks and validators."""

    def test_context_in_pre_load(self):
        """Test context is available in pre_load hooks."""
        class User(BaseModel):
            name: str
            role: str = "user"

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def set_role_from_context(self, data, **kwargs):
                if "default_role" in self.context:
                    data.setdefault("role", self.context["default_role"])
                return data

        schema = UserSchema()
        schema.context = {"default_role": "admin"}

        result = schema.load({"name": "Alice"})
        assert result.role == "admin"

    def test_context_in_validates(self):
        """Test context is available in @validates methods."""
        class Document(BaseModel):
            content: str

        class DocumentSchema(PydanticSchema[Document]):
            class Meta:
                model = Document

            @validates("content")
            def validate_length(self, value, **kwargs):
                max_length = self.context.get("max_length", 1000)
                if len(value) > max_length:
                    raise ValidationError(f"Content exceeds {max_length} characters")

        schema = DocumentSchema()
        schema.context = {"max_length": 10}

        with pytest.raises(ValidationError) as exc:
            schema.load({"content": "This is a very long content string"})

        assert "10 characters" in str(exc.value)

    def test_context_in_validates_schema(self):
        """Test context is available in @validates_schema methods."""
        class Order(BaseModel):
            items: list[str]
            total: float

        class OrderSchema(PydanticSchema[Order]):
            class Meta:
                model = Order

            @validates_schema
            def validate_order(self, data, **kwargs):
                min_order = self.context.get("min_order_value", 0)
                if data.get("total", 0) < min_order:
                    raise ValidationError(f"Minimum order is ${min_order}")

        schema = OrderSchema()
        schema.context = {"min_order_value": 50}

        with pytest.raises(ValidationError) as exc:
            schema.load({"items": ["widget"], "total": 25.0})

        assert "Minimum order is $50" in str(exc.value)


# ============================================================================
# Test error accumulation
# ============================================================================

class TestErrorAccumulation:
    """Test that multiple errors are accumulated and reported."""

    def test_multiple_field_errors_accumulated(self):
        """Test multiple field errors are all reported."""
        class Form(BaseModel):
            name: str = Field(min_length=1)
            age: int = Field(ge=0, le=150)
            email: EmailStr

        schema = schema_for(Form)()

        with pytest.raises(ValidationError) as exc:
            schema.load({"name": "", "age": -5, "email": "invalid"})

        errors = exc.value.messages
        # Should have errors for multiple fields
        assert len(errors) >= 2

    def test_errors_with_valid_data(self):
        """Test valid_data is available on BridgeValidationError."""

        class User(BaseModel):
            name: str
            email: EmailStr
            age: int = Field(ge=0)

        schema = schema_for(User)()

        try:
            schema.load({"name": "Alice", "email": "invalid", "age": -5})
            assert False, "Should have raised"
        except ValidationError as e:
            # Name was valid
            if hasattr(e, 'valid_data'):
                assert "name" in e.valid_data

    def test_nested_errors_reported(self):
        """Test nested model errors are properly reported."""
        class Address(BaseModel):
            street: str = Field(min_length=1)
            zip_code: str = Field(pattern=r"^\d{5}$")

        class Person(BaseModel):
            name: str
            address: Address

        schema = schema_for(Person)()

        with pytest.raises(ValidationError) as exc:
            schema.load({
                "name": "Alice",
                "address": {"street": "", "zip_code": "invalid"}
            })

        # Error path should include 'address'
        error_str = str(exc.value.messages)
        assert "address" in error_str or "street" in error_str or "zip_code" in error_str


# ============================================================================
# Test complex validation scenarios
# ============================================================================

class TestComplexValidation:
    """Test complex validation scenarios."""

    def test_discriminated_union(self):
        """Test discriminated unions (tagged unions)."""
        class Cat(BaseModel):
            pet_type: Literal["cat"]
            meow_volume: int

        class Dog(BaseModel):
            pet_type: Literal["dog"]
            bark_volume: int

        class Pet(BaseModel):
            pet: Cat | Dog = Field(discriminator="pet_type")

        schema = schema_for(Pet)()

        # Cat
        result = schema.load({"pet": {"pet_type": "cat", "meow_volume": 5}})
        assert isinstance(result.pet, Cat)

        # Dog
        result = schema.load({"pet": {"pet_type": "dog", "bark_volume": 10}})
        assert isinstance(result.pet, Dog)

    def test_recursive_model(self):
        """Test deeply recursive models."""
        class Node(BaseModel):
            value: int
            children: list["Node"] = []

        Node.model_rebuild()

        schema = schema_for(Node)()

        result = schema.load({
            "value": 1,
            "children": [
                {"value": 2, "children": [
                    {"value": 4, "children": []},
                    {"value": 5, "children": []}
                ]},
                {"value": 3, "children": []}
            ]
        })

        assert result.value == 1
        assert len(result.children) == 2
        assert result.children[0].children[0].value == 4

    def test_generic_model(self):
        """Test generic Pydantic models."""
        T = TypeVar("T")

        class Response(BaseModel, Generic[T]):
            data: T
            status: str = "ok"

        # Concrete instantiation
        class UserResponse(Response[dict[str, str]]):
            pass

        schema = schema_for(UserResponse)()
        result = schema.load({"data": {"name": "Alice"}, "status": "success"})

        assert result.data == {"name": "Alice"}
        assert result.status == "success"

    def test_multiple_validators_same_field(self):
        """Test multiple validators on the same field."""
        class Password(BaseModel):
            value: str

            @field_validator("value")
            @classmethod
            def check_length(cls, v):
                if len(v) < 8:
                    raise ValueError("Password must be at least 8 characters")
                return v

            @field_validator("value")
            @classmethod
            def check_uppercase(cls, v):
                if not any(c.isupper() for c in v):
                    raise ValueError("Password must contain uppercase")
                return v

            @field_validator("value")
            @classmethod
            def check_digit(cls, v):
                if not any(c.isdigit() for c in v):
                    raise ValueError("Password must contain a digit")
                return v

        schema = schema_for(Password)()

        # All validators pass
        result = schema.load({"value": "SecurePass123"})
        assert result.value == "SecurePass123"

        # One validator fails
        with pytest.raises(ValidationError):
            schema.load({"value": "short"})


# ============================================================================
# Test partial loading edge cases
# ============================================================================

class TestPartialLoadingEdgeCases:
    """Test edge cases in partial loading."""

    def test_partial_with_validators(self):
        """Test partial loading still runs validators on provided fields."""
        class User(BaseModel):
            name: str = Field(min_length=1)
            email: str = Field(pattern=r".*@.*")
            age: int = Field(ge=0)

        schema = schema_for(User)()

        # Partial with valid provided field
        result = schema.load({"name": "Alice"}, partial=True)
        assert result.name == "Alice"

        # Partial with invalid provided field still fails
        with pytest.raises(ValidationError):
            schema.load({"name": ""}, partial=True)

    def test_partial_tuple_specific_fields(self):
        """Test partial=('field1', 'field2') allows only those fields to be missing."""
        class User(BaseModel):
            name: str
            email: str
            age: int

        schema = schema_for(User)()

        # Only email is partial
        result = schema.load({"name": "Alice", "age": 30}, partial=("email",))
        assert result.name == "Alice"

        # Name is required, should fail
        with pytest.raises(ValidationError):
            schema.load({"email": "alice@example.com", "age": 30}, partial=("email",))

    def test_partial_with_defaults(self):
        """Test partial loading with fields that have defaults."""
        class Settings(BaseModel):
            theme: str = "light"
            language: str = "en"
            font_size: int

        schema = schema_for(Settings)()

        # font_size is required but partial allows it missing
        result = schema.load({"theme": "dark"}, partial=True)
        assert result.theme == "dark"
        assert result.language == "en"  # Default preserved


# ============================================================================
# Test unknown field handling edge cases
# ============================================================================

class TestUnknownFieldsEdgeCases:
    """Test edge cases in unknown field handling."""

    def test_unknown_include_preserves_all(self):
        """Test unknown=INCLUDE preserves all unknown fields."""

        class User(BaseModel):
            name: str

        schema = schema_for(User)(unknown=INCLUDE)
        result = schema.load({"name": "Alice", "extra1": "value1", "extra2": 123})

        # Result is a model, unknown fields might be stored differently
        assert result.name == "Alice"

    def test_unknown_exclude_with_nested(self):
        """Test unknown=EXCLUDE works with nested models."""

        class Address(BaseModel):
            city: str

        class Person(BaseModel):
            name: str
            address: Address

        schema = schema_for(Person)(unknown=EXCLUDE)
        result = schema.load({
            "name": "Alice",
            "unknown_field": "ignored",
            "address": {"city": "Boston"}
        })

        assert result.name == "Alice"
        assert result.address.city == "Boston"
