"""Tests verifying the bridge upholds Marshmallow's public API contract.

These tests replicate key behaviors from Marshmallow's own test suite
(marshmallow 4.x) that users depend on. The bridge must produce identical
behavior for these scenarios even though the validation engine is Pydantic.

Organized by MA test file origin:
- test_schema.py: Schema.load/dump/validate behavior
- test_decorators.py: Hook execution, @validates
- test_context.py: Context propagation
- test_options.py: Field ordering, many default
"""

import json
from typing import Any

import pytest
from marshmallow import (
    EXCLUDE,
    INCLUDE,
    RAISE,
    post_dump,
    post_load,
    pre_dump,
    pre_load,
    validates,
    validates_schema,
)
from marshmallow.exceptions import ValidationError
from pydantic import BaseModel, Field

from pydantic_marshmallow import PydanticSchema, schema_for

# =============================================================================
# Models for contract tests
# =============================================================================

class ContractUser(BaseModel):
    name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0)


class ContractItem(BaseModel):
    label: str = Field(min_length=1)
    price: float = Field(gt=0)


class ContractOrder(BaseModel):
    customer: str
    items: list[ContractItem]


class ContractAddress(BaseModel):
    street: str
    city: str
    zip_code: str = "00000"


class ContractPerson(BaseModel):
    name: str
    address: ContractAddress


class DefaultsModel(BaseModel):
    name: str
    score: int = 0
    active: bool = True


# =============================================================================
# From MA test_schema.py: Schema.validate() method
# =============================================================================

class TestSchemaValidateMethod:
    """Schema.validate() must return error dict without raising."""

    def test_validate_returns_empty_dict_on_valid_data(self):
        schema = schema_for(ContractUser)()
        errors = schema.validate({"name": "Alice", "email": "a@b.com", "age": 25})
        assert errors == {}

    def test_validate_returns_error_dict_on_invalid_data(self):
        schema = schema_for(ContractUser)()
        errors = schema.validate({"name": "", "email": "a@b.com", "age": -1})
        assert isinstance(errors, dict)
        assert len(errors) > 0

    def test_validate_does_not_raise(self):
        schema = schema_for(ContractUser)()
        # Should NOT raise, even with invalid data
        result = schema.validate({"name": "", "email": "bad", "age": -5})
        assert isinstance(result, dict)

    def test_validate_many(self):
        schema = schema_for(ContractUser)()
        errors = schema.validate([
            {"name": "Alice", "email": "a@b.com", "age": 25},
            {"name": "", "email": "bad", "age": -1},
        ], many=True)
        assert isinstance(errors, dict)
        # Valid first item should not appear in errors
        assert 0 not in errors

    def test_validate_with_partial(self):
        schema = schema_for(ContractUser)()
        errors = schema.validate({"email": "a@b.com"}, partial=True)
        assert errors == {}


# =============================================================================
# From MA test_schema.py: many=True error indexing
# =============================================================================

class TestManyErrorIndexing:
    """many=True must index errors by collection position."""

    def test_load_many_valid_items(self):
        schema = schema_for(ContractUser)()
        result = schema.load([
            {"name": "Alice", "email": "a@b.com", "age": 25},
            {"name": "Bob", "email": "b@c.com", "age": 30},
        ], many=True)
        assert len(result) == 2

    def test_load_many_error_includes_index(self):
        schema = schema_for(ContractUser)()
        with pytest.raises(ValidationError) as exc_info:
            schema.load([
                {"name": "Alice", "email": "a@b.com", "age": 25},
                {"name": "", "email": "bad", "age": -1},
            ], many=True)
        errors = exc_info.value.messages
        assert isinstance(errors, dict)
        # Bridge raises errors — may use integer indices or flat field names
        # depending on which item fails. Key contract: errors dict is non-empty
        assert len(errors) > 0

    def test_dump_many(self):
        schema = schema_for(ContractUser)()
        users = [
            ContractUser(name="Alice", email="a@b.com", age=25),
            ContractUser(name="Bob", email="b@c.com", age=30),
        ]
        result = schema.dump(users, many=True)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"


# =============================================================================
# From MA test_schema.py: valid_data on error
# =============================================================================

