"""Tests for validation features.

Consolidated tests for:
- Field constraints (min_length, max_length, ge, le, gt, lt, pattern)
- Type coercion
- Validation error handling

Uses parameterization for comprehensive constraint coverage.
"""

import pytest
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, Field

from pydantic_marshmallow import schema_for

# =============================================================================
# Shared Test Data (from conftest.py, but imported models redefined for clarity)
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


# =============================================================================
# String Constraint Tests (parameterized)
# =============================================================================

class TestStringConstraints:
    """Test string field constraints with parameterization."""

    @pytest.mark.parametrize(
        "min_len,max_len,value,should_pass",
        [
            (1, 100, "valid", True),
            (1, 100, "", False),  # min_length violation
            (1, 100, "a", True),  # boundary: exactly min
            (1, 5, "12345", True),  # boundary: exactly max
            (1, 5, "123456", False),  # max_length violation
            (3, 10, "ab", False),  # min_length violation
            (None, None, "", True),  # no constraints
        ],
        ids=[
            "valid_string",
            "empty_fails_min",
            "boundary_min",
            "boundary_max",
            "exceeds_max",
            "below_min",
            "no_constraints",
        ],
    )
    def test_string_length_constraints(self, min_len, max_len, value, should_pass):
        """Test min_length and max_length string constraints."""
        field_kwargs = {}
        if min_len is not None:
            field_kwargs["min_length"] = min_len
        if max_len is not None:
            field_kwargs["max_length"] = max_len

        class Model(BaseModel):
            value: str = Field(**field_kwargs) if field_kwargs else Field()

        schema = schema_for(Model)()

        if should_pass:
            result = schema.load({"value": value})
            assert result.value == value
        else:
            with pytest.raises(ValidationError) as exc_info:
                schema.load({"value": value})
            assert "value" in exc_info.value.messages

    @pytest.mark.parametrize(
        "pattern,value,should_pass",
        [
            (r"^\d{5}$", "12345", True),
            (r"^\d{5}$", "1234", False),
            (r"^\d{5}$", "123456", False),
            (r"^\d{5}$", "abcde", False),
            (r"^[a-z]+$", "hello", True),
            (r"^[a-z]+$", "Hello", False),
            (r"^[\w\.-]+@[\w\.-]+\.\w+$", "test@example.com", True),
            (r"^[\w\.-]+@[\w\.-]+\.\w+$", "invalid", False),
        ],
        ids=[
            "zip_valid",
            "zip_too_short",
            "zip_too_long",
            "zip_letters",
            "lowercase_valid",
            "lowercase_uppercase",
            "email_valid",
            "email_invalid",
        ],
    )
    def test_string_pattern_constraints(self, pattern, value, should_pass):
        """Test pattern (regex) string constraints."""
        class Model(BaseModel):
            value: str = Field(pattern=pattern)

        schema = schema_for(Model)()

        if should_pass:
            result = schema.load({"value": value})
            assert result.value == value
        else:
            with pytest.raises(ValidationError):
                schema.load({"value": value})


# =============================================================================
# Numeric Constraint Tests (parameterized)
# =============================================================================

