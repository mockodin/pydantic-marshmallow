"""Tests for the Pydantic-Marshmallow bridge."""

import queue
import threading

import pytest
from marshmallow import ValidationError, pre_load
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from pydantic_marshmallow import HybridModel, PydanticSchema, schema_for
from pydantic_marshmallow.bridge import _hybrid_instance_cache, _hybrid_schema_cache


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


class TestHybridModelInstanceCaching:
    """Verify the hook-guarded instance cache doesn't leak state."""

    def test_repeated_ma_load_independent_results(self):
        """Repeated ma_load calls produce independent model instances."""
        class Item(HybridModel):
            name: str
            value: int

        a = Item.ma_load({"name": "alpha", "value": 1})
        b = Item.ma_load({"name": "beta", "value": 2})

        assert a.name == "alpha" and a.value == 1
        assert b.name == "beta" and b.value == 2
        assert a is not b

    def test_repeated_ma_dump_independent_results(self):
        """Repeated ma_dump calls produce independent dicts."""
        class Item(HybridModel):
            name: str
            value: int

        a = Item(name="alpha", value=1)
        b = Item(name="beta", value=2)

        da = a.ma_dump()
        db = b.ma_dump()

        assert da == {"name": "alpha", "value": 1}
        assert db == {"name": "beta", "value": 2}

    def test_hookless_schema_is_cached(self):
        """Hookless HybridModel schemas use the cached instance."""
        class Plain(HybridModel):
            name: str

        # Warm up the cache
        Plain.ma_load({"name": "first"})

        assert Plain in _hybrid_instance_cache

    def test_hooked_schema_skips_instance_cache(self):
        """_default_schema_instance() refuses to cache schemas with hooks."""
        class Greeter(HybridModel):
            name: str

        # Build a hooked schema class that wraps the same model
        base_schema = Greeter.marshmallow_schema()

        class HookedSchema(base_schema):  # type: ignore[misc]
            @pre_load
            def uppercase_name(self, data, **kwargs):
                data["name"] = data["name"].upper()
                return data

        # Inject the hooked schema so _default_schema_instance() finds it
        _hybrid_schema_cache[Greeter] = HookedSchema
        _hybrid_instance_cache.pop(Greeter, None)

        try:
            result = Greeter.ma_load({"name": "alice"})

            # Hook executed — proves the schema class was used
            assert result.name == "ALICE"

            # Guard prevented caching — proves the hook flag check works
            assert Greeter not in _hybrid_instance_cache

            # Second call also gets a fresh instance with working hook
            result2 = Greeter.ma_load({"name": "bob"})
            assert result2.name == "BOB"
        finally:
            # Clean up: restore the original hookless schema
            _hybrid_schema_cache[Greeter] = base_schema
            _hybrid_instance_cache.pop(Greeter, None)

    def test_concurrent_ma_load_thread_safety(self):
        """Concurrent ma_load calls from multiple threads are safe."""
        class Counter(HybridModel):
            name: str
            idx: int

        errors: queue.Queue[str] = queue.Queue()

        def worker(thread_id: int):
            for i in range(50):
                result = Counter.ma_load({"name": f"t{thread_id}", "idx": i})
                if result.name != f"t{thread_id}" or result.idx != i:
                    errors.put(
                        f"Thread {thread_id} iteration {i}: "
                        f"got name={result.name}, idx={result.idx}"
                    )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        error_list = list(errors.queue)
        assert error_list == [], f"Thread safety violations: {error_list}"


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


# ============================================================================
# H5: Cache stampede double-check in from_model()
# ============================================================================


class TestCacheStampede:
    """H5: from_model() should double-check cache after acquiring lock."""

    def test_from_model_returns_cached_on_second_call(self) -> None:
        """Calling from_model twice returns the same class (cached)."""

        class CacheTestModel(BaseModel):
            x: int

        schema1 = PydanticSchema.from_model(CacheTestModel)
        schema2 = PydanticSchema.from_model(CacheTestModel)
        assert schema1 is schema2

    def test_concurrent_from_model_same_class(self) -> None:
        """Two threads calling from_model for same model get same class."""

        class ConcurrentModel(BaseModel):
            val: str

        results: list[type] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_schema() -> None:
            try:
                result = PydanticSchema.from_model(ConcurrentModel)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=create_schema) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 4
        # All threads should get the same cached class
        assert all(r is results[0] for r in results)
