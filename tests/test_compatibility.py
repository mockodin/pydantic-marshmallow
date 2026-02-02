"""
Compatibility tests for tracking Marshmallow and Pydantic version features.

This file tests features from specific versions to ensure the bridge
maintains compatibility as both libraries evolve.

Run with: pytest tests/test_compatibility.py -v
"""

from typing import Any

import pytest
from marshmallow import ValidationError, post_load, pre_load
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pydantic_marshmallow import PydanticSchema, schema_for

# =============================================================================
# MARSHMALLOW 3.18+ FEATURES (Baseline)
# =============================================================================

class TestMarshmallow318Baseline:
    """Baseline Marshmallow 3.18 features that must always work."""

    def test_schema_load(self):
        """Test basic schema.load()."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        result = schema.load({"name": "Alice"})
        assert result.name == "Alice"

    def test_schema_dump(self):
        """Test basic schema.dump()."""
        class User(BaseModel):
            name: str

        user = User(name="Alice")
        schema = schema_for(User)()
        result = schema.dump(user)
        assert result["name"] == "Alice"

    def test_unknown_raise(self):
        """Test unknown=RAISE (default)."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        with pytest.raises(ValidationError):
            schema.load({"name": "Alice", "extra": "field"})

    def test_many_true(self):
        """Test many=True for collections."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        result = schema.load([{"name": "Alice"}, {"name": "Bob"}], many=True)
        assert len(result) == 2
        assert result[0].name == "Alice"
        assert result[1].name == "Bob"

    def test_pre_load_hook(self):
        """Test @pre_load hook."""
        class User(BaseModel):
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def uppercase_name(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
                data["name"] = data["name"].upper()
                return data

        schema = UserSchema()
        result = schema.load({"name": "alice"})
        assert result.name == "ALICE"

    def test_post_load_hook(self):
        """Test @post_load hook."""
        class User(BaseModel):
            model_config = ConfigDict(extra="allow")
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @post_load
            def add_processed_flag(self, data: User, **kwargs) -> User:
                data.processed = True
                return data

        schema = UserSchema()
        result = schema.load({"name": "Alice"})
        assert result.processed is True


# =============================================================================
# PYDANTIC 2.0+ FEATURES (Baseline)
# =============================================================================

class TestPydantic20Baseline:
    """Baseline Pydantic 2.0 features that must always work."""

    def test_model_validate(self):
        """Test that Pydantic model_validate is used internally."""
        class User(BaseModel):
            name: str
            age: int = Field(ge=0)

        schema = schema_for(User)()
        result = schema.load({"name": "Alice", "age": 30})
        assert isinstance(result, User)
        assert result.name == "Alice"
        assert result.age == 30

    def test_field_constraints(self):
        """Test Field() constraints (ge, le, min_length, etc.)."""
        class User(BaseModel):
            name: str = Field(min_length=1, max_length=50)
            age: int = Field(ge=0, le=150)

        schema = schema_for(User)()

        # Valid
        result = schema.load({"name": "Alice", "age": 30})
        assert result.name == "Alice"

        # Invalid - name too short
        with pytest.raises(ValidationError):
            schema.load({"name": "", "age": 30})

        # Invalid - age negative
        with pytest.raises(ValidationError):
            schema.load({"name": "Alice", "age": -1})

    def test_field_validator(self):
        """Test @field_validator decorator."""
        class User(BaseModel):
            email: str

            @field_validator("email")
            @classmethod
            def normalize_email(cls, v: str) -> str:
                return v.lower().strip()

        schema = schema_for(User)()
        result = schema.load({"email": "  ALICE@EXAMPLE.COM  "})
        assert result.email == "alice@example.com"

    def test_config_dict(self):
        """Test ConfigDict options."""
        class User(BaseModel):
            model_config = ConfigDict(str_strip_whitespace=True)
            name: str

        schema = schema_for(User)()
        result = schema.load({"name": "  Alice  "})
        assert result.name == "Alice"

    def test_optional_fields(self):
        """Test Optional[T] fields."""
        class User(BaseModel):
            name: str
            nickname: str | None = None

        schema = schema_for(User)()

        # Without optional field
        result = schema.load({"name": "Alice"})
        assert result.nickname is None

        # With optional field
        result = schema.load({"name": "Alice", "nickname": "Ali"})
        assert result.nickname == "Ali"

    def test_type_coercion(self):
        """Test Pydantic's type coercion."""
        class Config(BaseModel):
            count: int
            ratio: float
            enabled: bool

        schema = schema_for(Config)()
        result = schema.load({
            "count": "123",
            "ratio": 42,
            "enabled": "true"
        })

        assert result.count == 123
        assert result.ratio == 42.0
        assert result.enabled is True

    def test_nested_models(self):
        """Test nested Pydantic models."""
        class Address(BaseModel):
            city: str

        class User(BaseModel):
            name: str
            address: Address

        schema = schema_for(User)()
        result = schema.load({
            "name": "Alice",
            "address": {"city": "NYC"}
        })

        assert result.name == "Alice"
        assert result.address.city == "NYC"


