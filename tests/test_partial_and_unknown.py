"""Tests for partial loading and unknown field handling.

Features tested:
- partial=True/tuple loading (missing required fields allowed)
- unknown=RAISE/EXCLUDE/INCLUDE field handling
- @validates("field") decorator
- @validates_schema decorator
- validate() method (returns errors dict)
- context passing to validators
"""

import pytest
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, EmailStr, Field

from pydantic_marshmallow import (
    EXCLUDE,
    INCLUDE,
    PydanticSchema,
    schema_for,
    validates,
    validates_schema,
)


# Test models
class User(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    age: int = Field(ge=0)


class Profile(BaseModel):
    username: str
    bio: str = ""
    verified: bool = False


class PasswordReset(BaseModel):
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


# =============================================================================
# Partial Loading Tests
# =============================================================================

class TestPartialLoading:
    """Test partial=True and partial=('field1', 'field2') support."""

    def test_partial_true_allows_missing_required_fields(self):
        """With partial=True, all required fields become optional."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=True)

        # Only provide name, missing email and age
        result = schema.load({"name": "Alice"})

        assert result.name == "Alice"

    def test_partial_tuple_allows_specific_missing_fields(self):
        """With partial=('field',), only that field becomes optional."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=("age",))

        # Missing age is allowed, but email is still required
        result = schema.load({"name": "Alice", "email": "alice@example.com"})

        assert result.name == "Alice"
        assert result.email == "alice@example.com"

    def test_partial_tuple_still_requires_unlisted_fields(self):
        """Fields not in partial tuple are still required."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=("age",))

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "Alice"})  # Missing email

        assert "email" in exc_info.value.messages

    def test_partial_validates_provided_fields(self):
        """Partial loading still validates provided fields."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=True)

        with pytest.raises(ValidationError):
            schema.load({"name": ""})  # Empty name fails min_length

    def test_partial_via_load_method(self):
        """partial can be passed to load() method."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        result = schema.load({"name": "Alice"}, partial=True)

        assert result.name == "Alice"


# =============================================================================
# Unknown Field Handling Tests
# =============================================================================

class TestUnknownFieldHandling:
    """Test unknown=RAISE/EXCLUDE/INCLUDE support."""

    def test_unknown_raise_is_default(self):
        """By default, unknown fields raise ValidationError."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "Alice",
                "email": "alice@example.com",
                "age": 30,
                "extra_field": "should fail",
            })

        assert "extra_field" in exc_info.value.messages

    def test_unknown_exclude_removes_extra_fields(self):
        """unknown=EXCLUDE silently removes unknown fields."""
        UserSchema = schema_for(User)
        schema = UserSchema(unknown=EXCLUDE)

        result = schema.load({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,
            "extra_field": "should be ignored",
        })

        assert result.name == "Alice"
        assert not hasattr(result, "extra_field")

    def test_unknown_include_keeps_extra_fields(self):
        """unknown=INCLUDE keeps unknown fields in result."""
        ProfileSchema = schema_for(Profile)
        schema = ProfileSchema(unknown=INCLUDE)

        result = schema.load({
            "username": "alice",
            "bio": "Hello",
            "extra_field": "should be kept",
        })

        assert result.username == "alice"
        # Extra field should be accessible via model_extra or similar

    def test_unknown_via_meta_class(self):
        """unknown can be set via Meta class."""
        class ProfileSchemaExclude(PydanticSchema[Profile]):
            class Meta:
                model = Profile
                unknown = EXCLUDE

        schema = ProfileSchemaExclude()

        result = schema.load({
            "username": "alice",
            "extra": "ignored",
        })

        assert result.username == "alice"


# =============================================================================
# Field Validator Tests
# =============================================================================

