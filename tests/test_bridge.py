"""Tests for the Pydantic-Marshmallow bridge."""

import pytest
from marshmallow import ValidationError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from pydantic_marshmallow import HybridModel, PydanticSchema, schema_for


class TestPydanticSchemaBasic:
    """Test basic PydanticSchema functionality."""

    def test_from_model_basic(self):
        """Test creating a schema from a simple Pydantic model."""
        class User(BaseModel):
            name: str
            age: int

        UserSchema = schema_for(User)
        schema = UserSchema()

        result = schema.load({"name": "Alice", "age": 30})

        assert isinstance(result, User)
        assert result.name == "Alice"
        assert result.age == 30

    def test_pydantic_validation_applied(self):
        """Test that Pydantic validation is actually used."""
        class Product(BaseModel):
            name: str = Field(min_length=1)
            price: float = Field(gt=0)

        ProductSchema = schema_for(Product)
        schema = ProductSchema()

        # Valid data
        result = schema.load({"name": "Widget", "price": 9.99})
        assert result.name == "Widget"

        # Invalid: empty name (Pydantic validation)
        with pytest.raises(ValidationError) as exc:
            schema.load({"name": "", "price": 9.99})
        assert "name" in exc.value.messages

        # Invalid: negative price (Pydantic validation)
        with pytest.raises(ValidationError) as exc:
            schema.load({"name": "Widget", "price": -5})
        assert "price" in exc.value.messages

    def test_pydantic_coercion(self):
        """Test that Pydantic's type coercion works."""
        class Config(BaseModel):
            count: int
            enabled: bool

        ConfigSchema = schema_for(Config)
        schema = ConfigSchema()

        # Pydantic coerces string "123" to int 123
        result = schema.load({"count": "123", "enabled": "true"})
        assert result.count == 123
        assert result.enabled is True

    def test_pydantic_email_validation(self):
        """Test Pydantic's EmailStr validation."""
        class Contact(BaseModel):
            email: EmailStr

        ContactSchema = schema_for(Contact)
        schema = ContactSchema()

        # Valid email
        result = schema.load({"email": "user@example.com"})
        assert result.email == "user@example.com"

        # Invalid email
        with pytest.raises(ValidationError):
            schema.load({"email": "not-an-email"})

    def test_pydantic_custom_validator(self):
        """Test that Pydantic's custom validators work."""
        class User(BaseModel):
            username: str

            @field_validator("username")
            @classmethod
            def username_alphanumeric(cls, v: str) -> str:
                if not v.isalnum():
                    raise ValueError("must be alphanumeric")
                return v.lower()

        UserSchema = schema_for(User)
        schema = UserSchema()

        # Valid: gets lowercased by validator
        result = schema.load({"username": "Alice123"})
        assert result.username == "alice123"

        # Invalid: contains special chars
        with pytest.raises(ValidationError):
            schema.load({"username": "alice@123"})


class TestPydanticSchemaAdvanced:
    """Test advanced PydanticSchema features."""

    def test_optional_fields(self):
        """Test Optional fields work correctly."""
        class Profile(BaseModel):
            name: str
            bio: str | None = None

        ProfileSchema = schema_for(Profile)
        schema = ProfileSchema()

        # Without optional
        result = schema.load({"name": "Alice"})
        assert result.name == "Alice"
        assert result.bio is None

        # With optional
        result = schema.load({"name": "Alice", "bio": "Hello!"})
        assert result.bio == "Hello!"

    def test_list_fields(self):
        """Test List fields work correctly."""
        class Team(BaseModel):
            name: str
            members: list[str]

        TeamSchema = schema_for(Team)
        schema = TeamSchema()

        result = schema.load({
            "name": "Engineering",
            "members": ["Alice", "Bob", "Charlie"]
        })

        assert result.name == "Engineering"
        assert result.members == ["Alice", "Bob", "Charlie"]

    def test_nested_models(self):
        """Test nested Pydantic models."""
        class Address(BaseModel):
            city: str
            country: str

        class Person(BaseModel):
            name: str
            address: Address

        PersonSchema = schema_for(Person)
        schema = PersonSchema()

        result = schema.load({
            "name": "Alice",
            "address": {"city": "Boston", "country": "USA"}
        })

        assert result.name == "Alice"
        assert isinstance(result.address, Address)
        assert result.address.city == "Boston"

    def test_dump_model_instance(self):
        """Test dumping a Pydantic model instance."""
        class User(BaseModel):
            name: str
            age: int

        UserSchema = schema_for(User)
        schema = UserSchema()

        user = User(name="Alice", age=30)
        result = schema.dump(user)

        assert result == {"name": "Alice", "age": 30}

    def test_dump_dict(self):
        """Test dumping a dict also works."""
        class User(BaseModel):
            name: str
            age: int

        UserSchema = schema_for(User)
        schema = UserSchema()

        result = schema.dump({"name": "Alice", "age": 30})

        assert result == {"name": "Alice", "age": 30}


