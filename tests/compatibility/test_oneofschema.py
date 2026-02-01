"""
Tests for marshmallow-oneofschema compatibility.

marshmallow-oneofschema provides polymorphic schema support - selecting
different schemas based on object type. This is useful for inheritance
hierarchies and discriminated unions.
"""

import pytest

oneofschema = pytest.importorskip("marshmallow_oneofschema")

from pydantic import BaseModel, Field  # noqa: E402

from pydantic_marshmallow import PydanticSchema  # noqa: E402

# =============================================================================
# Test Models - Polymorphic Hierarchy
# =============================================================================


class Animal(BaseModel):
    """Base animal model."""

    name: str
    age: int = Field(ge=0)


class Dog(Animal):
    """Dog model with breed."""

    breed: str
    is_good_boy: bool = True


class Cat(Animal):
    """Cat model with indoor/outdoor preference."""

    indoor: bool = True
    lives_remaining: int = Field(default=9, ge=0, le=9)


class Bird(Animal):
    """Bird model with wingspan."""

    wingspan_cm: float = Field(ge=0)
    can_fly: bool = True


# =============================================================================
# Schemas for Polymorphic Models
# =============================================================================


class DogSchema(PydanticSchema[Dog]):
    """Schema for Dog."""

    class Meta:
        model = Dog


class CatSchema(PydanticSchema[Cat]):
    """Schema for Cat."""

    class Meta:
        model = Cat


class BirdSchema(PydanticSchema[Bird]):
    """Schema for Bird."""

    class Meta:
        model = Bird


class AnimalSchema(oneofschema.OneOfSchema):
    """
    Polymorphic schema that selects Dog/Cat/Bird based on type.

    This demonstrates using PydanticSchema subclasses with OneOfSchema.
    """

    type_schemas = {
        "dog": DogSchema,
        "cat": CatSchema,
        "bird": BirdSchema,
    }

    def get_obj_type(self, obj):
        """Get type string from object."""
        if isinstance(obj, Dog):
            return "dog"
        elif isinstance(obj, Cat):
            return "cat"
        elif isinstance(obj, Bird):
            return "bird"
        else:
            raise ValueError(f"Unknown animal type: {type(obj)}")


# =============================================================================
# Tests
# =============================================================================


class TestOneOfSchemaBasics:
    """Test basic OneOfSchema functionality with PydanticSchema."""

    def test_load_dog(self):
        """Test loading a dog through polymorphic schema."""
        schema = AnimalSchema()
        data = {
            "type": "dog",
            "name": "Buddy",
            "age": 5,
            "breed": "Golden Retriever",
            "is_good_boy": True,
        }

        result = schema.load(data)

        assert isinstance(result, Dog)
        assert result.name == "Buddy"
        assert result.age == 5
        assert result.breed == "Golden Retriever"
        assert result.is_good_boy is True

    def test_load_cat(self):
        """Test loading a cat through polymorphic schema."""
        schema = AnimalSchema()
        data = {
            "type": "cat",
            "name": "Whiskers",
            "age": 3,
            "indoor": True,
            "lives_remaining": 9,
        }

        result = schema.load(data)

        assert isinstance(result, Cat)
        assert result.name == "Whiskers"
        assert result.age == 3
        assert result.indoor is True
        assert result.lives_remaining == 9

    def test_load_bird(self):
        """Test loading a bird through polymorphic schema."""
        schema = AnimalSchema()
        data = {
            "type": "bird",
            "name": "Tweety",
            "age": 2,
            "wingspan_cm": 15.5,
            "can_fly": True,
        }

        result = schema.load(data)

        assert isinstance(result, Bird)
        assert result.name == "Tweety"
        assert result.age == 2
        assert result.wingspan_cm == 15.5
        assert result.can_fly is True

    def test_dump_dog(self):
        """Test dumping a dog through polymorphic schema."""
        schema = AnimalSchema()
        dog = Dog(name="Max", age=4, breed="Labrador", is_good_boy=True)

        result = schema.dump(dog)

        assert result["type"] == "dog"
        assert result["name"] == "Max"
        assert result["age"] == 4
        assert result["breed"] == "Labrador"
        assert result["is_good_boy"] is True

    def test_dump_cat(self):
        """Test dumping a cat through polymorphic schema."""
        schema = AnimalSchema()
        cat = Cat(name="Felix", age=7, indoor=False, lives_remaining=8)

        result = schema.dump(cat)

        assert result["type"] == "cat"
        assert result["name"] == "Felix"
        assert result["age"] == 7
        assert result["indoor"] is False
        assert result["lives_remaining"] == 8

    def test_dump_bird(self):
        """Test dumping a bird through polymorphic schema."""
        schema = AnimalSchema()
        bird = Bird(name="Polly", age=10, wingspan_cm=25.0, can_fly=False)

        result = schema.dump(bird)

        assert result["type"] == "bird"
        assert result["name"] == "Polly"
        assert result["age"] == 10
        assert result["wingspan_cm"] == 25.0
        assert result["can_fly"] is False


