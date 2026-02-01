"""
Tests for Connexion compatibility.

Connexion is an OpenAPI-first REST framework that can use Marshmallow
for request/response validation. This tests that PydanticSchema works
correctly when registered with Connexion's schema resolvers.
"""

import pytest

connexion = pytest.importorskip("connexion")

import json  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

from pydantic_marshmallow import PydanticSchema, schema_for  # noqa: E402

# =============================================================================
# Test Models
# =============================================================================


class User(BaseModel):
    """User model for API testing."""

    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    email: str  # Using str since EmailStr requires email-validator
    age: int = Field(ge=0, le=150)


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""

    name: str = Field(min_length=1, max_length=100)
    email: str
    age: int = Field(ge=0, le=150)


class UserResponse(BaseModel):
    """Response model for user data."""

    id: int
    name: str
    email: str
    age: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    code: int
    message: str


# =============================================================================
# Schemas
# =============================================================================


class UserSchema(PydanticSchema[User]):
    """User schema for Connexion."""

    class Meta:
        model = User


class CreateUserRequestSchema(PydanticSchema[CreateUserRequest]):
    """Create user request schema."""

    class Meta:
        model = CreateUserRequest


class UserResponseSchema(PydanticSchema[UserResponse]):
    """User response schema."""

    class Meta:
        model = UserResponse


class ErrorResponseSchema(PydanticSchema[ErrorResponse]):
    """Error response schema."""

    class Meta:
        model = ErrorResponse


# =============================================================================
# Test OpenAPI Spec Generation
# =============================================================================


class TestConnexionSchemaIntegration:
    """Test that PydanticSchema can be used with Connexion's schema resolvers."""

    def test_schema_has_marshmallow_fields(self):
        """Verify schemas have proper Marshmallow field structure."""
        schema = UserSchema()

        assert "id" in schema.fields
        assert "name" in schema.fields
        assert "email" in schema.fields
        assert "age" in schema.fields

    def test_schema_load_produces_model(self):
        """Test that schema.load produces Pydantic model instances."""
        schema = UserSchema()
        data = {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30}

        result = schema.load(data)

        assert isinstance(result, User)
        assert result.id == 1
        assert result.name == "Alice"

    def test_schema_dump_produces_dict(self):
        """Test that schema.dump produces dict."""
        schema = UserSchema()
        user = User(id=1, name="Bob", email="bob@example.com", age=25)

        result = schema.dump(user)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["name"] == "Bob"

    def test_validation_error_format(self):
        """Test that validation errors are in Marshmallow format."""
        schema = CreateUserRequestSchema()
        invalid_data = {
            "name": "",  # Too short
            "email": "test@example.com",
            "age": -5,  # Negative
        }

        errors = schema.validate(invalid_data)

        # Should have validation errors
        assert errors  # Non-empty
        assert "name" in errors or "age" in errors


class TestConnexionRequestValidation:
    """Test request validation patterns used by Connexion."""

    def test_load_valid_request(self):
        """Test loading a valid request body."""
        schema = CreateUserRequestSchema()
        request_body = {
            "name": "Charlie",
            "email": "charlie@example.com",
            "age": 28,
        }

        result = schema.load(request_body)

        assert isinstance(result, CreateUserRequest)
        assert result.name == "Charlie"
        assert result.email == "charlie@example.com"
        assert result.age == 28

    def test_load_invalid_request_raises(self):
        """Test that invalid request raises ValidationError."""
        from marshmallow import ValidationError

        schema = CreateUserRequestSchema()
        invalid_body = {
            "name": "",  # Empty - violates min_length=1
            "email": "test@example.com",
            "age": 25,
        }

        with pytest.raises(ValidationError):
            schema.load(invalid_body)

    def test_partial_request_validation(self):
        """Test partial loading for PATCH requests."""
        schema = UserSchema()
        # PATCH request might only include fields to update
        partial_data = {"name": "Updated Name"}

        result = schema.load(partial_data, partial=True)

        assert result.name == "Updated Name"