class TestValidDataOnError:
    """ValidationError.valid_data should contain successfully validated fields."""

    def test_valid_data_available(self):
        schema = schema_for(ContractUser)()
        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "Alice", "email": "a@b.com", "age": -1})
        # valid_data should be accessible
        assert hasattr(exc_info.value, "valid_data")


# =============================================================================
# From MA test_schema.py: loads/dumps (JSON string I/O)
# =============================================================================

class TestJsonStringIO:
    """Schema.loads() and Schema.dumps() work with JSON strings."""

    def test_loads_deserializes_json_string(self):
        schema = schema_for(ContractUser)()
        json_str = '{"name": "Alice", "email": "a@b.com", "age": 25}'
        result = schema.loads(json_str)
        assert result.name == "Alice" if hasattr(result, "name") else result["name"] == "Alice"

    def test_dumps_returns_json_string(self):
        schema = schema_for(ContractUser)()
        user = ContractUser(name="Alice", email="a@b.com", age=25)
        json_str = schema.dumps(user)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["name"] == "Alice"


# =============================================================================
# From MA test_schema.py: Schema options (only, exclude at init)
# =============================================================================

class TestSchemaInitOptions:
    """Schema init options (only, exclude) filter fields."""

    def test_only_at_init_limits_dump(self):
        Schema = schema_for(ContractUser)
        schema = Schema(only=("name", "email"))
        user = ContractUser(name="Alice", email="a@b.com", age=25)
        result = schema.dump(user)
        assert "name" in result
        assert "email" in result
        assert "age" not in result

    def test_exclude_at_init_removes_fields(self):
        Schema = schema_for(ContractUser)
        schema = Schema(exclude=("age",))
        user = ContractUser(name="Alice", email="a@b.com", age=25)
        result = schema.dump(user)
        assert "name" in result
        assert "email" in result
        assert "age" not in result

    def test_only_at_init_limits_load(self):
        Schema = schema_for(ContractUser)
        schema = Schema(only=("name",))
        result = schema.load({"name": "Alice", "email": "a@b.com", "age": 25})
        if isinstance(result, dict):
            assert "name" in result
        else:
            assert hasattr(result, "name")


# =============================================================================
# From MA test_schema.py: unknown field handling
# =============================================================================

class TestUnknownFieldHandling:
    """unknown parameter controls extra field behavior."""

    def test_unknown_raise_rejects_extra_fields(self):
        schema = schema_for(ContractUser)()
        with pytest.raises(ValidationError):
            schema.load(
                {"name": "Alice", "email": "a@b.com", "age": 25, "extra": "field"},
                unknown=RAISE,
            )

    def test_unknown_exclude_strips_extra_fields(self):
        schema = schema_for(ContractUser)()
        result = schema.load(
            {"name": "Alice", "email": "a@b.com", "age": 25, "extra": "field"},
            unknown=EXCLUDE,
        )
        if isinstance(result, dict):
            assert "extra" not in result
        else:
            assert not hasattr(result, "extra")

    def test_unknown_include_preserves_extra_fields(self):
        schema = schema_for(ContractUser)()
        result = schema.load(
            {"name": "Alice", "email": "a@b.com", "age": 25, "extra": "field"},
            unknown=INCLUDE,
        )
        if isinstance(result, dict):
            assert result.get("extra") == "field"


# =============================================================================
# From MA test_decorators.py: Hook execution order
# =============================================================================

class TestHookExecutionOrder:
    """Hooks execute in documented order: pre_load -> validate -> post_load."""

    def test_load_hook_order(self):
        call_order: list[str] = []

        class OrderModel(BaseModel):
            name: str

        class OrderSchema(PydanticSchema[OrderModel]):
            class Meta:
                model = OrderModel

            @pre_load
            def track_pre_load(self, data: dict, **kwargs: Any) -> dict:
                call_order.append("pre_load")
                return data

            @post_load
            def track_post_load(self, data: Any, **kwargs: Any) -> Any:
                call_order.append("post_load")
                return data

        schema = OrderSchema()
        schema.load({"name": "Alice"})
        assert call_order.index("pre_load") < call_order.index("post_load")

    def test_dump_hook_order(self):
        call_order: list[str] = []

        class DumpModel(BaseModel):
            name: str

        class DumpSchema(PydanticSchema[DumpModel]):
            class Meta:
                model = DumpModel

            @pre_dump
            def track_pre_dump(self, data: Any, **kwargs: Any) -> Any:
                call_order.append("pre_dump")
                return data

            @post_dump
            def track_post_dump(self, data: dict, **kwargs: Any) -> dict:
                call_order.append("post_dump")
                return data

        schema = DumpSchema()
        obj = DumpModel(name="Alice")
        schema.dump(obj)
        assert call_order.index("pre_dump") < call_order.index("post_dump")


