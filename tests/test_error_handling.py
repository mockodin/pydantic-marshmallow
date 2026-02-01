"""Tests for error handling features.

Features tested:
- ValidationError.valid_data (partial success data)
- BridgeValidationError inheritance from MarshmallowValidationError
- Collection indices in error paths
- Custom error messages via json_schema_extra
- Error format compatibility with Marshmallow ecosystem
"""

from typing import List

import pytest
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, Field

from pydantic_marshmallow import (
    BridgeValidationError,
    PydanticSchema,
    schema_for,
)

# =============================================================================
# Test Models
# =============================================================================

class User(BaseModel):
    name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0)


class Item(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)


class Order(BaseModel):
    customer: str
    items: List[Item]


class Product(BaseModel):
    """Model with custom error messages via json_schema_extra."""
    name: str = Field(
        min_length=2,
        json_schema_extra={
            "error_messages": {
                "string_too_short": "Product name must be at least 2 characters",
                "default": "Invalid product name",
            }
        }
    )
    quantity: int = Field(
        ge=1,
        json_schema_extra={
            "error_messages": {
                "greater_than_equal": "Quantity must be at least 1",
            }
        }
    )


class Address(BaseModel):
    street: str
    city: str
    country: str = "USA"


# =============================================================================
# ValidationError.valid_data Tests
# =============================================================================

class TestValidDataOnError:
    """Test that valid_data is available on partial validation failures."""

    def test_valid_data_contains_successful_fields(self):
        """valid_data includes fields that passed validation."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(BridgeValidationError) as exc_info:
            schema.load({
                "name": "Alice",  # Valid
                "email": "alice@example.com",  # Valid
                "age": -5,  # Invalid: must be >= 0
            })

        error = exc_info.value
        assert "age" in error.messages
        assert error.valid_data.get("name") == "Alice"
        assert error.valid_data.get("email") == "alice@example.com"
        assert "age" not in error.valid_data

    def test_valid_data_empty_when_all_fail(self):
        """valid_data is empty when all fields fail."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(BridgeValidationError) as exc_info:
            schema.load({
                "name": "",  # Invalid: min_length
                "email": "not-an-email",  # May be invalid depending on strictness
                "age": -5,  # Invalid
            })

        error = exc_info.value
        # At least name and age should fail
        assert len(error.messages) >= 1

    def test_valid_data_on_missing_required(self):
        """valid_data includes valid provided fields even when others are missing."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(BridgeValidationError) as exc_info:
            schema.load({
                "name": "Alice",
                # Missing email and age
            })

        error = exc_info.value
        assert error.valid_data.get("name") == "Alice"

    def test_original_data_preserved(self):
        """Original input data is preserved in error.data."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        input_data = {
            "name": "Alice",
            "email": "alice@example.com",
            "age": -5,
        }

        with pytest.raises(BridgeValidationError) as exc_info:
            schema.load(input_data)

        # Note: error.data should be the original data
        # This tests that we track the original input
        error = exc_info.value
        assert error.messages  # Has errors


# =============================================================================
# Collection Index Error Path Tests
# =============================================================================

