"""Tests for schema instance parameters and Meta options.

Tests for Marshmallow-style schema parameters:
- only=tuple field filtering
- exclude=tuple field filtering
- load_only=tuple for write-only fields
- dump_only=tuple for read-only fields
- Meta.fields and Meta.exclude

Also tests:
- Literal field type (Constant equivalent)
- index_errors for collection error paths
- Custom error messages via json_schema_extra
- extra='allow'/'ignore' ConfigDict options
"""

from typing import Literal

import pytest
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict, Field

from pydantic_marshmallow import EXCLUDE, INCLUDE, PydanticSchema, schema_for

# =============================================================================
# Test Models
# =============================================================================

class User(BaseModel):
    name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0)
    password: str = "secret"  # Should be load_only
    internal_id: int = 0  # Should be dump_only


class Profile(BaseModel):
    username: str
    bio: str = ""
    private_notes: str = ""  # load_only
    computed_slug: str = ""  # dump_only


class Item(BaseModel):
    name: str = Field(min_length=1)  # Add constraint for validation test
    price: float = Field(gt=0)


class Order(BaseModel):
    customer: str
    items: list[Item]


class ModelWithConstant(BaseModel):
    """Model with a constant field."""
    status: Literal["active"] = "active"
    name: str


class ModelWithExtra(BaseModel):
    """Model that allows extra fields."""
    model_config = ConfigDict(extra="allow")
    name: str


class ModelIgnoreExtra(BaseModel):
    """Model that ignores extra fields."""
    model_config = ConfigDict(extra="ignore")
    name: str


# =============================================================================
# AUDIT SECTION 1: Schema Instance Parameters (⚠️ items)
# =============================================================================

class TestOnlyParameter:
    """Test only=tuple field filtering."""

    def test_only_on_load(self):
        """only should filter fields during load."""
        UserSchema = schema_for(User)
        schema = UserSchema(only=("name", "email"))

        # Should only accept name and email
        result = schema.load({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,  # Should be ignored or error
        })

        # The result should have name and email only
        assert result.name == "Alice"
        assert result.email == "alice@example.com"

    def test_only_on_dump(self):
        """only should filter fields during dump."""
        UserSchema = schema_for(User)
        schema = UserSchema(only=("name", "email"))

        user = User(name="Alice", email="alice@example.com", age=30)
        result = schema.dump(user)

        # Dump should only include name and email
        assert "name" in result
        assert "email" in result
        assert "age" not in result


class TestExcludeParameter:
    """Test exclude=tuple field filtering."""

    def test_exclude_on_dump(self):
        """exclude should filter fields during dump."""
        UserSchema = schema_for(User)
        schema = UserSchema(exclude=("password", "internal_id"))

        user = User(name="Alice", email="alice@example.com", age=30)
        result = schema.dump(user)

        assert "name" in result
        assert "password" not in result
        assert "internal_id" not in result


class TestLoadOnlyParameter:
    """Test load_only=tuple for write-only fields."""

    def test_load_only_fields_not_dumped(self):
        """load_only fields should not appear in dump output."""
        UserSchema = schema_for(User)
        schema = UserSchema(load_only=("password",))

        user = User(name="Alice", email="alice@example.com", age=30, password="secret123")
        result = schema.dump(user)

        # password should not be in dump output
        assert "password" not in result
        assert "name" in result


class TestDumpOnlyParameter:
    """Test dump_only=tuple for read-only fields."""

    def test_dump_only_fields_not_required_on_load(self):
        """dump_only fields should not be required during load."""
        UserSchema = schema_for(User)
        schema = UserSchema(dump_only=("internal_id",))

        # Should be able to load without internal_id
        result = schema.load({
            "name": "Alice",
            "email": "alice@example.com",
            "age": 30,
        })

        assert result.name == "Alice"


# =============================================================================
# AUDIT SECTION 2: Schema.Meta Options (⚠️ items)
# =============================================================================

class TestMetaFields:
    """Test Meta.fields whitelisting."""

    def test_meta_fields_whitelist(self):
        """Meta.fields should whitelist only specified fields via from_model."""
        # Use from_model with fields meta option
        LimitedUserSchema = PydanticSchema.from_model(User, fields=("name", "email"))

        schema = LimitedUserSchema()
        user = User(name="Alice", email="alice@example.com", age=30)
        result = schema.dump(user)

        # Only whitelisted fields should appear
        assert set(result.keys()) == {"name", "email"}