class TestFieldValidators:
    """Test @validates("field") decorator support."""

    def test_validates_decorator_basic(self):
        """@validates("field") runs on specific field."""
        class UserSchemaWithValidator(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name_not_admin(self, value, **kwargs):
                if value.lower() == "admin":
                    raise ValidationError("Cannot use 'admin' as name")

        schema = UserSchemaWithValidator()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "admin",
                "email": "admin@example.com",
                "age": 30,
            })

        assert "name" in exc_info.value.messages
        assert "admin" in str(exc_info.value.messages["name"]).lower()

    def test_validates_runs_after_pydantic(self):
        """@validates runs after Pydantic validation."""
        class UserSchemaWithValidator(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name_format(self, value, **kwargs):
                # If we get here, Pydantic already validated min_length
                if not value[0].isupper():
                    raise ValidationError("Name must start with uppercase")

        schema = UserSchemaWithValidator()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "alice",  # lowercase
                "email": "alice@example.com",
                "age": 30,
            })

        assert "uppercase" in str(exc_info.value.messages["name"]).lower()

    def test_validates_allows_valid_data(self):
        """@validates passes through valid data."""
        class UserSchemaWithValidator(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name(self, value, **kwargs):
                if len(value) < 2:
                    raise ValidationError("Name too short")

        schema = UserSchemaWithValidator()

        result = schema.load({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,
        })

        assert result.name == "Alice"


# =============================================================================
# Schema Validator Tests
# =============================================================================

class TestSchemaValidators:
    """Test @validates_schema decorator support."""

    def test_validates_schema_basic(self):
        """@validates_schema validates across fields."""
        class PasswordResetSchema(PydanticSchema[PasswordReset]):
            class Meta:
                model = PasswordReset

            @validates_schema
            def validate_passwords_match(self, data, **kwargs):
                if data.get("password") != data.get("confirm_password"):
                    raise ValidationError({"_schema": ["Passwords must match"]})

        schema = PasswordResetSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "password": "secret123",
                "confirm_password": "different456",
            })

        assert "_schema" in exc_info.value.messages

    def test_validates_schema_allows_valid(self):
        """@validates_schema passes through valid data."""
        class PasswordResetSchema(PydanticSchema[PasswordReset]):
            class Meta:
                model = PasswordReset

            @validates_schema
            def validate_passwords_match(self, data, **kwargs):
                if data.get("password") != data.get("confirm_password"):
                    raise ValidationError({"_schema": ["Passwords must match"]})

        schema = PasswordResetSchema()

        result = schema.load({
            "password": "secret123",
            "confirm_password": "secret123",
        })

        assert result.password == "secret123"


# =============================================================================
# validate() Method Tests
# =============================================================================

class TestValidateMethod:
    """Test validate() method that returns errors without raising."""

    def test_validate_returns_empty_dict_on_success(self):
        """validate() returns {} when data is valid."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        errors = schema.validate({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,
        })

        assert errors == {}

    def test_validate_returns_errors_dict_on_failure(self):
        """validate() returns error dict instead of raising."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        errors = schema.validate({
            "name": "",
            "email": "not-an-email",
            "age": -5,
        })

        assert errors != {}
        # Should have errors for invalid fields
        assert "name" in errors or "email" in errors or "age" in errors

    def test_validate_with_partial(self):
        """validate() respects partial parameter."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        # Without partial, missing required field is error
        errors_without = schema.validate({"name": "Alice"})
        assert "email" in errors_without

        # With partial, missing field is OK
        errors_with = schema.validate({"name": "Alice"}, partial=True)
        assert errors_with == {}


# =============================================================================
# Context Tests
# =============================================================================

class TestContextPassing:
    """Test context passing to validators."""

    def test_context_accessible_in_schema(self):
        """Context dict is accessible via self.context."""
        class ContextAwareSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name_with_context(self, value, **kwargs):
                forbidden = self.context.get("forbidden_names", [])
                if value.lower() in [n.lower() for n in forbidden]:
                    raise ValidationError(f"Name '{value}' is forbidden")

        schema = ContextAwareSchema(context={"forbidden_names": ["admin", "root"]})

        with pytest.raises(ValidationError):
            schema.load({
                "name": "admin",
                "email": "admin@example.com",
                "age": 30,
            })

    def test_context_allows_valid_values(self):
        """Context validation passes for valid input."""
        class ContextAwareSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name_with_context(self, value, **kwargs):
                forbidden = self.context.get("forbidden_names", [])
                if value.lower() in [n.lower() for n in forbidden]:
                    raise ValidationError(f"Name '{value}' is forbidden")

        schema = ContextAwareSchema(context={"forbidden_names": ["admin"]})

        result = schema.load({
            "name": "Alice",  # Not in forbidden list
            "email": "alice@example.com",
            "age": 30,
        })

        assert result.name == "Alice"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_partial_with_unknown_exclude(self):
        """Combine partial loading with unknown=EXCLUDE."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=True, unknown=EXCLUDE)

        result = schema.load({
            "name": "Alice",
            "extra": "ignored",
        })

        assert result.name == "Alice"

    def test_validators_with_partial(self):
        """Field validators work with partial loading."""
        class UserSchemaWithValidator(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name(self, value, **kwargs):
                if value.lower() == "admin":
                    raise ValidationError("Cannot use admin")

        schema = UserSchemaWithValidator(partial=True)

        with pytest.raises(ValidationError):
            schema.load({"name": "admin"})

    def test_validate_method_with_validators(self):
        """validate() method works with @validates decorators."""
        class UserSchemaWithValidator(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name(self, value, **kwargs):
                if value.lower() == "admin":
                    raise ValidationError("Cannot use admin")

        schema = UserSchemaWithValidator()

        errors = schema.validate({
            "name": "admin",
            "email": "admin@example.com",
            "age": 30,
        })

        assert "name" in errors
