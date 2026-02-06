"""Tests for advanced Marshmallow hook features.

Features tested:
- handle_error() override for custom error handling
- on_bind_field() override for field customization
- skip_on_field_errors parameter for @validates_schema
- Complete validation flow order verification
"""


import pytest
from marshmallow import fields as ma_fields
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, Field

from pydantic_marshmallow import PydanticSchema, schema_for, validates, validates_schema

# =============================================================================
# Test Models
# =============================================================================

class User(BaseModel):
    name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0)


class Product(BaseModel):
    name: str
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)


class PasswordForm(BaseModel):
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


# =============================================================================
# handle_error() Tests
# =============================================================================

class TestHandleError:
    """Test handle_error() override support."""

    def test_handle_error_is_called_on_validation_error(self):
        """handle_error() is called when validation fails."""
        errors_received = []

        class UserSchemaWithHandler(PydanticSchema[User]):
            class Meta:
                model = User

            def handle_error(self, error, data, *, many, **kwargs):
                errors_received.append(error.messages)
                raise error

        schema = UserSchemaWithHandler()

        with pytest.raises(ValidationError):
            schema.load({"name": "", "email": "test@example.com", "age": 30})

        assert len(errors_received) >= 1

    def test_handle_error_receives_correct_data(self):
        """handle_error() receives the original input data."""
        received_data = []

        class UserSchemaWithHandler(PydanticSchema[User]):
            class Meta:
                model = User

            def handle_error(self, error, data, *, many, **kwargs):
                received_data.append(data)
                raise error

        schema = UserSchemaWithHandler()
        input_data = {"name": "", "email": "test@example.com", "age": 30}

        with pytest.raises(ValidationError):
            schema.load(input_data)

        assert len(received_data) >= 1

    def test_handle_error_can_transform_error(self):
        """handle_error() can transform the error before raising."""
        class UserSchemaWithTransform(PydanticSchema[User]):
            class Meta:
                model = User

            def handle_error(self, error, data, *, many, **kwargs):
                # Transform error messages
                transformed = {"validation_failed": ["Please check your input"]}
                raise ValidationError(transformed)

        schema = UserSchemaWithTransform()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "", "email": "test@example.com", "age": 30})

        assert "validation_failed" in exc_info.value.messages

    def test_handle_error_default_reraises(self):
        """Default handle_error() re-raises the error unchanged."""
        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "", "email": "test@example.com", "age": 30})

        # Should have original error structure
        assert "name" in exc_info.value.messages


# =============================================================================
# on_bind_field() Tests
# =============================================================================

class TestOnBindField:
    """Test on_bind_field() override support."""

    def test_on_bind_field_is_called_for_each_field(self):
        """on_bind_field() is called for each field during initialization."""
        bound_fields = []

        class UserSchemaWithBind(PydanticSchema[User]):
            class Meta:
                model = User

            def on_bind_field(self, field_name, field_obj):
                bound_fields.append(field_name)
                super().on_bind_field(field_name, field_obj)

        schema = UserSchemaWithBind()

        # Should have been called for each model field
        assert "name" in bound_fields
        assert "email" in bound_fields
        assert "age" in bound_fields

    def test_on_bind_field_can_modify_fields(self):
        """on_bind_field() can modify field properties."""
        class UserSchemaAllowNone(PydanticSchema[User]):
            class Meta:
                model = User

            def on_bind_field(self, field_name, field_obj):
                # Make all fields allow None
                field_obj.allow_none = True
                super().on_bind_field(field_name, field_obj)

        schema = UserSchemaAllowNone()

        # Check that fields allow None
        for field_name, field_obj in schema.fields.items():
            assert field_obj.allow_none is True

    def test_on_bind_field_can_add_metadata(self):
        """on_bind_field() can add metadata to fields."""
        class UserSchemaWithMeta(PydanticSchema[User]):
            class Meta:
                model = User

            def on_bind_field(self, field_name, field_obj):
                # Add custom metadata
                if not hasattr(field_obj, 'metadata'):
                    field_obj.metadata = {}
                field_obj.metadata['bound'] = True
                super().on_bind_field(field_name, field_obj)

        schema = UserSchemaWithMeta()

        for field_name, field_obj in schema.fields.items():
            assert field_obj.metadata.get('bound') is True


# =============================================================================
# skip_on_field_errors Tests
# =============================================================================