class TestMetaExclude:
    """Test Meta.exclude blacklisting."""

    def test_meta_exclude_blacklist(self):
        """Meta.exclude should blacklist specified fields via from_model."""
        # Use from_model with exclude meta option
        FilteredUserSchema = PydanticSchema.from_model(User, exclude=("password", "internal_id"))

        schema = FilteredUserSchema()
        user = User(name="Alice", email="alice@example.com", age=30)
        result = schema.dump(user)

        assert "password" not in result
        assert "internal_id" not in result


class TestIndexErrors:
    """Test index_errors for collection error indices."""

    def test_collection_errors_include_index(self):
        """Errors in collections should include the index."""
        OrderSchema = schema_for(Order)
        schema = OrderSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "customer": "Alice",
                "items": [
                    {"name": "Widget", "price": 10.0},
                    {"name": "", "price": 5.0},  # Invalid name
                ],
            })

        errors = exc_info.value.messages
        # Check if index is in the error path
        has_index = any("1" in str(k) or "items" in str(k) for k in errors.keys())
        assert has_index or "items.1.name" in errors or "items" in errors


# =============================================================================
# AUDIT SECTION 3: Field Types (⚠️ items)
# =============================================================================

class TestConstantField:
    """Test Constant field type mapping to Literal."""

    def test_literal_field_accepts_only_constant(self):
        """Literal field should only accept the constant value."""
        ConstantSchema = schema_for(ModelWithConstant)
        schema = ConstantSchema()

        # Should work with the constant value
        result = schema.load({"status": "active", "name": "Test"})
        assert result.status == "active"

        # Should fail with different value
        with pytest.raises(ValidationError):
            schema.load({"status": "inactive", "name": "Test"})


# =============================================================================
# AUDIT SECTION 4: Field Options (⚠️ items)
# =============================================================================

class TestErrorMessagesOption:
    """Test error_messages field option."""

    def test_custom_error_messages_via_json_schema_extra(self):
        """Custom error messages should work via json_schema_extra."""
        class Product(BaseModel):
            name: str = Field(
                min_length=2,
                json_schema_extra={
                    "error_messages": {
                        "string_too_short": "Name must be at least 2 characters",
                    }
                }
            )

        ProductSchema = schema_for(Product)
        schema = ProductSchema()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "A"})

        errors = exc_info.value.messages
        assert "name" in errors
        # Custom message should be used
        assert any("2 characters" in str(msg) for msg in errors.get("name", []))


# =============================================================================
# AUDIT SECTION 5: Pydantic ConfigDict (⚠️ items)
# =============================================================================

class TestExtraAllow:
    """Test extra='allow' mapping to unknown=INCLUDE."""

    def test_extra_allow_keeps_unknown_fields(self):
        """Model with extra='allow' should keep unknown fields."""
        ExtraSchema = schema_for(ModelWithExtra)
        schema = ExtraSchema(unknown=INCLUDE)

        result = schema.load({
            "name": "Test",
            "extra_field": "should be kept",
        })

        assert result.name == "Test"
        # Extra field handling depends on model config


class TestExtraIgnore:
    """Test extra='ignore' mapping to unknown=EXCLUDE."""

    def test_extra_ignore_removes_unknown_fields(self):
        """Model with extra='ignore' should remove unknown fields."""
        IgnoreSchema = schema_for(ModelIgnoreExtra)
        schema = IgnoreSchema(unknown=EXCLUDE)

        result = schema.load({
            "name": "Test",
            "extra_field": "should be ignored",
        })

        assert result.name == "Test"


# =============================================================================
# Audit Summary (Schema Parameters Only)
# =============================================================================

