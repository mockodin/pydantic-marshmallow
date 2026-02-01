"""Test Marshmallow hooks compatibility with PydanticSchema.

These tests verify that all Marshmallow hooks (pre_load, post_load,
pre_dump, post_dump) work correctly with the Pydantic bridge.
"""

from typing import Any, Dict

import pytest
from marshmallow import ValidationError, post_dump, post_load, pre_dump, pre_load
from pydantic import BaseModel

from pydantic_marshmallow import PydanticSchema


class TestPreLoadHooks:
    """Test @pre_load hooks run before Pydantic validation."""

    def test_pre_load_transforms_data(self):
        """Test that pre_load can transform data before Pydantic validates."""
        class User(BaseModel):
            email: str
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def normalize_email(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Normalize email to lowercase before validation."""
                if "email" in data:
                    data["email"] = data["email"].lower().strip()
                return data

            @pre_load
            def normalize_name(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Trim whitespace from name."""
                if "name" in data:
                    data["name"] = data["name"].strip()
                return data

        schema = UserSchema()
        result = schema.load({
            "email": "  ALICE@EXAMPLE.COM  ",
            "name": "  Alice Smith  "
        })

        assert result.email == "alice@example.com"
        assert result.name == "Alice Smith"

    def test_pre_load_can_add_fields(self):
        """Test that pre_load can add default values."""
        class Config(BaseModel):
            version: str
            debug: bool

        class ConfigSchema(PydanticSchema[Config]):
            class Meta:
                model = Config

            @pre_load
            def add_defaults(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Add default version if not provided."""
                if "version" not in data:
                    data["version"] = "1.0.0"
                return data

        schema = ConfigSchema()
        result = schema.load({"debug": True})

        assert result.version == "1.0.0"
        assert result.debug is True

    def test_pre_load_can_rename_fields(self):
        """Test that pre_load can rename fields for API compatibility."""
        class User(BaseModel):
            user_id: int
            display_name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def rename_legacy_fields(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Support legacy API field names."""
                if "id" in data and "user_id" not in data:
                    data["user_id"] = data.pop("id")
                if "name" in data and "display_name" not in data:
                    data["display_name"] = data.pop("name")
                return data

        schema = UserSchema()

        # Modern field names
        result = schema.load({"user_id": 1, "display_name": "Alice"})
        assert result.user_id == 1

        # Legacy field names
        result = schema.load({"id": 2, "name": "Bob"})
        assert result.user_id == 2
        assert result.display_name == "Bob"

    def test_pre_load_can_reject_data(self):
        """Test that pre_load can raise ValidationError."""
        class Submission(BaseModel):
            data: str

        class SubmissionSchema(PydanticSchema[Submission]):
            class Meta:
                model = Submission

            @pre_load
            def check_not_empty(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Reject if all values are empty."""
                if all(not v for v in data.values()):
                    raise ValidationError("Submission cannot be empty")
                return data

        schema = SubmissionSchema()

        with pytest.raises(ValidationError) as exc:
            schema.load({"data": ""})

        assert "empty" in str(exc.value).lower()


class TestPostLoadHooks:
    """Test @post_load hooks run after Pydantic creates the model."""

    def test_post_load_can_modify_instance(self):
        """Test that post_load can modify the Pydantic model instance."""
        class User(BaseModel):
            model_config = {"extra": "allow"}
            name: str
            computed_greeting: str = ""

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @post_load
            def compute_greeting(self, data: User, **kwargs: Any) -> User:
                """Add a computed greeting field."""
                # Note: data is the Pydantic model instance from _make_model
                data.computed_greeting = f"Hello, {data.name}!"
                return data

        schema = UserSchema()
        result = schema.load({"name": "Alice"})

        assert result.name == "Alice"
        assert result.computed_greeting == "Hello, Alice!"

    def test_post_load_receives_pydantic_model(self):
        """Test that post_load receives a Pydantic model instance."""
        class Product(BaseModel):
            name: str
            price: float

        received_type = None

        class ProductSchema(PydanticSchema[Product]):
            class Meta:
                model = Product

            @post_load
            def check_type(self, data: Any, **kwargs: Any) -> Any:
                nonlocal received_type
                received_type = type(data)
                return data

        schema = ProductSchema()
        result = schema.load({"name": "Widget", "price": 9.99})

        assert received_type is Product
        assert isinstance(result, Product)


class TestPreDumpHooks:
    """Test @pre_dump hooks run before serialization."""

    def test_pre_dump_transforms_model(self):
        """Test that pre_dump can transform before serialization."""
        class User(BaseModel):
            name: str
            password: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_dump
            def hide_password(self, data: Any, **kwargs: Any) -> Any:
                """Convert model to dict and hide password."""
                if isinstance(data, BaseModel):
                    d = data.model_dump()
                else:
                    d = dict(data)
                d["password"] = "***"
                return d

        schema = UserSchema()
        user = User(name="Alice", password="secret123")
        result = schema.dump(user)

        assert result["name"] == "Alice"
        assert result["password"] == "***"


class TestPostDumpHooks:
    """Test @post_dump hooks run after serialization."""

    def test_post_dump_transforms_output(self):
        """Test that post_dump can transform the output dict."""
        class User(BaseModel):
            id: int
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @post_dump
            def add_links(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Add HATEOAS-style links to output."""
                data["_links"] = {
                    "self": f"/api/users/{data['id']}",
                    "collection": "/api/users"
                }
                return data

        schema = UserSchema()
        user = User(id=42, name="Alice")
        result = schema.dump(user)

        assert result["id"] == 42
        assert result["name"] == "Alice"
        assert result["_links"]["self"] == "/api/users/42"

    def test_post_dump_can_remove_fields(self):
        """Test that post_dump can remove internal fields."""
        class InternalUser(BaseModel):
            id: int
            name: str
            internal_flag: bool = False

        class PublicUserSchema(PydanticSchema[InternalUser]):
            class Meta:
                model = InternalUser

            @post_dump
            def remove_internal(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Remove internal fields from public API."""
                data.pop("internal_flag", None)
                return data

        schema = PublicUserSchema()
        user = InternalUser(id=1, name="Alice", internal_flag=True)
        result = schema.dump(user)

        assert "internal_flag" not in result
        assert result["id"] == 1

    def test_post_dump_can_transform_keys(self):
        """Test that post_dump can transform dict keys (e.g., camelCase)."""
        class User(BaseModel):
            user_id: int
            first_name: str
            last_name: str

        def to_camel_case(snake_str: str) -> str:
            """Convert snake_case to camelCase."""
            components = snake_str.split("_")
            return components[0] + "".join(x.title() for x in components[1:])

        class CamelCaseUserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @post_dump
            def camelize_keys(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                """Convert all keys to camelCase."""
                return {to_camel_case(k): v for k, v in data.items()}

        schema = CamelCaseUserSchema()
        user = User(user_id=1, first_name="Alice", last_name="Smith")
        result = schema.dump(user)

        assert result == {
            "userId": 1,
            "firstName": "Alice",
            "lastName": "Smith"
        }


class TestMultipleHooks:
    """Test multiple hooks working together."""

    def test_full_lifecycle_hooks(self):
        """Test all hooks in a complete request/response cycle."""
        hook_calls = []

        class User(BaseModel):
            model_config = {"extra": "allow"}
            username: str
            email: str
            processed: bool = False

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @pre_load
            def log_pre_load(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                hook_calls.append("pre_load")
                # Normalize input
                data["email"] = data.get("email", "").lower()
                return data

            @post_load
            def log_post_load(self, data: User, **kwargs: Any) -> User:
                hook_calls.append("post_load")
                data.processed = True
                return data

            @pre_dump
            def log_pre_dump(self, data: Any, **kwargs: Any) -> Any:
                hook_calls.append("pre_dump")
                return data

            @post_dump
            def log_post_dump(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                hook_calls.append("post_dump")
                data["_serialized"] = True
                return data

        schema = UserSchema()

        # Load
        hook_calls.clear()
        user = schema.load({
            "username": "alice",
            "email": "ALICE@EXAMPLE.COM"
        })

        assert hook_calls == ["pre_load", "post_load"]
        assert user.email == "alice@example.com"  # Normalized by pre_load
        assert user.processed is True  # Set by post_load

        # Dump
        hook_calls.clear()
        result = schema.dump(user)

        assert hook_calls == ["pre_dump", "post_dump"]
        assert result["_serialized"] is True


class TestHooksWithMany:
    """Test hooks work correctly with many=True."""

    def test_pre_load_with_many(self):
        """Test pre_load is called for each item when many=True."""
        class Item(BaseModel):
            name: str

        class ItemSchema(PydanticSchema[Item]):
            class Meta:
                model = Item

            @pre_load
            def uppercase_name(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                data["name"] = data["name"].upper()
                return data

        schema = ItemSchema(many=True)
        results = schema.load([
            {"name": "apple"},
            {"name": "banana"},
            {"name": "cherry"}
        ])

        assert [r.name for r in results] == ["APPLE", "BANANA", "CHERRY"]

    def test_post_dump_with_many(self):
        """Test post_dump is called for each item when many=True."""
        class User(BaseModel):
            id: int
            name: str

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @post_dump
            def add_self_link(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
                data["_self"] = f"/users/{data['id']}"
                return data

        schema = UserSchema(many=True)
        users = [
            User(id=1, name="Alice"),
            User(id=2, name="Bob")
        ]
        results = schema.dump(users)

        assert results[0]["_self"] == "/users/1"
        assert results[1]["_self"] == "/users/2"