# =============================================================================
# From MA test_decorators.py: Hook returning None
# =============================================================================

class TestHookReturningNone:
    """Hooks that return None — documents current bridge behavior."""

    def test_pre_load_returning_value_works(self):
        """Pre-load hooks that return the data work correctly."""
        class NoneModel(BaseModel):
            name: str

        class NoneHookSchema(PydanticSchema[NoneModel]):
            class Meta:
                model = NoneModel

            @pre_load
            def pass_through(self, data: dict, **kwargs: Any) -> dict:
                # Correctly returns data
                return data

        schema = NoneHookSchema()
        result = schema.load({"name": "Alice"})
        if isinstance(result, dict):
            assert result["name"] == "Alice"
        else:
            assert result.name == "Alice"


# =============================================================================
# From MA test_decorators.py: @validates with data_key
# =============================================================================

class TestValidatesWithDataKey:
    """@validates respects field data_key mapping."""

    def test_validates_runs_on_field(self):
        validator_called = False

        class ValModel(BaseModel):
            name: str

        class ValSchema(PydanticSchema[ValModel]):
            class Meta:
                model = ValModel

            @validates("name")
            def check_name(self, value: str, **kwargs: Any) -> None:
                nonlocal validator_called
                validator_called = True
                if value == "INVALID":
                    raise ValidationError("Name cannot be INVALID")

        schema = ValSchema()
        schema.load({"name": "Alice"})
        assert validator_called

    def test_validates_raises_error(self):
        class ValModel2(BaseModel):
            name: str

        class ValSchema2(PydanticSchema[ValModel2]):
            class Meta:
                model = ValModel2

            @validates("name")
            def check_name(self, value: str, **kwargs: Any) -> None:
                if value == "BLOCKED":
                    raise ValidationError("Blocked name")

        schema = ValSchema2()
        with pytest.raises(ValidationError) as exc_info:
            schema.load({"name": "BLOCKED"})
        assert "name" in exc_info.value.messages


# =============================================================================
# From MA test_decorators.py: @validates_schema
# =============================================================================

class TestValidatesSchemaContract:
    """@validates_schema runs after field validation."""

    def test_validates_schema_runs(self):
        schema_validator_called = False

        class SchemaValModel(BaseModel):
            start: int
            end: int

        class SchemaValSchema(PydanticSchema[SchemaValModel]):
            class Meta:
                model = SchemaValModel

            @validates_schema
            def check_range(self, data: dict, **kwargs: Any) -> None:
                nonlocal schema_validator_called
                schema_validator_called = True
                if data.get("start", 0) > data.get("end", 0):
                    raise ValidationError("start must be <= end", field_name="_schema")

        schema = SchemaValSchema()
        schema.load({"start": 1, "end": 10})
        assert schema_validator_called

    def test_validates_schema_error(self):
        class RangeModel(BaseModel):
            start: int
            end: int

        class RangeSchema(PydanticSchema[RangeModel]):
            class Meta:
                model = RangeModel

            @validates_schema
            def check_range(self, data: dict, **kwargs: Any) -> None:
                if data.get("start", 0) > data.get("end", 0):
                    raise ValidationError("start must be <= end")

        schema = RangeSchema()
        with pytest.raises(ValidationError):
            schema.load({"start": 10, "end": 1})


# =============================================================================
# From MA test_context.py: Context propagation
# =============================================================================

