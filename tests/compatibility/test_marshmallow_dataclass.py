"""
Tests for marshmallow-dataclass integration and interoperability.

Verifies that PydanticSchema works correctly alongside marshmallow-dataclass
which provides similar functionality for Python dataclasses.
"""
from dataclasses import dataclass, field as dataclass_field

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field

from pydantic_marshmallow import schema_for

# Third-party imports with conditional availability
try:
    import marshmallow_dataclass
    from marshmallow_dataclass import dataclass as mm_dataclass

    MARSHMALLOW_DATACLASS_AVAILABLE = True
except ImportError:
    MARSHMALLOW_DATACLASS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MARSHMALLOW_DATACLASS_AVAILABLE, reason="marshmallow-dataclass not installed"
)


# Standard dataclasses for testing with marshmallow-dataclass
@dataclass
class AddressDataclass:
    """Address as a dataclass."""

    street: str
    city: str
    country: str = "USA"
    zip_code: str | None = None


@dataclass
class UserDataclass:
    """User as a dataclass."""

    name: str
    email: str
    age: int | None = None
    address: AddressDataclass | None = None


@dataclass
class ProductDataclass:
    """Product as a dataclass."""

    name: str
    price: float
    tags: list[str] = dataclass_field(default_factory=list)
    description: str | None = None


# Pydantic models (for comparison)
class AddressPydantic(BaseModel):
    """Address as a Pydantic model."""

    street: str
    city: str
    country: str = "USA"
    zip_code: str | None = None


class UserPydantic(BaseModel):
    """User as a Pydantic model."""

    name: str = Field(min_length=1)
    email: str
    age: int | None = Field(default=None, ge=0)
    address: AddressPydantic | None = None


class ProductPydantic(BaseModel):
    """Product as a Pydantic model."""

    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    tags: list[str] = Field(default_factory=list)
    description: str | None = None


class TestMarshmallowDataclassBaseline:
    """Verify marshmallow-dataclass works normally (baseline)."""

    def test_dataclass_schema_generation(self):
        """marshmallow-dataclass can generate schemas from dataclasses."""
        UserSchema = marshmallow_dataclass.class_schema(UserDataclass)
        schema = UserSchema()

        assert schema is not None
        assert hasattr(schema, "load")
        assert hasattr(schema, "dump")

    def test_dataclass_schema_load(self):
        """marshmallow-dataclass schemas can load data."""
        UserSchema = marshmallow_dataclass.class_schema(UserDataclass)
        schema = UserSchema()

        user = schema.load({"name": "Test User", "email": "test@example.com"})

        assert isinstance(user, UserDataclass)
        assert user.name == "Test User"
        assert user.email == "test@example.com"

    def test_dataclass_schema_dump(self):
        """marshmallow-dataclass schemas can dump data."""
        UserSchema = marshmallow_dataclass.class_schema(UserDataclass)
        schema = UserSchema()

        user = UserDataclass(name="Test User", email="test@example.com")
        result = schema.dump(user)

        assert result["name"] == "Test User"
        assert result["email"] == "test@example.com"


class TestBothSchemasCoexist:
    """Test both PydanticSchema and marshmallow-dataclass schemas work together."""

    def test_both_schemas_in_same_module(self):
        """Both schema types can coexist in the same module."""
        # Pydantic schema
        PydanticUserSchema = schema_for(UserPydantic)

        # Dataclass schema
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        # Both should be valid Schema subclasses
        assert issubclass(PydanticUserSchema, Schema)
        assert issubclass(DataclassUserSchema, Schema)

    def test_schemas_produce_different_instances(self):
        """Each schema type produces its own model instances."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        data = {"name": "Test User", "email": "test@example.com", "age": 25}

        # Load through Pydantic schema
        pydantic_user = PydanticUserSchema().load(data)
        assert isinstance(pydantic_user, UserPydantic)

        # Load through dataclass schema
        dataclass_user = DataclassUserSchema().load(data)
        assert isinstance(dataclass_user, UserDataclass)

    def test_schemas_have_same_basic_behavior(self):
        """Both schemas handle basic cases similarly."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 25,
            "address": {"street": "123 Main St", "city": "Boston", "country": "USA"},
        }

        # Both should successfully load the data
        pydantic_user = PydanticUserSchema().load(data)
        dataclass_user = DataclassUserSchema().load(data)

        # Both should have the same field values
        assert pydantic_user.name == dataclass_user.name
        assert pydantic_user.email == dataclass_user.email
        assert pydantic_user.age == dataclass_user.age


