"""Tests for dump() serialization options.

Tests Pydantic's exclude_unset, exclude_defaults, exclude_none options
exposed through the Marshmallow bridge.
"""

from pydantic import BaseModel, computed_field

from pydantic_marshmallow import schema_for


class TestExcludeNone:
    """Test exclude_none=True removes None values from dump."""

    def test_exclude_none_basic(self):
        """exclude_none removes None values from dump output."""
        class User(BaseModel):
            name: str
            nickname: str | None = None
            bio: str | None = None

        schema = schema_for(User)()
        user = User(name="Alice", bio="Developer")

        # Default includes None
        result = schema.dump(user)
        assert "nickname" in result
        assert result["nickname"] is None

        # exclude_none removes it
        result = schema.dump(user, exclude_none=True)
        assert "nickname" not in result
        assert result["bio"] == "Developer"

    def test_exclude_none_with_many(self):
        """exclude_none works with many=True."""
        class Item(BaseModel):
            name: str
            quantity: int | None = None

        schema = schema_for(Item)()
        items = [
            Item(name="Widget"),
            Item(name="Gadget", quantity=5),
        ]

        results = schema.dump(items, many=True, exclude_none=True)
        assert "quantity" not in results[0]
        assert results[1]["quantity"] == 5

    def test_exclude_none_preserves_non_none(self):
        """exclude_none preserves non-None optional values."""
        class Profile(BaseModel):
            name: str
            avatar_url: str | None = None
            status: str | None = None

        schema = schema_for(Profile)()
        profile = Profile(name="Alice", avatar_url="http://example.com/avatar.jpg")

        result = schema.dump(profile, exclude_none=True)
        assert result["avatar_url"] == "http://example.com/avatar.jpg"
        assert "status" not in result


class TestExcludeUnset:
    """Test exclude_unset=True removes fields that weren't explicitly set."""

    def test_exclude_unset_basic(self):
        """exclude_unset removes fields not explicitly provided."""
        class Config(BaseModel):
            host: str
            port: int = 8080
            debug: bool = False

        schema = schema_for(Config)()
        config = Config(host="localhost")  # port and debug use defaults

        # Default includes all
        result = schema.dump(config)
        assert "port" in result
        assert "debug" in result

        # exclude_unset removes unset fields
        result = schema.dump(config, exclude_unset=True)
        assert "host" in result
        assert "port" not in result
        assert "debug" not in result

    def test_exclude_unset_with_explicitly_set_defaults(self):
        """exclude_unset preserves explicitly set fields even if they equal defaults."""
        class Flags(BaseModel):
            enabled: bool = False
            visible: bool = True

        schema = schema_for(Flags)()
        # Explicitly set enabled=False (which is also the default)
        flags = Flags(enabled=False)

        result = schema.dump(flags, exclude_unset=True)
        assert "enabled" in result  # Explicitly set, so preserved
        assert "visible" not in result  # Not set, uses default

    def test_exclude_unset_all_fields_set(self):
        """All fields included when all are explicitly set."""
        class Settings(BaseModel):
            theme: str = "light"
            font_size: int = 12

        schema = schema_for(Settings)()
        settings = Settings(theme="dark", font_size=16)

        result = schema.dump(settings, exclude_unset=True)
        assert result == {"theme": "dark", "font_size": 16}


class TestExcludeDefaults:
    """Test exclude_defaults=True removes fields equal to their default."""

    def test_exclude_defaults_basic(self):
        """exclude_defaults removes fields equal to their default value."""
        class Settings(BaseModel):
            theme: str = "light"
            font_size: int = 12
            custom_css: str = ""

        schema = schema_for(Settings)()
        # Set theme to non-default, leave others as default
        settings = Settings(theme="dark", font_size=12, custom_css="")

        result = schema.dump(settings, exclude_defaults=True)
        assert "theme" in result  # Non-default value
        assert result["theme"] == "dark"
        assert "font_size" not in result  # Equals default
        assert "custom_css" not in result  # Equals default

    def test_exclude_defaults_with_required(self):
        """Required fields are always included."""
        class User(BaseModel):
            name: str  # Required, no default
            status: str = "active"

        schema = schema_for(User)()
        user = User(name="Alice", status="active")

        result = schema.dump(user, exclude_defaults=True)
        assert "name" in result  # Required
        assert "status" not in result  # Equals default

    def test_exclude_defaults_none_default(self):
        """Field with None default is excluded when value is None."""
        class Profile(BaseModel):
            name: str
            bio: str | None = None

        schema = schema_for(Profile)()
        profile = Profile(name="Alice", bio=None)

        result = schema.dump(profile, exclude_defaults=True)
        assert "name" in result
        assert "bio" not in result  # Equals default (None)


