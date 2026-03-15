"""Tests for Pydantic alias support (validation_alias, serialization_alias).

Covers GitHub issue #16: full alias support beyond the basic `alias` field.
"""

from __future__ import annotations

import pytest
from marshmallow import EXCLUDE, RAISE
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field

from pydantic_marshmallow import schema_for
from pydantic_marshmallow.bridge import PydanticSchema, _get_model_field_names_with_aliases

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------

class BasicAliasModel(BaseModel):
    """Model with standard alias (regression baseline)."""
    model_config = ConfigDict(populate_by_name=True)

    user_name: str = Field(alias="userName")
    age: int


class ValidationAliasModel(BaseModel):
    """Model with validation_alias (load-only alias)."""
    model_config = ConfigDict(populate_by_name=True)

    db_url: str = Field(validation_alias="DATABASE_URL")
    port: int = Field(default=5432)


class SerializationAliasModel(BaseModel):
    """Model with serialization_alias (dump-only alias)."""

    first_name: str = Field(serialization_alias="firstName")
    last_name: str = Field(serialization_alias="lastName")


class MixedAliasModel(BaseModel):
    """Model with all three alias types on different fields."""
    model_config = ConfigDict(populate_by_name=True)

    field_a: str = Field(alias="a")
    field_b: str = Field(validation_alias="b_input")
    field_c: str = Field(serialization_alias="c_output")
    field_d: str  # no alias at all


class AllThreeAliasesModel(BaseModel):
    """Model with alias, validation_alias, and serialization_alias on the SAME field."""
    model_config = ConfigDict(populate_by_name=True)

    value: str = Field(
        alias="val",
        validation_alias="val_in",
        serialization_alias="val_out",
    )