class TestFieldCompatibility:
    """Test field handling between both schema types."""

    def test_optional_fields(self):
        """Both handle optional fields correctly."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        data = {"name": "Test", "email": "test@example.com"}

        pydantic_user = PydanticUserSchema().load(data)
        dataclass_user = DataclassUserSchema().load(data)

        assert pydantic_user.age is None
        assert dataclass_user.age is None

    def test_default_values(self):
        """Both respect default values."""
        PydanticAddressSchema = schema_for(AddressPydantic)
        DataclassAddressSchema = marshmallow_dataclass.class_schema(AddressDataclass)

        data = {"street": "123 Main", "city": "Boston"}

        pydantic_address = PydanticAddressSchema().load(data)
        dataclass_address = DataclassAddressSchema().load(data)

        assert pydantic_address.country == "USA"
        assert dataclass_address.country == "USA"

    def test_list_fields(self):
        """Both handle list fields correctly."""
        PydanticProductSchema = schema_for(ProductPydantic)
        DataclassProductSchema = marshmallow_dataclass.class_schema(ProductDataclass)

        data = {"name": "Widget", "price": 19.99, "tags": ["sale", "featured"]}

        pydantic_product = PydanticProductSchema().load(data)
        dataclass_product = DataclassProductSchema().load(data)

        assert pydantic_product.tags == ["sale", "featured"]
        assert dataclass_product.tags == ["sale", "featured"]


class TestNestedSchemas:
    """Test nested schema handling."""

    def test_nested_pydantic_to_dataclass(self):
        """Nested data can flow between schema types."""
        # Load with Pydantic, get nested data
        PydanticUserSchema = schema_for(UserPydantic)

        data = {
            "name": "Test User",
            "email": "test@example.com",
            "address": {"street": "123 Main St", "city": "Boston"},
        }

        pydantic_user = PydanticUserSchema().load(data)
        assert pydantic_user.address is not None
        assert pydantic_user.address.street == "123 Main St"

        # Dump and reload with dataclass schema
        dumped = PydanticUserSchema().dump(pydantic_user)

        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)
        dataclass_user = DataclassUserSchema().load(dumped)

        assert dataclass_user.address is not None
        assert dataclass_user.address.street == "123 Main St"


class TestValidationDifferences:
    """Test validation differences between Pydantic and dataclass schemas."""

    def test_pydantic_additional_validation(self):
        """Pydantic provides additional validation that dataclass doesn't."""
        PydanticUserSchema = schema_for(UserPydantic)

        from pydantic_marshmallow import BridgeValidationError

        # Pydantic schema has min_length constraint on name
        with pytest.raises(BridgeValidationError):
            PydanticUserSchema().load({"name": "", "email": "test@example.com"})

        # Pydantic schema has ge=0 constraint on age
        with pytest.raises(BridgeValidationError):
            PydanticUserSchema().load(
                {"name": "Test", "email": "test@example.com", "age": -5}
            )

    def test_dataclass_basic_validation(self):
        """Dataclass schema provides basic type validation."""
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        from marshmallow import ValidationError

        # Invalid type for age should fail
        with pytest.raises(ValidationError):
            DataclassUserSchema().load(
                {"name": "Test", "email": "test@example.com", "age": "not an int"}
            )