class TestSkipOnFieldErrors:
    """Test skip_on_field_errors parameter for @validates_schema."""

    def test_skip_on_field_errors_true_skips_schema_validation(self):
        """With skip_on_field_errors=True (default), schema validators skip on field errors."""
        schema_validator_called = []

        class PasswordSchema(PydanticSchema[PasswordForm]):
            class Meta:
                model = PasswordForm

            @validates("password")
            def validate_password(self, value, **kwargs):
                if len(value) < 8:
                    raise ValidationError("Password must be at least 8 characters")

            @validates_schema(skip_on_field_errors=True)
            def validate_passwords_match(self, data, **kwargs):
                schema_validator_called.append(True)
                if data.get("password") != data.get("confirm_password"):
                    raise ValidationError({"_schema": ["Passwords must match"]})

        schema = PasswordSchema()

        # Field validation fails, so schema validator should be skipped
        with pytest.raises(ValidationError):
            schema.load({"password": "short", "confirm_password": "short"})

        # Schema validator should NOT have been called
        assert len(schema_validator_called) == 0

    def test_skip_on_field_errors_false_runs_schema_validation(self):
        """With skip_on_field_errors=False, schema validators run even with field errors."""
        schema_validator_called = []

        class PasswordSchema(PydanticSchema[PasswordForm]):
            class Meta:
                model = PasswordForm

            @validates("password")
            def validate_password(self, value, **kwargs):
                if "admin" in value.lower():
                    raise ValidationError("Password cannot contain 'admin'")

            @validates_schema(skip_on_field_errors=False)
            def validate_passwords_match(self, data, **kwargs):
                schema_validator_called.append(True)
                if data.get("password") != data.get("confirm_password"):
                    raise ValidationError({"_schema": ["Passwords must match"]})

        schema = PasswordSchema()

        # Trigger field error AND schema error
        with pytest.raises(ValidationError) as exc_info:
            schema.load({"password": "adminpass123", "confirm_password": "different"})

        # Schema validator should have been called
        assert len(schema_validator_called) == 1
        # Both errors should be present
        errors = exc_info.value.messages
        assert "password" in errors or "_schema" in errors

    def test_skip_on_field_errors_default_is_true(self):
        """Default value for skip_on_field_errors is True."""
        schema_validator_called = []

        class ProductSchema(PydanticSchema[Product]):
            class Meta:
                model = Product

            @validates("price")
            def validate_price(self, value, **kwargs):
                if value <= 0:
                    raise ValidationError("Price must be positive")

            @validates_schema  # No explicit skip_on_field_errors
            def validate_product(self, data, **kwargs):
                schema_validator_called.append(True)

        schema = ProductSchema()

        with pytest.raises(ValidationError):
            schema.load({"name": "Widget", "price": -10, "quantity": 5})

        # Schema validator should be skipped by default
        assert len(schema_validator_called) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestAdvancedIntegration:
    """Integration tests combining advanced features."""

    def test_handle_error_with_field_validators(self):
        """handle_error() works with @validates decorators."""
        errors_logged = []

        class UserSchemaWithLogging(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name(self, value, **kwargs):
                if value.lower() == "admin":
                    raise ValidationError("Cannot use admin as name")

            def handle_error(self, error, data, *, many, **kwargs):
                errors_logged.append({"error": error.messages, "data": data})
                raise error

        schema = UserSchemaWithLogging()

        with pytest.raises(ValidationError):
            schema.load({"name": "admin", "email": "admin@example.com", "age": 30})

        assert len(errors_logged) >= 1
        assert "name" in errors_logged[0]["error"]

    def test_on_bind_field_with_custom_fields(self):
        """on_bind_field() works with explicitly declared fields."""
        class UserSchemaWithCustomField(PydanticSchema[User]):
            # Explicitly declare a field
            nickname = ma_fields.String(load_default="Anonymous")

            class Meta:
                model = User

            def on_bind_field(self, field_name, field_obj):
                if field_name == "nickname":
                    field_obj.metadata["custom"] = True
                super().on_bind_field(field_name, field_obj)

        schema = UserSchemaWithCustomField()

        assert "nickname" in schema.fields
        assert schema.fields["nickname"].metadata.get("custom") is True

    def test_combined_validators_with_skip_on_field_errors(self):
        """Multiple @validates_schema with different skip_on_field_errors settings."""
        calls = {"always": 0, "skip": 0}

        class ProductSchema(PydanticSchema[Product]):
            class Meta:
                model = Product

            @validates("price")
            def validate_price(self, value, **kwargs):
                if value > 10000:
                    raise ValidationError("Price too high")

            @validates_schema(skip_on_field_errors=False)
            def always_validate(self, data, **kwargs):
                calls["always"] += 1

            @validates_schema(skip_on_field_errors=True)
            def skip_on_errors(self, data, **kwargs):
                calls["skip"] += 1

        schema = ProductSchema()

        # Trigger field error
        with pytest.raises(ValidationError):
            schema.load({"name": "Expensive", "price": 99999, "quantity": 1})

        # "always" should run, "skip" should not
        assert calls["always"] == 1
        assert calls["skip"] == 0


class TestValidationFlow:
    """Test the complete validation flow with all hooks."""

    def test_validation_order_with_all_hooks(self):
        """Verify the order: pre_load → pydantic → @validates → @validates_schema → post_load."""
        from marshmallow import post_load, pre_load

        call_order = []

        class OrderedSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def step1_pre_load(self, data, **kwargs):
                call_order.append("pre_load")
                return data

            @validates("name")
            def step2_validate_name(self, value, **kwargs):
                call_order.append("validates_name")

            @validates_schema
            def step3_validate_schema(self, data, **kwargs):
                call_order.append("validates_schema")

            @post_load
            def step4_post_load(self, data, **kwargs):
                call_order.append("post_load")
                return data

        schema = OrderedSchema()
        schema.load({"name": "Alice", "email": "alice@example.com", "age": 30})

        # Verify order
        assert call_order == ["pre_load", "validates_name", "validates_schema", "post_load"]