# =============================================================================
# PYDANTIC 2.5+ FEATURES
# =============================================================================

class TestPydantic25Features:
    """Features added in Pydantic 2.5."""

    def test_alias_with_populate_by_name(self):
        """Test Field(alias=...) with populate_by_name=True."""
        class User(BaseModel):
            model_config = ConfigDict(populate_by_name=True)
            user_name: str = Field(alias="userName")

        schema = schema_for(User)()

        # Load with alias
        result = schema.load({"userName": "Alice"})
        assert result.user_name == "Alice"

        # Load with field name
        result = schema.load({"user_name": "Bob"})
        assert result.user_name == "Bob"


# =============================================================================
# FUTURE VERSION PLACEHOLDERS
# =============================================================================

class TestMarshmallowFutureFeatures:
    """
    Placeholder for testing new Marshmallow features.

    When Marshmallow releases a new version:
    1. Add tests here for new features
    2. Mark with @pytest.mark.skip if not yet implemented
    3. Remove skip mark once implemented
    """

    @pytest.mark.skip(reason="Template for future feature")
    def test_future_marshmallow_feature(self):
        """
        Test [feature name] from Marshmallow X.Y.

        Added in: Marshmallow X.Y
        Docs: https://marshmallow.readthedocs.io/...
        """


class TestPydanticFutureFeatures:
    """
    Placeholder for testing new Pydantic features.

    When Pydantic releases a new version:
    1. Add tests here for new features
    2. Mark with @pytest.mark.skip if not yet implemented
    3. Remove skip mark once implemented
    """

    @pytest.mark.skip(reason="Template for future feature")
    def test_future_pydantic_feature(self):
        """
        Test [feature name] from Pydantic X.Y.

        Added in: Pydantic X.Y
        Docs: https://docs.pydantic.dev/...
        """


# =============================================================================
# ECOSYSTEM COMPATIBILITY
# =============================================================================

class TestEcosystemCompatibility:
    """Tests to verify ecosystem tool compatibility."""

    def test_schema_is_marshmallow_subclass(self):
        """Verify schema is a proper Marshmallow Schema subclass."""
        from marshmallow import Schema

        class User(BaseModel):
            name: str

        UserSchema = schema_for(User)

        assert issubclass(UserSchema, Schema)
        assert isinstance(UserSchema(), Schema)

    def test_schema_has_fields_attribute(self):
        """Verify schema has fields attribute (used by apispec)."""
        class User(BaseModel):
            name: str
            age: int

        schema = schema_for(User)()

        assert hasattr(schema, "fields")
        assert "name" in schema.fields
        assert "age" in schema.fields

    def test_schema_has_meta_attribute(self):
        """Verify schema has Meta class (used by various tools)."""
        class User(BaseModel):
            name: str

        UserSchema = schema_for(User)

        assert hasattr(UserSchema, "Meta")
        assert hasattr(UserSchema.Meta, "model")

    def test_loads_and_dumps(self):
        """Verify JSON string methods work (used by many tools)."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()

        # loads() - from JSON string
        result = schema.loads('{"name": "Alice"}')
        assert result.name == "Alice"

        # dumps() - to JSON string
        user = User(name="Bob")
        json_str = schema.dumps(user)
        assert '"name"' in json_str
        assert '"Bob"' in json_str


# =============================================================================
# VERSION DETECTION HELPERS
# =============================================================================

def get_marshmallow_version() -> tuple:
    """Get installed Marshmallow version as tuple."""
    from importlib.metadata import version
    ver = version("marshmallow")
    return tuple(int(x) for x in ver.split(".")[:2])


def get_pydantic_version() -> tuple:
    """Get installed Pydantic version as tuple."""
    from importlib.metadata import version
    ver = version("pydantic")
    return tuple(int(x) for x in ver.split(".")[:2])


@pytest.fixture(scope="module", autouse=True)
def show_version_info():
    """Display version info for debugging (runs once per module)."""
    from importlib.metadata import version

    ma_version = version("marshmallow")
    pd_version = version("pydantic")

    print(f"\n{'='*60}")
    print(f"Marshmallow version: {ma_version}")
    print(f"Pydantic version: {pd_version}")
    print(f"{'='*60}\n")
