"""Tests for return_instance parameter.

Tests the return_instance parameter that controls whether load() returns
a Pydantic model instance (default) or a plain dict.
"""

import pytest
from marshmallow import pre_load
from pydantic import BaseModel, computed_field

from pydantic_marshmallow import PydanticSchema, schema_for


class TestReturnInstanceBasic:
    """Basic return_instance parameter tests."""

    def test_return_instance_true_is_default(self):
        """return_instance=True is the default behavior."""
        class User(BaseModel):
            name: str
            age: int

        schema = schema_for(User)()
        result = schema.load({"name": "Alice", "age": 30})

        assert isinstance(result, User)
        assert result.name == "Alice"
        assert result.age == 30

    def test_return_instance_false_returns_dict(self):
        """return_instance=False returns a plain dict."""
        class User(BaseModel):
            name: str
            age: int

        schema = schema_for(User)()
        result = schema.load({"name": "Alice", "age": 30}, return_instance=False)

        assert isinstance(result, dict)
        assert not isinstance(result, User)
        assert result == {"name": "Alice", "age": 30}

    def test_return_instance_true_explicit(self):
        """return_instance=True explicitly returns model instance."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        result = schema.load({"name": "Alice"}, return_instance=True)

        assert isinstance(result, User)


class TestReturnInstanceWithMany:
    """return_instance with many=True."""

    def test_many_with_instance_mode(self):
        """many=True returns list of model instances by default."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        results = schema.load([{"name": "Alice"}, {"name": "Bob"}], many=True)

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, User) for r in results)
        assert results[0].name == "Alice"
        assert results[1].name == "Bob"

    def test_many_with_dict_mode(self):
        """many=True with return_instance=False returns list of dicts."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()
        results = schema.load(
            [{"name": "Alice"}, {"name": "Bob"}],
            many=True,
            return_instance=False
        )

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)
        assert results[0] == {"name": "Alice"}
        assert results[1] == {"name": "Bob"}

    def test_many_empty_list(self):
        """many=True with empty list works in both modes."""
        class User(BaseModel):
            name: str

        schema = schema_for(User)()

        results_instance = schema.load([], many=True)
        assert results_instance == []

        results_dict = schema.load([], many=True, return_instance=False)
        assert results_dict == []


class TestReturnInstanceWithComputedFields:
    """return_instance with computed fields."""

    def test_dict_mode_includes_computed_fields(self):
        """return_instance=False includes computed fields in dict."""
        class User(BaseModel):
            first: str
            last: str

            @computed_field
            @property
            def full_name(self) -> str:
                return f"{self.first} {self.last}"

        schema = schema_for(User)()
        result = schema.load({"first": "Alice", "last": "Smith"}, return_instance=False)

        assert isinstance(result, dict)
        assert result["first"] == "Alice"
        assert result["last"] == "Smith"
        assert result["full_name"] == "Alice Smith"

    def test_instance_mode_has_computed_fields(self):
        """return_instance=True gives model with accessible computed fields."""
        class Rectangle(BaseModel):
            width: float
            height: float

            @computed_field
            @property
            def area(self) -> float:
                return self.width * self.height

        schema = schema_for(Rectangle)()
        result = schema.load({"width": 10, "height": 5})

        assert isinstance(result, Rectangle)
        assert result.area == 50.0


class TestReturnInstanceWithHooks:
    """return_instance with pre_load/post_load hooks."""

    def test_pre_load_transformations_preserved_in_instance(self):
        """pre_load transformations are preserved in instance mode."""
        class User(BaseModel):
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def uppercase_name(self, data, **kwargs):
                data["name"] = data["name"].upper()
                return data

        schema = UserSchema()
        result = schema.load({"name": "alice"})

        assert isinstance(result, User)
        assert result.name == "ALICE"

    def test_pre_load_transformations_preserved_in_dict(self):
        """pre_load transformations are preserved in dict mode."""
        class User(BaseModel):
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def uppercase_name(self, data, **kwargs):
                data["name"] = data["name"].upper()
                return data

        schema = UserSchema()
        result = schema.load({"name": "alice"}, return_instance=False)

        assert isinstance(result, dict)
        assert result["name"] == "ALICE"


class TestReturnInstanceWithValidation:
    """return_instance doesn't affect validation behavior."""

    def test_validation_runs_in_dict_mode(self):
        """Pydantic validation runs even with return_instance=False."""
        from marshmallow import ValidationError
        from pydantic import Field

        class User(BaseModel):
            name: str = Field(min_length=1)
            age: int = Field(ge=0)

        schema = schema_for(User)()

        # Valid data works
        result = schema.load({"name": "Alice", "age": 30}, return_instance=False)
        assert result == {"name": "Alice", "age": 30}

        # Invalid data still raises
        with pytest.raises(ValidationError):
            schema.load({"name": "", "age": -5}, return_instance=False)

    def test_type_coercion_in_dict_mode(self):
        """Pydantic type coercion works in dict mode."""
        class Config(BaseModel):
            count: int
            enabled: bool

        schema = schema_for(Config)()
        result = schema.load({"count": "42", "enabled": "true"}, return_instance=False)

        # Types are coerced
        assert result["count"] == 42
        assert result["enabled"] is True


class TestReturnInstanceUseCases:
    """Common use cases for return_instance parameter."""

    def test_api_response_serialization(self):
        """Use dict mode for direct JSON serialization."""
        class ApiResponse(BaseModel):
            status: str
            data: dict

            @computed_field
            @property
            def success(self) -> bool:
                return self.status == "ok"

        schema = schema_for(ApiResponse)()
        result = schema.load(
            {"status": "ok", "data": {"user_id": 123}},
            return_instance=False
        )

        # Ready for json.dumps()
        import json
        json_str = json.dumps(result)
        assert '"success": true' in json_str or '"success":true' in json_str

    def test_orm_integration(self):
        """Use instance mode for ORM integration."""
        class UserData(BaseModel):
            name: str
            email: str

        schema = schema_for(UserData)()
        user_data = schema.load({"name": "Alice", "email": "alice@example.com"})

        # Can access as object attributes for ORM
        assert user_data.name == "Alice"
        assert user_data.email == "alice@example.com"