class TestNumericConstraints:
    """Test numeric field constraints with parameterization."""

    @pytest.mark.parametrize(
        "constraint_type,constraint_value,test_value,should_pass",
        [
            # ge (greater than or equal)
            ("ge", 0, 0, True),  # boundary: equal
            ("ge", 0, 1, True),  # above
            ("ge", 0, -1, False),  # below
            ("ge", 18, 18, True),
            ("ge", 18, 17, False),
            # le (less than or equal)
            ("le", 100, 100, True),  # boundary: equal
            ("le", 100, 99, True),  # below
            ("le", 100, 101, False),  # above
            # gt (greater than)
            ("gt", 0, 1, True),
            ("gt", 0, 0, False),  # boundary: equal fails
            ("gt", 0, -1, False),
            # lt (less than)
            ("lt", 100, 99, True),
            ("lt", 100, 100, False),  # boundary: equal fails
            ("lt", 100, 101, False),
            # multiple_of
            ("multiple_of", 2, 4, True),
            ("multiple_of", 2, 3, False),
            ("multiple_of", 5, 0, True),
        ],
        ids=[
            "ge_equal",
            "ge_above",
            "ge_below_fails",
            "ge_age_valid",
            "ge_age_invalid",
            "le_equal",
            "le_below",
            "le_above_fails",
            "gt_above",
            "gt_equal_fails",
            "gt_below_fails",
            "lt_below",
            "lt_equal_fails",
            "lt_above_fails",
            "multiple_of_valid",
            "multiple_of_invalid",
            "multiple_of_zero",
        ],
    )
    def test_numeric_constraints(self, constraint_type, constraint_value, test_value, should_pass):
        """Test ge, le, gt, lt, multiple_of numeric constraints."""
        class Model(BaseModel):
            value: int = Field(**{constraint_type: constraint_value})

        schema = schema_for(Model)()

        if should_pass:
            result = schema.load({"value": test_value})
            assert result.value == test_value
        else:
            with pytest.raises(ValidationError):
                schema.load({"value": test_value})

    @pytest.mark.parametrize(
        "ge_val,le_val,test_value,should_pass",
        [
            (0, 100, 50, True),
            (0, 100, 0, True),  # lower boundary
            (0, 100, 100, True),  # upper boundary
            (0, 100, -1, False),  # below range
            (0, 100, 101, False),  # above range
            (1, 5, 3, True),  # narrow range
        ],
        ids=[
            "mid_range",
            "lower_boundary",
            "upper_boundary",
            "below_range",
            "above_range",
            "narrow_range_mid",
        ],
    )
    def test_combined_numeric_constraints(self, ge_val, le_val, test_value, should_pass):
        """Test combined ge and le constraints (range validation)."""
        class Model(BaseModel):
            value: int = Field(ge=ge_val, le=le_val)

        schema = schema_for(Model)()

        if should_pass:
            result = schema.load({"value": test_value})
            assert result.value == test_value
        else:
            with pytest.raises(ValidationError):
                schema.load({"value": test_value})


# =============================================================================
# Type Coercion Tests (parameterized)
# =============================================================================

class TestTypeCoercion:
    """Test Pydantic's automatic type coercion."""

    @pytest.mark.parametrize(
        "input_value,expected_value",
        [
            ("123", 123),
            (123, 123),
            (123.0, 123),
            ("0", 0),
            ("-42", -42),
        ],
        ids=["string_to_int", "int_unchanged", "float_to_int", "zero_string", "negative_string"],
    )
    def test_int_coercion(self, input_value, expected_value):
        """Test string/float to int coercion."""
        class Model(BaseModel):
            value: int

        schema = schema_for(Model)()
        result = schema.load({"value": input_value})
        assert result.value == expected_value

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("true", True),
            ("True", True),
            ("1", True),
            (1, True),
            ("false", False),
            ("False", False),
            ("0", False),
            (0, False),
            (True, True),
            (False, False),
        ],
        ids=[
            "true_lower",
            "true_title",
            "one_string",
            "one_int",
            "false_lower",
            "false_title",
            "zero_string",
            "zero_int",
            "bool_true",
            "bool_false",
        ],
    )
    def test_bool_coercion(self, input_value, expected):
        """Test various values to bool coercion."""
        class Model(BaseModel):
            value: bool

        schema = schema_for(Model)()
        result = schema.load({"value": input_value})
        assert result.value is expected

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            (42, 42.0),
            ("3.14", 3.14),
            (0, 0.0),
        ],
        ids=["int_to_float", "string_to_float", "zero"],
    )
    def test_float_coercion(self, input_value, expected):
        """Test int/string to float coercion."""
        class Model(BaseModel):
            value: float

        schema = schema_for(Model)()
        result = schema.load({"value": input_value})
        assert result.value == expected


# =============================================================================
# Collection Constraint Tests (parameterized)
# =============================================================================