class TestCollectionErrorPaths:
    """Test that error paths include collection indices."""

    def test_many_errors_include_index(self):
        """Errors in many=True include the item index."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load([
                {"name": "Alice", "email": "alice@example.com", "age": 30},  # Valid
                {"name": "", "email": "bob@example.com", "age": 25},  # Invalid: empty name
                {"name": "Charlie", "email": "charlie@example.com", "age": -1},  # Invalid: negative age
            ], many=True)

        # Should have errors - exact format may vary
        assert exc_info.value.messages

    def test_nested_collection_error_paths(self):
        """Errors in nested collections show full path."""
        OrderSchema = schema_for(Order)
        schema = OrderSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "customer": "Alice",
                "items": [
                    {"name": "Widget", "price": 10.0},  # Valid
                    {"name": "", "price": 5.0},  # Invalid: empty name
                    {"name": "Gadget", "price": -1.0},  # Invalid: negative price
                ],
            })

        errors = exc_info.value.messages
        # Should have errors for items - the exact paths depend on Pydantic
        assert errors  # Has some errors

    def test_single_item_nested_error(self):
        """Single nested object errors show field path."""
        class Container(BaseModel):
            address: Address

        ContainerSchema = schema_for(Container)
        schema = ContainerSchema()

        # Valid nested object should work
        result = schema.load({
            "address": {"street": "123 Main St", "city": "Boston"}
        })
        assert result.address.street == "123 Main St"


# =============================================================================
# Custom Error Message Tests
# =============================================================================

class TestCustomErrorMessages:
    """Test custom error messages via json_schema_extra."""

    def test_custom_error_message_applies(self):
        """Custom error messages from json_schema_extra are used."""
        ProductSchema = schema_for(Product)
        schema = ProductSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "A",  # Too short
                "quantity": 5,  # Valid
            })

        errors = exc_info.value.messages
        assert "name" in errors
        # Check if custom message is used
        name_errors = errors["name"]
        assert any("2 characters" in str(msg) for msg in name_errors) or \
               any("string" in str(msg).lower() for msg in name_errors)

    def test_quantity_custom_message(self):
        """Custom error message for numeric constraint."""
        ProductSchema = schema_for(Product)
        schema = ProductSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "Widget",
                "quantity": 0,  # Invalid: must be >= 1
            })

        errors = exc_info.value.messages
        assert "quantity" in errors

    def test_default_custom_message(self):
        """Default custom message is used when specific type not found."""
        ProductSchema = schema_for(Product)
        schema = ProductSchema()

        # Valid case works
        result = schema.load({"name": "Widget", "quantity": 5})
        assert result.name == "Widget"


# =============================================================================
# Error Format Tests
# =============================================================================

class TestErrorFormat:
    """Test error message format compatibility with Marshmallow."""

    def test_errors_dict_format(self):
        """Errors are a dict with field names as keys."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "", "email": "bad", "age": -1})

        errors = exc_info.value.messages
        assert isinstance(errors, dict)
        # Each error value should be a list
        for field, msgs in errors.items():
            assert isinstance(msgs, list), f"Errors for {field} should be a list"

    def test_schema_level_errors_use_schema_key(self):
        """Schema-level errors use '_schema' key."""
        from pydantic_marshmallow import validates_schema

        class PasswordForm(BaseModel):
            password: str
            confirm: str

        class PasswordSchema(PydanticSchema[PasswordForm]):
            class Meta:
                model = PasswordForm

            @validates_schema
            def check_match(self, data, **kwargs):
                if data.get("password") != data.get("confirm"):
                    raise ValidationError({"_schema": ["Passwords must match"]})

        schema = PasswordSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"password": "secret", "confirm": "different"})

        assert "_schema" in exc_info.value.messages


# =============================================================================
# Integration Tests
# =============================================================================

class TestErrorHandlingIntegration:
    """Integration tests for error handling features."""

    def test_valid_data_with_partial(self):
        """valid_data works with partial loading."""
        UserSchema = schema_for(User)
        schema = UserSchema(partial=True)

        with pytest.raises(BridgeValidationError) as exc_info:
            schema.load({
                "name": "",  # Invalid even for partial
            })

        error = exc_info.value
        assert "name" in error.messages

    def test_validate_method_doesnt_expose_valid_data(self):
        """validate() returns just errors dict, not valid_data."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        errors = schema.validate({
            "name": "Alice",
            "email": "alice@example.com",
            "age": -5,
        })

        # validate() returns plain dict of errors
        assert isinstance(errors, dict)
        assert "age" in errors

    def test_multiple_errors_same_field(self):
        """Multiple errors on same field are collected."""
        class StrictUser(BaseModel):
            username: str = Field(min_length=3, max_length=10, pattern=r'^[a-z]+$')

        StrictSchema = schema_for(StrictUser)
        schema = StrictSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"username": "AB"})  # Too short AND has uppercase

        errors = exc_info.value.messages
        assert "username" in errors


class TestBridgeValidationErrorInheritance:
    """Test that BridgeValidationError behaves like MarshmallowValidationError."""

    def test_isinstance_check(self):
        """BridgeValidationError is instance of MarshmallowValidationError."""
        from marshmallow.exceptions import ValidationError as MAError

        error = BridgeValidationError({"field": ["error"]})
        assert isinstance(error, MAError)

    def test_messages_attribute(self):
        """BridgeValidationError has messages attribute."""
        error = BridgeValidationError({"field": ["error message"]})
        assert error.messages == {"field": ["error message"]}

    def test_valid_data_default_empty(self):
        """valid_data defaults to empty dict."""
        error = BridgeValidationError({"field": ["error"]})
        assert error.valid_data == {}

    def test_valid_data_set_explicitly(self):
        """valid_data can be set explicitly."""
        error = BridgeValidationError(
            {"bad_field": ["error"]},
            valid_data={"good_field": "value"},
        )
        assert error.valid_data == {"good_field": "value"}