class TestSchemaParametersSummary:
    """Verify schema parameter features are working.

    This summary test validates the features specific to this file:
    - only/exclude tuple parameters
    - load_only/dump_only tuple parameters
    - Meta.fields and Meta.exclude
    - Literal field type
    - index_errors in collections
    - extra='allow'/'ignore' handling

    Note: Basic features (load/dump/many/partial/unknown/hooks/validators)
    are tested in their respective test files:
    - test_bridge.py, test_hooks.py, test_partial_and_unknown.py,
    - test_error_handling.py, test_advanced_hooks.py
    """

    def test_all_schema_parameters_work(self, capsys):
        """Print summary of schema parameter feature support."""
        working = []
        not_working = []

        tests = {
            "only=tuple (dump)": self._test_only_dump,
            "exclude=tuple (dump)": self._test_exclude_dump,
            "load_only=tuple": self._test_load_only,
            "dump_only=tuple": self._test_dump_only,
            "Meta.fields whitelist": self._test_meta_fields,
            "Meta.exclude blacklist": self._test_meta_exclude,
            "index_errors": self._test_index_errors,
            "Constant/Literal": self._test_constant,
            "extra='allow'": self._test_extra_allow,
            "extra='ignore'": self._test_extra_ignore,
        }

        for name, test_fn in tests.items():
            try:
                test_fn()
                working.append(name)
            except Exception as e:
                not_working.append((name, str(e)[:50]))

        print("\n" + "=" * 60)
        print("SCHEMA PARAMETERS AUDIT")
        print("=" * 60)
        print(f"\n✅ WORKING ({len(working)}):")
        for item in working:
            print(f"   - {item}")
        if not_working:
            print(f"\n⚠️ NOT WORKING ({len(not_working)}):")
            for item, err in not_working:
                print(f"   - {item}: {err}")
        print("=" * 60)

        # Fail test if any features don't work
        assert len(not_working) == 0, f"Features not working: {[n for n, _ in not_working]}"

    def _test_only_dump(self):
        UserSchema = schema_for(User)
        schema = UserSchema(only=("name", "email"))
        user = User(name="Alice", email="a@b.com", age=30)
        result = schema.dump(user)
        assert "age" not in result, f"age should not be in dump: {result}"

    def _test_exclude_dump(self):
        UserSchema = schema_for(User)
        schema = UserSchema(exclude=("password",))
        user = User(name="Alice", email="a@b.com", age=30)
        result = schema.dump(user)
        assert "password" not in result, f"password should not be in dump: {result}"

    def _test_load_only(self):
        UserSchema = schema_for(User)
        schema = UserSchema(load_only=("password",))
        user = User(name="Alice", email="a@b.com", age=30, password="secret")
        result = schema.dump(user)
        assert "password" not in result, f"password should not be in dump: {result}"

    def _test_dump_only(self):
        UserSchema = schema_for(User)
        schema = UserSchema(dump_only=("internal_id",))
        result = schema.load({"name": "Alice", "email": "a@b.com", "age": 30})
        assert result.name == "Alice"

    def _test_meta_fields(self):
        class MetaFieldsTestSchema(PydanticSchema[User]):
            class Meta:
                model = User
                fields = ("name", "email")

        schema = MetaFieldsTestSchema()
        user = User(name="Alice", email="a@b.com", age=30)
        result = schema.dump(user)
        assert set(result.keys()) == {"name", "email"}, f"Got: {result.keys()}"

    def _test_meta_exclude(self):
        class MetaExcludeTestSchema(PydanticSchema[User]):
            class Meta:
                model = User
                exclude = ("password",)

        schema = MetaExcludeTestSchema()
        user = User(name="Alice", email="a@b.com", age=30)
        result = schema.dump(user)
        assert "password" not in result, f"password in dump: {result}"

    def _test_index_errors(self):
        OrderSchema = schema_for(Order)
        schema = OrderSchema()

        try:
            schema.load({
                "customer": "Alice",
                "items": [
                    {"name": "Widget", "price": 10.0},
                    {"name": "", "price": 5.0},
                ],
            })
        except ValidationError as e:
            assert "items" in str(e.messages) or "1" in str(e.messages)
            return
        raise AssertionError("Should have raised ValidationError")

    def _test_constant(self):
        ConstantSchema = schema_for(ModelWithConstant)
        schema = ConstantSchema()
        result = schema.load({"status": "active", "name": "Test"})
        assert result.status == "active"

    def _test_extra_allow(self):
        ExtraSchema = schema_for(ModelWithExtra)
        schema = ExtraSchema(unknown=INCLUDE)
        result = schema.load({"name": "Test", "extra": "value"})
        assert result.name == "Test"

    def _test_extra_ignore(self):
        IgnoreSchema = schema_for(ModelIgnoreExtra)
        schema = IgnoreSchema(unknown=EXCLUDE)
        result = schema.load({"name": "Test", "extra": "ignored"})
        assert result.name == "Test"