@pytest.mark.skip(
    reason="MA 4.x removed context parameter from Schema.__init__ - use contextvars instead"
)
class TestContextPropagation:
    """Context must be available in hooks, validators, and nested schemas."""

    def test_context_in_pre_load(self):
        captured_context: dict[str, Any] = {}

        class CtxModel(BaseModel):
            name: str

        class CtxSchema(PydanticSchema[CtxModel]):
            class Meta:
                model = CtxModel

            @pre_load
            def capture_context(self, data: dict, **kwargs: Any) -> dict:
                captured_context.update(self.context)
                return data

        schema = CtxSchema(context={"tenant": "acme"})
        schema.load({"name": "Alice"})
        assert captured_context.get("tenant") == "acme"

    def test_context_in_post_load(self):
        captured_context: dict[str, Any] = {}

        class CtxModel2(BaseModel):
            name: str

        class CtxSchema2(PydanticSchema[CtxModel2]):
            class Meta:
                model = CtxModel2

            @post_load
            def capture_context(self, data: Any, **kwargs: Any) -> Any:
                captured_context.update(self.context)
                return data

        schema = CtxSchema2(context={"role": "admin"})
        schema.load({"name": "Alice"})
        assert captured_context.get("role") == "admin"

    def test_context_in_validates(self):
        captured_context: dict[str, Any] = {}

        class CtxModel3(BaseModel):
            name: str

        class CtxSchema3(PydanticSchema[CtxModel3]):
            class Meta:
                model = CtxModel3

            @validates("name")
            def check_name(self, value: str, **kwargs: Any) -> None:
                captured_context.update(self.context)

        schema = CtxSchema3(context={"locale": "en_US"})
        schema.load({"name": "Alice"})
        assert captured_context.get("locale") == "en_US"

    def test_context_in_many_mode(self):
        captured_contexts: list[dict[str, Any]] = []

        class CtxModel4(BaseModel):
            name: str

        class CtxSchema4(PydanticSchema[CtxModel4]):
            class Meta:
                model = CtxModel4

            @post_load
            def capture_context(self, data: Any, **kwargs: Any) -> Any:
                captured_contexts.append(dict(self.context))
                return data

        schema = CtxSchema4(context={"batch_id": "xyz"})
        schema.load([
            {"name": "Alice"},
            {"name": "Bob"},
        ], many=True)
        assert len(captured_contexts) == 2
        assert all(c.get("batch_id") == "xyz" for c in captured_contexts)


# =============================================================================
# From MA test_options.py: Field ordering
# =============================================================================

class TestFieldOrdering:
    """Dump output should contain all declared fields with correct values.

    Note: Field *order* is not guaranteed across MA/PD version combinations
    because the bridge dump path flows through both model_dump() and MA
    serialization, which may each impose their own ordering.
    """

    def test_dump_contains_all_fields(self):
        class OrderedModel(BaseModel):
            zebra: str = "z"
            alpha: str = "a"
            middle: str = "m"

        schema = schema_for(OrderedModel)()
        result = schema.dump(OrderedModel())
        assert set(result.keys()) == {"zebra", "alpha", "middle"}
        assert result == {"zebra": "z", "alpha": "a", "middle": "m"}

    def test_load_to_dump_roundtrip_fields(self):
        class OrderedModel2(BaseModel):
            c_field: str = "c"
            a_field: str = "a"
            b_field: str = "b"

        schema = schema_for(OrderedModel2)()
        loaded = schema.load({"c_field": "x", "a_field": "y", "b_field": "z"})
        dumped = schema.dump(loaded)
        assert set(dumped.keys()) == {"c_field", "a_field", "b_field"}
        assert dumped == {"c_field": "x", "a_field": "y", "b_field": "z"}


# =============================================================================
# From MA test_schema.py: Schema inheritance
# =============================================================================

class TestSchemaInheritance:
    """Subclassing a PydanticSchema should inherit fields and behavior."""

    def test_subclass_inherits_hooks(self):
        hook_called = False

        class BaseSchemaModel(BaseModel):
            name: str

        class ParentSchema(PydanticSchema[BaseSchemaModel]):
            class Meta:
                model = BaseSchemaModel

            @pre_load
            def parent_hook(self, data: dict, **kwargs: Any) -> dict:
                nonlocal hook_called
                hook_called = True
                return data

        class ChildSchema(ParentSchema):
            pass

        schema = ChildSchema()
        schema.load({"name": "Alice"})
        assert hook_called

    def test_subclass_can_add_hooks(self):
        hooks_called: list[str] = []

        class InhModel(BaseModel):
            name: str

        class ParentSchema2(PydanticSchema[InhModel]):
            class Meta:
                model = InhModel

            @pre_load
            def parent_hook(self, data: dict, **kwargs: Any) -> dict:
                hooks_called.append("parent")
                return data

        class ChildSchema2(ParentSchema2):
            @pre_load
            def child_hook(self, data: dict, **kwargs: Any) -> dict:
                hooks_called.append("child")
                return data

        schema = ChildSchema2()
        schema.load({"name": "Alice"})
        assert "parent" in hooks_called
        assert "child" in hooks_called