class TestCollectionConstraints:
    """Test list/collection constraints."""

    @pytest.mark.parametrize(
        "min_items,max_items,items,should_pass",
        [
            (1, 5, ["a"], True),  # exactly min
            (1, 5, ["a", "b", "c", "d", "e"], True),  # exactly max
            (1, 5, [], False),  # below min
            (1, 5, ["a", "b", "c", "d", "e", "f"], False),  # above max
            (0, None, [], True),  # empty allowed
            (None, 3, ["a", "b"], True),  # no min
        ],
        ids=[
            "exactly_min",
            "exactly_max",
            "below_min_fails",
            "above_max_fails",
            "empty_allowed",
            "no_min_constraint",
        ],
    )
    def test_list_length_constraints(self, min_items, max_items, items, should_pass):
        """Test min_length and max_length on list fields."""
        field_kwargs = {}
        if min_items is not None:
            field_kwargs["min_length"] = min_items
        if max_items is not None:
            field_kwargs["max_length"] = max_items

        class Model(BaseModel):
            items: list[str] = Field(**field_kwargs) if field_kwargs else Field()

        schema = schema_for(Model)()

        if should_pass:
            result = schema.load({"items": items})
            assert result.items == items
        else:
            with pytest.raises(ValidationError):
                schema.load({"items": items})


# =============================================================================
# Empty/None Value Tests (parameterized)
# =============================================================================

class TestEmptyAndNoneValues:
    """Test handling of empty and None values."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("", ""),
            (None, None),
            ("   ", "   "),
        ],
        ids=["empty_string", "none", "whitespace"],
    )
    def test_optional_string_values(self, value, expected):
        """Test Optional[str] accepts empty/None values."""
        class Model(BaseModel):
            value: str | None = None

        schema = schema_for(Model)()
        result = schema.load({"value": value})
        assert result.value == expected

    @pytest.mark.parametrize(
        "field_type,empty_value,should_pass",
        [
            (list[str], [], True),
            (dict, {}, True),
            (str, "", True),
            (str | None, None, True),
            (int | None, None, True),
        ],
        ids=["empty_list", "empty_dict", "empty_string", "none_string", "none_int"],
    )
    def test_empty_collection_values(self, field_type, empty_value, should_pass):
        """Test empty collections are handled correctly."""
        class Model(BaseModel):
            value: field_type

        schema = schema_for(Model)()
        result = schema.load({"value": empty_value})
        assert result.value == empty_value


# =============================================================================
# Multiple Errors Accumulation
# =============================================================================

class TestMultipleErrorsAccumulation:
    """Test that multiple validation errors are accumulated."""

    def test_multiple_field_errors(self, validated_user_schema):
        """All field errors should be reported, not just the first."""
        with pytest.raises(ValidationError) as exc_info:
            validated_user_schema.load({
                "name": "",  # min_length=1 violation
                "age": -5,  # ge=0 violation
                "email": "invalid",  # email format violation
                "score": 150,  # le=100 violation
            })

        errors = exc_info.value.messages
        # Should have multiple error fields
        assert len(errors) >= 2, f"Expected multiple errors, got: {errors}"

    def test_nested_errors_include_path(self):
        """Nested validation errors should include the field path."""
        class Item(BaseModel):
            name: str = Field(min_length=1)
            price: float = Field(gt=0)

        class Order(BaseModel):
            customer: str
            items: list[Item]

        schema = schema_for(Order)()

        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "customer": "Alice",
                "items": [
                    {"name": "Valid", "price": 10.0},
                    {"name": "", "price": 5.0},  # name min_length violation
                ],
            })

        error_str = str(exc_info.value.messages)
        assert "items" in error_str or "name" in error_str


# =============================================================================
# Using Shared Fixtures
# =============================================================================

class TestWithSharedFixtures:
    """Demonstrate using shared fixtures from conftest."""

    def test_simple_user_load(self, simple_user_schema):
        """Use pre-built simple_user_schema fixture."""
        result = simple_user_schema.load(SIMPLE_USER_DATA)
        assert result.name == "Alice Smith"
        assert result.age == 30

    def test_validated_user_load(self, validated_user_schema):
        """Use pre-built validated_user_schema fixture."""
        result = validated_user_schema.load(VALIDATED_USER_DATA)
        assert result.name == "Alice Smith"
        assert result.score == 95.5

    def test_with_data_factory(self, simple_user_schema, user_data_factory):
        """Use factory fixture for custom test data."""
        data = user_data_factory(name="Custom User", age=25)
        result = simple_user_schema.load(data)
        assert result.name == "Custom User"
        assert result.age == 25