class TestOneOfSchemaValidation:
    """Test that Pydantic validation works through OneOfSchema."""

    def test_validation_error_propagates(self):
        """Test that Pydantic validation errors propagate correctly."""
        schema = AnimalSchema()
        data = {
            "type": "dog",
            "name": "Buddy",
            "age": -5,  # Invalid: must be >= 0
            "breed": "Lab",
        }

        with pytest.raises(Exception):  # noqa: B017
            schema.load(data)

    def test_cat_lives_validation(self):
        """Test Cat's lives_remaining constraint (0-9)."""
        schema = AnimalSchema()
        data = {
            "type": "cat",
            "name": "Mittens",
            "age": 5,
            "lives_remaining": 10,  # Invalid: max is 9
        }

        with pytest.raises(Exception):  # noqa: B017
            schema.load(data)

    def test_bird_wingspan_validation(self):
        """Test Bird's wingspan constraint (>= 0)."""
        schema = AnimalSchema()
        data = {
            "type": "bird",
            "name": "Tweety",
            "age": 1,
            "wingspan_cm": -5.0,  # Invalid: must be >= 0
        }

        with pytest.raises(Exception):  # noqa: B017
            schema.load(data)

    def test_unknown_type_error(self):
        """Test that unknown type raises error."""
        schema = AnimalSchema()
        data = {
            "type": "fish",
            "name": "Nemo",
            "age": 1,
        }

        with pytest.raises(Exception):  # noqa: B017
            schema.load(data)


class TestOneOfSchemaWithMany:
    """Test OneOfSchema with many=True (list of polymorphic objects)."""

    def test_load_many_mixed(self):
        """Test loading a list of mixed animal types."""
        schema = AnimalSchema(many=True)
        data = [
            {"type": "dog", "name": "Rex", "age": 3, "breed": "German Shepherd"},
            {"type": "cat", "name": "Luna", "age": 2, "indoor": True},
            {"type": "bird", "name": "Sky", "age": 1, "wingspan_cm": 20.0},
        ]

        result = schema.load(data)

        assert len(result) == 3
        assert isinstance(result[0], Dog)
        assert isinstance(result[1], Cat)
        assert isinstance(result[2], Bird)

        assert result[0].name == "Rex"
        assert result[1].name == "Luna"
        assert result[2].name == "Sky"

    def test_dump_many_mixed(self):
        """Test dumping a list of mixed animal types."""
        schema = AnimalSchema(many=True)
        animals = [
            Dog(name="Spot", age=4, breed="Dalmatian"),
            Cat(name="Garfield", age=8, indoor=True),
            Bird(name="Zazu", age=5, wingspan_cm=30.0),
        ]

        result = schema.dump(animals)

        assert len(result) == 3
        assert result[0]["type"] == "dog"
        assert result[1]["type"] == "cat"
        assert result[2]["type"] == "bird"


class TestOneOfSchemaDefaults:
    """Test that Pydantic defaults work correctly through OneOfSchema."""

    def test_dog_default_good_boy(self):
        """Test Dog's is_good_boy defaults to True."""
        schema = AnimalSchema()
        data = {
            "type": "dog",
            "name": "Cooper",
            "age": 2,
            "breed": "Beagle",
            # is_good_boy not provided - should default to True
        }

        result = schema.load(data)

        assert result.is_good_boy is True

    def test_cat_default_lives(self):
        """Test Cat's lives_remaining defaults to 9."""
        schema = AnimalSchema()
        data = {
            "type": "cat",
            "name": "Shadow",
            "age": 4,
            # indoor and lives_remaining not provided
        }

        result = schema.load(data)

        assert result.indoor is True
        assert result.lives_remaining == 9

    def test_bird_default_can_fly(self):
        """Test Bird's can_fly defaults to True."""
        schema = AnimalSchema()
        data = {
            "type": "bird",
            "name": "Robin",
            "age": 1,
            "wingspan_cm": 12.0,
            # can_fly not provided
        }

        result = schema.load(data)

        assert result.can_fly is True


class TestOneOfSchemaWithTypeField:
    """Test type field customization."""

    def test_custom_type_field_name(self):
        """Test using a custom type field name."""

        class CustomAnimalSchema(oneofschema.OneOfSchema):
            type_field = "animal_type"  # Custom field name
            type_schemas = {
                "dog": DogSchema,
                "cat": CatSchema,
            }

            def get_obj_type(self, obj):
                if isinstance(obj, Dog):
                    return "dog"
                elif isinstance(obj, Cat):
                    return "cat"
                raise ValueError(f"Unknown type: {type(obj)}")

        schema = CustomAnimalSchema()

        # Load with custom type field
        data = {
            "animal_type": "dog",
            "name": "Duke",
            "age": 6,
            "breed": "Boxer",
        }

        result = schema.load(data)
        assert isinstance(result, Dog)
        assert result.name == "Duke"

        # Dump includes custom type field
        dumped = schema.dump(result)
        assert "animal_type" in dumped
        assert dumped["animal_type"] == "dog"