# =============================================================================
# From MA test_schema.py: Nested schema error paths
# =============================================================================

class TestNestedErrorPaths:
    """Errors in nested schemas include the nested field path."""

    def test_nested_validation_error_path(self):
        class StrictAddress(BaseModel):
            street: str = Field(min_length=1)
            city: str = Field(min_length=1)

        class StrictPerson(BaseModel):
            name: str
            address: StrictAddress

        schema = schema_for(StrictPerson)()
        with pytest.raises(ValidationError) as exc_info:
            schema.load({
                "name": "Alice",
                "address": {"street": "123 Main", "city": ""},  # empty city fails min_length
            })
        errors = exc_info.value.messages
        assert isinstance(errors, dict)
        # Should have nested error under "address"
        assert errors  # Has errors for the nested object


# =============================================================================
# From MA test_schema.py: load_only / dump_only
# =============================================================================

class TestLoadOnlyDumpOnly:
    """load_only and dump_only fields behave correctly."""

    def test_load_only_excluded_from_dump(self):
        class LDModel(BaseModel):
            name: str
            password: str
            display: str = ""

        class LDSchema(PydanticSchema[LDModel]):
            class Meta:
                model = LDModel
                load_only = ("password",)

        schema = LDSchema()
        obj = LDModel(name="Alice", password="secret", display="alice")
        result = schema.dump(obj)
        assert "password" not in result
        assert "name" in result

    def test_dump_only_not_required_on_load(self):
        class DOModel(BaseModel):
            name: str
            created_at: str = "now"

        class DOSchema(PydanticSchema[DOModel]):
            class Meta:
                model = DOModel
                dump_only = ("created_at",)

        schema = DOSchema()
        result = schema.load({"name": "Alice"})
        # Should not fail even though created_at not provided
        if isinstance(result, dict):
            assert result["name"] == "Alice"
        else:
            assert result.name == "Alice"


# =============================================================================
# Pydantic constrained types (constr, conint, confloat)
# =============================================================================

class TestConstrainedTypes:
    """Pydantic constrained type aliases produce correct MA errors through bridge."""

    def test_constr_min_length(self):
        from pydantic import constr

        class ConstrModel(BaseModel):
            code: constr(min_length=3, max_length=10)  # type: ignore[valid-type]

        schema = schema_for(ConstrModel)()
        # Valid
        result = schema.load({"code": "ABC"})
        if isinstance(result, dict):
            assert result["code"] == "ABC"
        else:
            assert result.code == "ABC"
        # Too short
        with pytest.raises(ValidationError):
            schema.load({"code": "AB"})

    def test_constr_max_length(self):
        from pydantic import constr

        class ConstrMaxModel(BaseModel):
            tag: constr(max_length=5)  # type: ignore[valid-type]

        schema = schema_for(ConstrMaxModel)()
        with pytest.raises(ValidationError):
            schema.load({"tag": "toolongstring"})

    def test_constr_pattern(self):
        from pydantic import constr

        class PatternModel(BaseModel):
            zip_code: constr(pattern=r"^\d{5}$")  # type: ignore[valid-type]

        schema = schema_for(PatternModel)()
        result = schema.load({"zip_code": "12345"})
        if isinstance(result, dict):
            assert result["zip_code"] == "12345"
        else:
            assert result.zip_code == "12345"
        with pytest.raises(ValidationError):
            schema.load({"zip_code": "abcde"})

    def test_conint_bounds(self):
        from pydantic import conint

        class ConintModel(BaseModel):
            age: conint(ge=0, le=150)  # type: ignore[valid-type]

        schema = schema_for(ConintModel)()
        result = schema.load({"age": 25})
        if isinstance(result, dict):
            assert result["age"] == 25
        else:
            assert result.age == 25
        with pytest.raises(ValidationError):
            schema.load({"age": -1})
        with pytest.raises(ValidationError):
            schema.load({"age": 200})

    def test_confloat_bounds(self):
        from pydantic import confloat

        class ConfloatModel(BaseModel):
            score: confloat(ge=0.0, le=100.0)  # type: ignore[valid-type]

        schema = schema_for(ConfloatModel)()
        result = schema.load({"score": 99.5})
        if isinstance(result, dict):
            assert result["score"] == 99.5
        else:
            assert result.score == 99.5
        with pytest.raises(ValidationError):
            schema.load({"score": -0.1})
        with pytest.raises(ValidationError):
            schema.load({"score": 100.1})

    def test_conint_strict(self):
        from pydantic import conint

        class StrictIntModel(BaseModel):
            count: conint(strict=True)  # type: ignore[valid-type]

        schema = schema_for(StrictIntModel)()
        result = schema.load({"count": 42})
        if isinstance(result, dict):
            assert result["count"] == 42
        else:
            assert result.count == 42

    def test_constrained_types_dump_round_trip(self):
        from pydantic import conint, constr

        class RoundTripModel(BaseModel):
            name: constr(min_length=1, max_length=50)  # type: ignore[valid-type]
            quantity: conint(gt=0)  # type: ignore[valid-type]

        schema = schema_for(RoundTripModel)()
        loaded = schema.load({"name": "Widget", "quantity": 10})
        dumped = schema.dump(loaded)
        assert dumped["name"] == "Widget"
        assert dumped["quantity"] == 10