class TestCombinedExclusionOptions:
    """Test combining multiple exclusion options."""

    def test_exclude_none_and_unset(self):
        """Combine exclude_none and exclude_unset."""
        class Record(BaseModel):
            id: int
            name: str
            description: str | None = None
            status: str = "active"

        schema = schema_for(Record)()
        record = Record(id=1, name="Test")  # description=None, status=default

        result = schema.dump(record, exclude_none=True, exclude_unset=True)
        assert "id" in result
        assert "name" in result
        assert "description" not in result  # None + unset
        assert "status" not in result  # unset

    def test_exclude_defaults_and_none(self):
        """Combine exclude_defaults and exclude_none."""
        class Config(BaseModel):
            enabled: bool = False
            value: int | None = None

        schema = schema_for(Config)()
        config = Config(enabled=False, value=None)

        result = schema.dump(config, exclude_defaults=True, exclude_none=True)
        assert "enabled" not in result  # Equals default
        assert "value" not in result  # Is None (and equals default)

    def test_all_exclusion_options(self):
        """Combine all three exclusion options."""
        class Item(BaseModel):
            id: int
            name: str
            description: str | None = None
            active: bool = True
            extra: str = ""

        schema = schema_for(Item)()
        item = Item(id=1, name="Widget")

        result = schema.dump(
            item,
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True
        )
        # Only explicitly set non-default, non-None values
        assert set(result.keys()) == {"id", "name"}


class TestExclusionOptionsWithComputedFields:
    """Test exclusion options work with computed fields."""

    def test_exclude_none_with_computed(self):
        """exclude_none removes None computed fields."""
        class Product(BaseModel):
            price: float
            discount: float | None = None

            @computed_field
            @property
            def final_price(self) -> float | None:
                if self.discount is None:
                    return None
                return self.price * (1 - self.discount)

        schema = schema_for(Product)()
        product = Product(price=100)  # No discount

        result = schema.dump(product, exclude_none=True)
        assert "final_price" not in result
        assert "discount" not in result
        assert "price" in result

    def test_non_none_computed_preserved(self):
        """Non-None computed fields are preserved with exclude_none=True."""
        class Rectangle(BaseModel):
            width: float
            height: float

            @computed_field
            @property
            def area(self) -> float:
                return self.width * self.height

        schema = schema_for(Rectangle)()
        rect = Rectangle(width=10, height=5)

        result = schema.dump(rect, exclude_none=True)
        assert result["area"] == 50.0


class TestExclusionOptionsEdgeCases:
    """Edge cases for exclusion options."""

    def test_empty_result_possible(self):
        """All fields can be excluded, resulting in empty dict."""
        class AllDefaults(BaseModel):
            a: str = "default_a"
            b: int = 0
            c: str | None = None

        schema = schema_for(AllDefaults)()
        obj = AllDefaults()

        result = schema.dump(obj, exclude_defaults=True)
        assert result == {}

    def test_nested_model_exclusions(self):
        """Exclusion options don't affect nested model structure."""
        class Address(BaseModel):
            city: str
            country: str = "USA"

        class Person(BaseModel):
            name: str
            address: Address

        schema = schema_for(Person)()
        person = Person(name="Alice", address=Address(city="Boston"))

        result = schema.dump(person, exclude_unset=True)
        # Nested object structure preserved
        assert "address" in result
        assert result["address"]["city"] == "Boston"