class TestConnexionResponseSerialization:
    """Test response serialization patterns used by Connexion."""

    def test_dump_response(self):
        """Test dumping a response model."""
        schema = UserResponseSchema()
        response = UserResponse(
            id=42, name="Diana", email="diana@example.com", age=35
        )

        result = schema.dump(response)

        assert result == {
            "id": 42,
            "name": "Diana",
            "email": "diana@example.com",
            "age": 35,
        }

    def test_dump_many_responses(self):
        """Test dumping a list of responses."""
        schema = UserResponseSchema(many=True)
        responses = [
            UserResponse(id=1, name="User1", email="u1@example.com", age=20),
            UserResponse(id=2, name="User2", email="u2@example.com", age=30),
        ]

        result = schema.dump(responses)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_error_response_serialization(self):
        """Test error response serialization."""
        schema = ErrorResponseSchema()
        error = ErrorResponse(code=400, message="Bad Request")

        result = schema.dump(error)

        assert result == {"code": 400, "message": "Bad Request"}


class TestConnexionSchemaRegistry:
    """Test patterns for registering schemas with Connexion."""

    def test_schema_for_function(self):
        """Test using schema_for to create schemas dynamically."""
        # This is how you might register schemas in a resolver

        dynamic_user_schema = schema_for(User)
        schema = dynamic_user_schema()

        data = {"id": 1, "name": "Eve", "email": "eve@example.com", "age": 22}
        result = schema.load(data)

        assert isinstance(result, User)
        assert result.name == "Eve"

    def test_schema_as_class_attribute(self):
        """Test pattern where model has .Schema attribute."""
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class Item(BaseModel):
            name: str
            price: float = Field(ge=0)

        # Access schema via class attribute
        schema = Item.Schema()
        data = {"name": "Widget", "price": 9.99}

        result = schema.load(data)

        assert isinstance(result, Item)
        assert result.name == "Widget"
        assert result.price == 9.99


class TestConnexionOpenAPISpec:
    """Test OpenAPI spec generation compatibility."""

    def test_schema_has_load_fields(self):
        """Test that schemas expose load_fields for spec generation."""
        schema = UserSchema()

        # Connexion/apispec uses these for spec generation
        assert hasattr(schema, "load_fields")
        assert hasattr(schema, "dump_fields")
        assert hasattr(schema, "fields")

    def test_schema_class_has_opts(self):
        """Test that schema class has Meta options."""
        # Connexion may inspect schema class Meta
        assert hasattr(UserSchema, "Meta")
        assert hasattr(UserSchema.Meta, "model")

    def test_nested_schema_compatibility(self):
        """Test nested models work with Connexion patterns."""

        class Address(BaseModel):
            street: str
            city: str
            zip_code: str

        class Person(BaseModel):
            name: str
            address: Address

        person_schema_cls = schema_for(Person)
        schema = person_schema_cls()

        data = {
            "name": "Frank",
            "address": {"street": "123 Main St", "city": "Boston", "zip_code": "02101"},
        }

        result = schema.load(data)

        assert result.name == "Frank"
        assert result.address.city == "Boston"


class TestConnexionJSONHandling:
    """Test JSON serialization patterns used by Connexion."""

    def test_dumps_produces_json(self):
        """Test that schema.dumps produces JSON string."""
        schema = UserSchema()
        user = User(id=1, name="Grace", email="grace@example.com", age=28)

        json_str = schema.dumps(user)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["name"] == "Grace"

    def test_loads_from_json(self):
        """Test that schema.loads deserializes from JSON string."""
        schema = UserSchema()
        json_str = '{"id": 1, "name": "Henry", "email": "henry@example.com", "age": 40}'

        result = schema.loads(json_str)

        assert isinstance(result, User)
        assert result.name == "Henry"
        assert result.age == 40

    def test_many_loads_from_json(self):
        """Test loading multiple objects from JSON array."""
        schema = UserSchema(many=True)
        json_str = '''[
            {"id": 1, "name": "User1", "email": "u1@example.com", "age": 20},
            {"id": 2, "name": "User2", "email": "u2@example.com", "age": 30}
        ]'''

        result = schema.loads(json_str)

        assert len(result) == 2
        assert all(isinstance(u, User) for u in result)