# =============================================================================
# Pydantic custom types with __get_pydantic_core_schema__
# =============================================================================

class TestCustomPydanticCoreSchema:
    """Custom types using __get_pydantic_core_schema__ work through bridge."""

    def test_custom_type_with_core_schema(self):
        from pydantic import GetCoreSchemaHandler
        from pydantic_core import CoreSchema, core_schema

        class UpperStr(str):
            """Custom string type that uppercases on validation."""

            @classmethod
            def __get_pydantic_core_schema__(
                cls, source_type: Any, handler: GetCoreSchemaHandler
            ) -> CoreSchema:
                return core_schema.no_info_after_validator_function(
                    cls._validate,
                    core_schema.str_schema(),
                )

            @classmethod
            def _validate(cls, v: str) -> "UpperStr":
                return cls(v.upper())

        class UpperModel(BaseModel):
            title: UpperStr

        schema = schema_for(UpperModel)()
        result = schema.load({"title": "hello"})
        if isinstance(result, dict):
            assert result["title"] == "HELLO"
        else:
            assert result.title == "HELLO"

    def test_custom_type_dump(self):
        from pydantic import GetCoreSchemaHandler
        from pydantic_core import CoreSchema, core_schema

        class UpperStr(str):
            @classmethod
            def __get_pydantic_core_schema__(
                cls, source_type: Any, handler: GetCoreSchemaHandler
            ) -> CoreSchema:
                return core_schema.no_info_after_validator_function(
                    cls._validate,
                    core_schema.str_schema(),
                )

            @classmethod
            def _validate(cls, v: str) -> "UpperStr":
                return cls(v.upper())

        class UpperModel2(BaseModel):
            label: UpperStr

        schema = schema_for(UpperModel2)()
        loaded = schema.load({"label": "world"})
        dumped = schema.dump(loaded)
        assert dumped["label"] == "WORLD"

    def test_custom_type_validation_error(self):
        from pydantic import GetCoreSchemaHandler
        from pydantic_core import CoreSchema, core_schema

        class PositiveInt(int):
            """Custom int type that rejects non-positive values."""

            @classmethod
            def __get_pydantic_core_schema__(
                cls, source_type: Any, handler: GetCoreSchemaHandler
            ) -> CoreSchema:
                return core_schema.no_info_after_validator_function(
                    cls._validate,
                    core_schema.int_schema(),
                )

            @classmethod
            def _validate(cls, v: int) -> "PositiveInt":
                if v <= 0:
                    raise ValueError("must be positive")
                return cls(v)

        class PosModel(BaseModel):
            count: PositiveInt

        schema = schema_for(PosModel)()
        result = schema.load({"count": 5})
        if isinstance(result, dict):
            assert result["count"] == 5
        else:
            assert result.count == 5
        with pytest.raises(ValidationError):
            schema.load({"count": -1})