class AliasWithSerAliasModel(BaseModel):
    """Model with both alias and serialization_alias on the same field."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="n", serialization_alias="display_name")


class AliasWithDefaultsModel(BaseModel):
    """Model with serialization_alias and default values."""

    required_field: str = Field(serialization_alias="reqField")
    optional_field: str = Field(default="default_val", serialization_alias="optField")
    nullable_field: str | None = Field(default=None, serialization_alias="nullField")


class NestedInnerModel(BaseModel):
    """Inner model with serialization_alias for nested tests."""

    inner_val: int = Field(serialization_alias="innerValue")


class NestedOuterModel(BaseModel):
    """Outer model containing a nested model with aliases."""

    label: str = Field(serialization_alias="Label")
    nested: NestedInnerModel


# ---------------------------------------------------------------------------
# Tests: Basic alias (regression)
# ---------------------------------------------------------------------------

class TestBasicAliasRegression:
    """Ensure existing alias behavior is preserved."""

    def test_load_with_alias(self):
        schema = schema_for(BasicAliasModel)()
        result = schema.load({"userName": "Alice", "age": 30})
        assert result.user_name == "Alice"
        assert result.age == 30

    def test_load_with_field_name(self):
        schema = schema_for(BasicAliasModel)()
        result = schema.load({"user_name": "Bob", "age": 25})
        assert result.user_name == "Bob"

    def test_dump_uses_alias(self):
        schema = schema_for(BasicAliasModel)()
        model = BasicAliasModel(userName="Alice", age=30)
        dumped = schema.dump(model)
        assert dumped["userName"] == "Alice"
        assert dumped["age"] == 30


# ---------------------------------------------------------------------------
# Tests: validation_alias
# ---------------------------------------------------------------------------

class TestValidationAlias:
    """Test validation_alias (load-only)."""

    def test_load_with_validation_alias(self):
        schema = schema_for(ValidationAliasModel)()
        result = schema.load({"DATABASE_URL": "postgres://localhost/db"})
        assert result.db_url == "postgres://localhost/db"

    def test_load_with_field_name(self):
        schema = schema_for(ValidationAliasModel)()
        result = schema.load({"db_url": "mysql://localhost/db"})
        assert result.db_url == "mysql://localhost/db"

    def test_dump_uses_field_name_not_validation_alias(self):
        """validation_alias should NOT appear in dump output."""
        schema = schema_for(ValidationAliasModel)()
        model = ValidationAliasModel(db_url="postgres://localhost/db")
        dumped = schema.dump(model)
        assert "db_url" in dumped
        assert "DATABASE_URL" not in dumped

    def test_unknown_field_detection_with_validation_alias(self):
        """validation_alias values should be recognized, not rejected as unknown."""
        schema = schema_for(ValidationAliasModel)(unknown=RAISE)
        # Should NOT raise — DATABASE_URL is a known validation_alias
        result = schema.load({"DATABASE_URL": "postgres://localhost/db"})
        assert result.db_url == "postgres://localhost/db"

    def test_unknown_field_exclude_with_validation_alias(self):
        """EXCLUDE mode should keep validation_alias keyed fields."""
        schema = schema_for(ValidationAliasModel)(unknown=EXCLUDE)
        result = schema.load({"DATABASE_URL": "postgres://localhost/db", "unknown_key": "x"})
        assert result.db_url == "postgres://localhost/db"


# ---------------------------------------------------------------------------
# Tests: serialization_alias
# ---------------------------------------------------------------------------

class TestSerializationAlias:
    """Test serialization_alias (dump-only)."""

    def test_dump_uses_serialization_alias(self):
        schema = schema_for(SerializationAliasModel)()
        model = SerializationAliasModel(first_name="Alice", last_name="Smith")
        dumped = schema.dump(model)
        assert dumped["firstName"] == "Alice"
        assert dumped["lastName"] == "Smith"
        assert "first_name" not in dumped
        assert "last_name" not in dumped

    def test_load_uses_field_name(self):
        """Load should use field names, not serialization_alias."""
        schema = schema_for(SerializationAliasModel)()
        result = schema.load({"first_name": "Bob", "last_name": "Jones"})
        assert result.first_name == "Bob"
        assert result.last_name == "Jones"

    def test_round_trip(self):
        """Load by field name, dump with serialization_alias."""
        schema = schema_for(SerializationAliasModel)()
        loaded = schema.load({"first_name": "Eve", "last_name": "Park"})
        dumped = schema.dump(loaded)
        assert dumped == {"firstName": "Eve", "lastName": "Park"}


# ---------------------------------------------------------------------------
# Tests: Mixed aliases on different fields
# ---------------------------------------------------------------------------

class TestMixedAliases:
    """Test model with different alias types on different fields."""

    def test_load_mixed(self):
        schema = schema_for(MixedAliasModel)()
        result = schema.load({
            "a": "val_a",
            "b_input": "val_b",
            "field_c": "val_c",
            "field_d": "val_d",
        })
        assert result.field_a == "val_a"
        assert result.field_b == "val_b"
        assert result.field_c == "val_c"
        assert result.field_d == "val_d"

    def test_dump_mixed(self):
        schema = schema_for(MixedAliasModel)()
        model = MixedAliasModel(
            field_a="val_a",
            field_b="val_b",
            field_c="val_c",
            field_d="val_d",
        )
        dumped = schema.dump(model)
        assert dumped["a"] == "val_a"           # alias → data_key
        assert dumped["field_b"] == "val_b"     # validation_alias → no dump effect
        assert dumped["c_output"] == "val_c"    # serialization_alias → post-processed
        assert dumped["field_d"] == "val_d"     # plain field name


# ---------------------------------------------------------------------------
# Tests: All three aliases on SAME field
# ---------------------------------------------------------------------------

class TestAllThreeAliases:
    """Test field with alias, validation_alias, and serialization_alias."""

    def test_load_with_validation_alias(self):
        """validation_alias should take precedence for load."""
        schema = schema_for(AllThreeAliasesModel)()
        result = schema.load({"val_in": "hello"})
        assert result.value == "hello"

    def test_load_with_field_name(self):
        schema = schema_for(AllThreeAliasesModel)()
        result = schema.load({"value": "hello"})
        assert result.value == "hello"

    def test_dump_uses_serialization_alias(self):
        """serialization_alias should override alias for dump output."""
        schema = schema_for(AllThreeAliasesModel)()
        model = AllThreeAliasesModel(value="hello")
        dumped = schema.dump(model)
        assert dumped["val_out"] == "hello"
        assert "val" not in dumped       # alias should NOT appear
        assert "val_in" not in dumped    # validation_alias should NOT appear
        assert "value" not in dumped     # field name should NOT appear


# ---------------------------------------------------------------------------
# Tests: alias + serialization_alias (the tricky combo)
# ---------------------------------------------------------------------------

class TestAliasWithSerializationAlias:
    """Test field with both alias (→ data_key) AND serialization_alias."""

    def test_dump_uses_serialization_alias_over_alias(self):
        """serialization_alias should win over alias in dump output."""
        schema = schema_for(AliasWithSerAliasModel)()
        model = AliasWithSerAliasModel(name="Alice")
        dumped = schema.dump(model)
        assert dumped["display_name"] == "Alice"
        assert "n" not in dumped       # alias data_key should be replaced
        assert "name" not in dumped    # field name should not appear

    def test_load_with_alias(self):
        schema = schema_for(AliasWithSerAliasModel)()
        result = schema.load({"n": "Bob"})
        assert result.name == "Bob"

    def test_load_with_field_name(self):
        schema = schema_for(AliasWithSerAliasModel)()
        result = schema.load({"name": "Charlie"})
        assert result.name == "Charlie"


# ---------------------------------------------------------------------------
# Tests: Exclusion options with serialization_alias
# ---------------------------------------------------------------------------

class TestAliasWithExclusions:
    """Test alias interactions with exclude_unset, exclude_none, exclude_defaults."""

    def test_exclude_none_with_serialization_alias(self):
        schema = schema_for(AliasWithDefaultsModel)()
        model = AliasWithDefaultsModel(required_field="hello")
        dumped = schema.dump(model, exclude_none=True)
        assert dumped["reqField"] == "hello"
        assert dumped["optField"] == "default_val"
        assert "nullField" not in dumped  # None → excluded

    def test_exclude_defaults_with_serialization_alias(self):
        schema = schema_for(AliasWithDefaultsModel)()
        model = AliasWithDefaultsModel(required_field="hello")
        dumped = schema.dump(model, exclude_defaults=True)
        assert dumped["reqField"] == "hello"
        assert "optField" not in dumped    # default → excluded
        assert "nullField" not in dumped   # default (None) → excluded

    def test_exclude_unset_with_serialization_alias(self):
        schema = schema_for(AliasWithDefaultsModel)()
        model = AliasWithDefaultsModel(required_field="hello")
        dumped = schema.dump(model, exclude_unset=True)
        assert dumped["reqField"] == "hello"
        # optional_field and nullable_field were not explicitly set
        assert "optField" not in dumped
        assert "nullField" not in dumped

    def test_exclude_unset_with_plain_alias(self):
        """Regression: exclude_unset must work when field has alias (data_key)."""

        class Model(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            user_name: str = Field(alias="userName", default="John")
            age: int = Field(default=25)

        schema = schema_for(Model)()
        model = Model(age=30)  # user_name not explicitly set
        dumped = schema.dump(model, exclude_unset=True)
        assert dumped == {"age": 30}
        assert "userName" not in dumped  # aliased field must be excluded

    def test_exclude_defaults_with_plain_alias(self):
        """Regression: exclude_defaults must work when field has alias (data_key)."""

        class Model(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            user_name: str = Field(alias="userName", default="John")
            age: int = Field(default=25)

        schema = schema_for(Model)()
        model = Model(user_name="John", age=25)  # all defaults
        dumped = schema.dump(model, exclude_defaults=True)
        assert "userName" not in dumped
        assert "age" not in dumped

    def test_exclude_none_with_plain_alias(self):
        """Regression: exclude_none must work when field has alias (data_key)."""

        class Model(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            user_name: str | None = Field(alias="userName", default=None)
            age: int = Field(default=25)

        schema = schema_for(Model)()
        model = Model(age=30)
        dumped = schema.dump(model, exclude_none=True)
        assert "userName" not in dumped
        assert dumped["age"] == 30


# ---------------------------------------------------------------------------
# Tests: Nested models with aliases
# ---------------------------------------------------------------------------

class TestNestedAliases:
    """Test aliases in nested model configurations."""

    def test_nested_serialization_alias(self):
        """Both outer and inner serialization_alias should be applied."""
        schema = schema_for(NestedOuterModel)()
        model = NestedOuterModel(
            label="test",
            nested=NestedInnerModel(inner_val=42),
        )
        dumped = schema.dump(model)
        assert dumped["Label"] == "test"
        assert dumped["nested"]["innerValue"] == 42
        assert "inner_val" not in dumped["nested"]

    def test_nested_load(self):
        schema = schema_for(NestedOuterModel)()
        result = schema.load({
            "label": "test",
            "nested": {"inner_val": 42},
        })
        assert result.label == "test"
        assert result.nested.inner_val == 42


# ---------------------------------------------------------------------------
# Tests: AliasPath and AliasChoices (graceful handling)
# ---------------------------------------------------------------------------

class TestNonStringAliases:
    """Test that AliasPath and AliasChoices are handled gracefully."""

    def test_alias_path_ignored_in_cache(self):
        """AliasPath is not a string — should not crash the cache."""
        class Model(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            value: str = Field(validation_alias=AliasPath("data", "value"))

        schema = schema_for(Model)()
        # Load with field name should work
        result = schema.load({"value": "hello"})
        assert result.value == "hello"

    def test_alias_choices_ignored_in_cache(self):
        """AliasChoices is not a string — should not crash the cache."""
        class Model(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            value: str = Field(validation_alias=AliasChoices("val", "v"))

        schema = schema_for(Model)()
        result = schema.load({"value": "hello"})
        assert result.value == "hello"

    def test_serialization_alias_string_only(self):
        """Pydantic only accepts str for serialization_alias, AliasPath raises at model definition."""
        # Pydantic rejects non-string serialization_alias at model definition time.
        # This test verifies that our code only processes string serialization_alias
        # values, which is the only valid type Pydantic accepts.
        class Model(BaseModel):
            value: str = Field(serialization_alias="out_value")

        schema = schema_for(Model)()
        model = Model(value="hello")
        dumped = schema.dump(model)
        assert dumped["out_value"] == "hello"
        assert "value" not in dumped


# ---------------------------------------------------------------------------
# Tests: dump(many=True) with aliases
# ---------------------------------------------------------------------------

class TestDumpManyWithAliases:
    """Test dump with many=True and serialization aliases."""

    def test_dump_many_applies_serialization_alias(self):
        schema = schema_for(SerializationAliasModel)()
        models = [
            SerializationAliasModel(first_name="Alice", last_name="Smith"),
            SerializationAliasModel(first_name="Bob", last_name="Jones"),
        ]
        dumped = schema.dump(models, many=True)
        assert len(dumped) == 2
        assert dumped[0]["firstName"] == "Alice"
        assert dumped[1]["firstName"] == "Bob"
        assert "first_name" not in dumped[0]
        assert "first_name" not in dumped[1]


# ---------------------------------------------------------------------------
# Tests: exclude_none=True for dict inputs (moved from code review fixes)
# ---------------------------------------------------------------------------


class NoneModel(BaseModel):
    name: str
    age: int | None = None
    bio: str | None = None


class NoneSchema(PydanticSchema[NoneModel]):
    class Meta:
        model = NoneModel


class TestExcludeNoneDictInputs:
    """exclude_none must work for dict inputs, not just BaseModel."""

    def test_exclude_none_with_model_instance(self) -> None:
        """Baseline: exclude_none works with BaseModel instances."""
        schema = NoneSchema()
        obj = NoneModel(name="Alice", age=None, bio=None)
        result = schema.dump(obj, exclude_none=True)
        assert "name" in result
        assert "age" not in result
        assert "bio" not in result

    def test_exclude_none_with_dict_input(self) -> None:
        """Fix: exclude_none should also filter None from dict inputs."""
        schema = NoneSchema()
        data = {"name": "Bob", "age": None, "bio": None}
        result = schema.dump(data, exclude_none=True)
        assert result["name"] == "Bob"
        assert "age" not in result
        assert "bio" not in result

    def test_exclude_none_false_with_dict_preserves_nones(self) -> None:
        """When exclude_none=False, None values are preserved in dict dump."""
        schema = NoneSchema()
        data = {"name": "Carol", "age": None}
        result = schema.dump(data, exclude_none=False)
        assert result["name"] == "Carol"
        assert "age" in result
        assert result["age"] is None

    def test_exclude_none_dict_no_nones_unchanged(self) -> None:
        """Dict with no None values is unaffected by exclude_none=True."""
        schema = NoneSchema()
        data = {"name": "Dave", "age": 30, "bio": "hi"}
        result = schema.dump(data, exclude_none=True)
        assert result == {"name": "Dave", "age": 30, "bio": "hi"}


# ---------------------------------------------------------------------------
# Tests: AliasChoices / AliasPath in _get_model_field_names_with_aliases
# ---------------------------------------------------------------------------


class TestAliasChoicesAndPath:
    """AliasChoices and AliasPath should be recognised as valid field names."""

    def test_alias_path_recognized(self) -> None:
        """AliasPath validation_alias adds top-level key to known names."""
        class PathModel(BaseModel):
            name: str = Field(validation_alias=AliasPath("data", "name"))

        PydanticSchema.from_model(PathModel)
        names = _get_model_field_names_with_aliases(PathModel)
        assert "data" in names
        assert "name" in names

    def test_alias_choices_recognized(self) -> None:
        """AliasChoices validation_alias adds all string choices to known names."""
        class ChoicesModel(BaseModel):
            name: str = Field(validation_alias=AliasChoices("Name", "NAME"))

        names = _get_model_field_names_with_aliases(ChoicesModel)
        assert "name" in names
        assert "Name" in names
        assert "NAME" in names

    def test_alias_choices_with_alias_path(self) -> None:
        """AliasChoices containing AliasPath entries extracts top-level keys."""
        class MixedModel(BaseModel):
            value: int = Field(
                validation_alias=AliasChoices("val", AliasPath("data", "value"))
            )

        names = _get_model_field_names_with_aliases(MixedModel)
        assert "val" in names
        assert "data" in names
        assert "value" in names

    def test_load_with_alias_choices_raise_mode(self) -> None:
        """Loading via AliasChoices key in RAISE mode should not error."""
        class AcModel(BaseModel):
            name: str = Field(validation_alias=AliasChoices("Name", "NAME"))

        schema_cls = PydanticSchema.from_model(AcModel)
        result = schema_cls(unknown=RAISE).load({"Name": "Alice"})
        name = result["name"] if isinstance(result, dict) else result.name
        assert name == "Alice"