class TestSchemaInheritance:
    """Test that both schema types maintain proper inheritance."""

    def test_both_are_schema_subclasses(self):
        """Both schema types are Marshmallow Schema subclasses."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        assert issubclass(PydanticUserSchema, Schema)
        assert issubclass(DataclassUserSchema, Schema)

        assert isinstance(PydanticUserSchema(), Schema)
        assert isinstance(DataclassUserSchema(), Schema)

    def test_both_have_standard_attributes(self):
        """Both schema types have standard Marshmallow attributes."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        for SchemaClass in [PydanticUserSchema, DataclassUserSchema]:
            schema = SchemaClass()

            assert hasattr(schema, "fields")
            assert hasattr(schema, "load")
            assert hasattr(schema, "dump")
            assert hasattr(schema, "loads")
            assert hasattr(schema, "dumps")


class TestMixedUsage:
    """Test mixing both schema types in realistic scenarios."""

    def test_api_style_workflow(self):
        """Both schemas work in API-style workflows."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        # Simulate receiving JSON-like data
        incoming_data = {
            "name": "API User",
            "email": "api@example.com",
            "age": 30,
            "address": {"street": "456 Oak Ave", "city": "Seattle"},
        }

        # Validate with either schema
        pydantic_user = PydanticUserSchema().load(incoming_data)
        dataclass_user = DataclassUserSchema().load(incoming_data)

        # Serialize back (for response)
        pydantic_output = PydanticUserSchema().dump(pydantic_user)
        dataclass_output = DataclassUserSchema().dump(dataclass_user)

        # Both should produce similar output
        assert pydantic_output["name"] == dataclass_output["name"]
        assert pydantic_output["email"] == dataclass_output["email"]

    def test_data_transfer_between_schemas(self):
        """Data can be transferred between Pydantic and dataclass instances."""
        PydanticUserSchema = schema_for(UserPydantic)
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        # Start with Pydantic instance
        pydantic_user = UserPydantic(
            name="Transfer User", email="transfer@example.com", age=25
        )

        # Dump to dict
        data = PydanticUserSchema().dump(pydantic_user)

        # Load as dataclass
        dataclass_user = DataclassUserSchema().load(data)

        assert dataclass_user.name == "Transfer User"
        assert dataclass_user.email == "transfer@example.com"

        # And back to Pydantic
        data2 = DataclassUserSchema().dump(dataclass_user)
        pydantic_user2 = PydanticUserSchema().load(data2)

        assert pydantic_user2.name == "Transfer User"


class TestUseCase:
    """Test practical use cases for having both schema types."""

    def test_gradual_migration_scenario(self):
        """
        Test scenario: gradually migrating from dataclasses to Pydantic.

        A team might have existing dataclasses but want to use Pydantic
        for new models. Both should work together.
        """
        # Existing legacy dataclass schema
        LegacyUserSchema = marshmallow_dataclass.class_schema(UserDataclass)

        # New Pydantic model schema
        NewProductSchema = schema_for(ProductPydantic)

        # Both work in same codebase
        user = LegacyUserSchema().load(
            {"name": "Legacy User", "email": "legacy@example.com"}
        )
        product = NewProductSchema().load(
            {"name": "New Product", "price": 29.99, "tags": ["new"]}
        )

        assert user.name == "Legacy User"
        assert product.name == "New Product"

    def test_interoperability_with_existing_code(self):
        """Test that Pydantic schemas work where dataclass schemas worked."""

        def process_with_schema(schema: Schema, data: dict) -> dict:
            """Generic function that works with any Marshmallow schema."""
            instance = schema.load(data)
            return schema.dump(instance)

        # Works with dataclass schema
        DataclassUserSchema = marshmallow_dataclass.class_schema(UserDataclass)
        result1 = process_with_schema(
            DataclassUserSchema(),
            {"name": "DC User", "email": "dc@example.com"},
        )

        # Also works with Pydantic schema
        PydanticUserSchema = schema_for(UserPydantic)
        result2 = process_with_schema(
            PydanticUserSchema(),
            {"name": "Pydantic User", "email": "pydantic@example.com"},
        )

        assert result1["name"] == "DC User"
        assert result2["name"] == "Pydantic User"