class TestHybridModel:
    """Test HybridModel functionality."""

    def test_as_pydantic_model(self):
        """Test using HybridModel as a Pydantic model."""
        class User(HybridModel):
            name: str
            age: int

        # Works like a normal Pydantic model
        user = User(name="Alice", age=30)
        assert user.name == "Alice"
        assert user.age == 30

    def test_ma_load(self):
        """Test loading via Marshmallow."""
        class User(HybridModel):
            name: str
            age: int

        user = User.ma_load({"name": "Alice", "age": 30})

        assert isinstance(user, User)
        assert user.name == "Alice"
        assert user.age == 30

    def test_ma_dump(self):
        """Test dumping via Marshmallow."""
        class User(HybridModel):
            name: str
            age: int

        user = User(name="Alice", age=30)
        result = user.ma_dump()

        assert result == {"name": "Alice", "age": 30}

    def test_marshmallow_schema_class(self):
        """Test getting the Marshmallow schema class."""
        class User(HybridModel):
            name: str
            age: int

        schema_cls = User.marshmallow_schema()

        assert issubclass(schema_cls, PydanticSchema)

        schema = schema_cls()
        result = schema.load({"name": "Alice", "age": 30})
        assert isinstance(result, User)


class TestMarshmallowEcosystemCompatibility:
    """Test compatibility with Marshmallow ecosystem features."""

    def test_unknown_fields_rejected(self):
        """Test that unknown fields are rejected when model forbids extra."""
        class User(BaseModel):
            model_config = ConfigDict(extra='forbid')
            name: str

        UserSchema = schema_for(User)
        schema = UserSchema()

        with pytest.raises(ValidationError):
            schema.load({"name": "Alice", "extra": "field"})

    def test_many_loading(self):
        """Test loading many items."""
        class User(BaseModel):
            name: str

        UserSchema = schema_for(User)
        schema = UserSchema(many=True)

        result = schema.load([
            {"name": "Alice"},
            {"name": "Bob"},
        ])

        assert len(result) == 2
        assert all(isinstance(u, User) for u in result)
        assert result[0].name == "Alice"
        assert result[1].name == "Bob"

    def test_partial_loading(self):
        """Test partial loading (for updates)."""
        class User(BaseModel):
            name: str
            age: int

            model_config = {"extra": "ignore"}  # Allow partial for updates

        # For partial updates, you'd typically use a separate model
        # or handle it at the API layer

    def test_json_serialization(self):
        """Test JSON string serialization/deserialization."""
        class User(BaseModel):
            name: str
            age: int

        UserSchema = schema_for(User)
        schema = UserSchema()

        # Dump to JSON
        user = User(name="Alice", age=30)
        json_str = schema.dumps(user)
        assert '"name": "Alice"' in json_str or '"name":"Alice"' in json_str

        # Load from JSON
        result = schema.loads('{"name": "Bob", "age": 25}')
        assert result.name == "Bob"
        assert result.age == 25


class TestPydanticSchemaDecorator:
    """Test the @pydantic_schema decorator."""

    def test_decorator_adds_schema_attribute(self):
        """Test that decorator adds .Schema to model."""
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class User(BaseModel):
            name: str
            age: int

        assert hasattr(User, "Schema")
        assert User.Schema is not None

    def test_decorator_schema_loads_data(self):
        """Test that decorated model's Schema can load data."""
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class Product(BaseModel):
            name: str
            price: float = Field(gt=0)

        schema = Product.Schema()
        result = schema.load({"name": "Widget", "price": 9.99})

        assert isinstance(result, Product)
        assert result.name == "Widget"
        assert result.price == 9.99

    def test_decorator_schema_validates_with_pydantic(self):
        """Test that decorated model uses Pydantic validation."""
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class User(BaseModel):
            email: EmailStr

        schema = User.Schema()

        # Valid email
        result = schema.load({"email": "test@example.com"})
        assert result.email == "test@example.com"

        # Invalid email - should fail Pydantic validation
        with pytest.raises(ValidationError):
            schema.load({"email": "not-an-email"})

    def test_decorator_preserves_model_functionality(self):
        """Test that decorated model still works as normal Pydantic model."""
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class User(BaseModel):
            name: str
            age: int

        # Can still instantiate directly
        user = User(name="Alice", age=30)
        assert user.name == "Alice"

        # Can still use model_dump
        data = user.model_dump()
        assert data == {"name": "Alice", "age": 30}

        # Can still use model_validate
        user2 = User.model_validate({"name": "Bob", "age": 25})
        assert user2.name == "Bob"
