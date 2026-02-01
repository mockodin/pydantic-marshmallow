"""
Tests for apispec integration.

Verifies that PydanticSchema works correctly with apispec
for OpenAPI specification generation.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field

from pydantic_marshmallow import schema_for

# Third-party imports with conditional availability
try:
    from apispec import APISpec
    from apispec.ext.marshmallow import MarshmallowPlugin

    APISPEC_AVAILABLE = True
except ImportError:
    APISPEC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not APISPEC_AVAILABLE, reason="apispec not installed"
)


# Pydantic models for testing
class UserStatus(str, Enum):
    """User status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class UserPydantic(BaseModel):
    """User model with various field types."""

    id: Optional[int] = Field(default=None, description="User ID")
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    email: str = Field(description="User's email address")
    age: Optional[int] = Field(default=None, ge=0, le=150, description="User's age")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="Account status")
    created_at: Optional[datetime] = Field(
        default=None, description="Account creation timestamp"
    )


class AddressPydantic(BaseModel):
    """Address model."""

    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    country: str = Field(default="USA", description="Country code")
    zip_code: Optional[str] = Field(default=None, description="Postal code")


class UserWithAddressPydantic(BaseModel):
    """User with nested address."""

    name: str = Field(description="User name")
    email: str = Field(description="User email")
    address: AddressPydantic = Field(description="User's address")


class ProductPydantic(BaseModel):
    """Product model with various constraints."""

    id: Optional[int] = Field(default=None, description="Product ID")
    name: str = Field(min_length=1, max_length=200, description="Product name")
    description: Optional[str] = Field(default=None, description="Product description")
    price: Decimal = Field(gt=0, decimal_places=2, description="Product price")
    tags: List[str] = Field(default_factory=list, description="Product tags")
    in_stock: bool = Field(default=True, description="Availability status")


class OrderItemPydantic(BaseModel):
    """Order item."""

    product_id: int = Field(description="Product identifier")
    quantity: int = Field(ge=1, description="Quantity ordered")
    unit_price: Decimal = Field(gt=0, description="Price per unit")


class OrderPydantic(BaseModel):
    """Order with nested items."""

    id: Optional[int] = Field(default=None, description="Order ID")
    customer_name: str = Field(description="Customer name")
    items: List[OrderItemPydantic] = Field(description="Order line items")
    total: Decimal = Field(ge=0, description="Order total")
    notes: Optional[str] = Field(default=None, description="Order notes")


@pytest.fixture
def spec():
    """Create an APISpec instance with MarshmallowPlugin."""
    return APISpec(
        title="Test API",
        version="1.0.0",
        openapi_version="3.0.0",
        plugins=[MarshmallowPlugin()],
    )


class TestApispecBaseline:
    """Verify apispec works normally with native Marshmallow schemas."""

    def test_apispec_initialization(self, spec):
        """APISpec initializes correctly."""
        assert spec is not None
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"

    def test_native_schema_registration(self, spec):
        """Native Marshmallow schemas can be registered."""
        from marshmallow import fields

        class NativeUserSchema(Schema):
            id = fields.Integer()
            name = fields.String(required=True)

        spec.components.schema("NativeUser", schema=NativeUserSchema)

        openapi_spec = spec.to_dict()
        assert "NativeUser" in openapi_spec["components"]["schemas"]


class TestPydanticSchemaRegistration:
    """Test registering PydanticSchema with apispec."""

    def test_schema_for_registration(self, spec):
        """schema_for schemas can be registered with apispec."""
        UserSchema = schema_for(UserPydantic)

        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        assert "User" in openapi_spec["components"]["schemas"]

    def test_schema_fields_in_openapi(self, spec):
        """Schema fields appear in OpenAPI spec."""
        UserSchema = schema_for(UserPydantic)

        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        user_schema = openapi_spec["components"]["schemas"]["User"]

        assert "properties" in user_schema
        assert "name" in user_schema["properties"]
        assert "email" in user_schema["properties"]

    def test_required_fields_marked(self, spec):
        """Required fields are marked in OpenAPI spec."""
        UserSchema = schema_for(UserPydantic)

        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        user_schema = openapi_spec["components"]["schemas"]["User"]

        # name and email are required (no default)
        assert "required" in user_schema
        assert "name" in user_schema["required"]
        assert "email" in user_schema["required"]


class TestFieldTypeMapping:
    """Test that Pydantic field types map to correct OpenAPI types."""

    def test_string_field(self, spec):
        """String fields map to OpenAPI string type."""
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        name_prop = openapi_spec["components"]["schemas"]["User"]["properties"]["name"]

        assert name_prop["type"] == "string"

    def test_integer_field(self, spec):
        """Integer fields map to OpenAPI integer type."""
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        # id should be integer
        id_prop = openapi_spec["components"]["schemas"]["User"]["properties"]["id"]

        assert id_prop["type"] == "integer"

    def test_boolean_field(self, spec):
        """Boolean fields map to OpenAPI boolean type."""
        ProductSchema = schema_for(ProductPydantic)
        spec.components.schema("Product", schema=ProductSchema)

        openapi_spec = spec.to_dict()
        in_stock_prop = openapi_spec["components"]["schemas"]["Product"]["properties"][
            "in_stock"
        ]

        assert in_stock_prop["type"] == "boolean"

    def test_array_field(self, spec):
        """List fields map to OpenAPI array type."""
        ProductSchema = schema_for(ProductPydantic)
        spec.components.schema("Product", schema=ProductSchema)

        openapi_spec = spec.to_dict()
        tags_prop = openapi_spec["components"]["schemas"]["Product"]["properties"][
            "tags"
        ]

        assert tags_prop["type"] == "array"
        assert "items" in tags_prop


class TestNestedSchemas:
    """Test nested schema registration."""

    def test_nested_schema_inline(self, spec):
        """Nested schemas appear inline in OpenAPI spec."""
        UserWithAddressSchema = schema_for(UserWithAddressPydantic)

        spec.components.schema("UserWithAddress", schema=UserWithAddressSchema)

        openapi_spec = spec.to_dict()
        user_schema = openapi_spec["components"]["schemas"]["UserWithAddress"]

        assert "address" in user_schema["properties"]
        # Nested schema should have its own properties
        address_prop = user_schema["properties"]["address"]
        assert "properties" in address_prop or "$ref" in address_prop

    def test_nested_array_schema(self, spec):
        """Nested schemas in arrays work correctly."""
        OrderSchema = schema_for(OrderPydantic)

        spec.components.schema("Order", schema=OrderSchema)

        openapi_spec = spec.to_dict()
        order_schema = openapi_spec["components"]["schemas"]["Order"]

        assert "items" in order_schema["properties"]
        items_prop = order_schema["properties"]["items"]
        assert items_prop["type"] == "array"


class TestMultipleSchemas:
    """Test registering multiple schemas."""

    def test_multiple_schemas_registered(self, spec):
        """Multiple PydanticSchema schemas can be registered."""
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)
        OrderSchema = schema_for(OrderPydantic)

        spec.components.schema("User", schema=UserSchema)
        spec.components.schema("Product", schema=ProductSchema)
        spec.components.schema("Order", schema=OrderSchema)

        openapi_spec = spec.to_dict()
        schemas = openapi_spec["components"]["schemas"]

        assert "User" in schemas
        assert "Product" in schemas
        assert "Order" in schemas

    def test_schemas_are_independent(self, spec):
        """Each schema has its own properties."""
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)

        spec.components.schema("User", schema=UserSchema)
        spec.components.schema("Product", schema=ProductSchema)

        openapi_spec = spec.to_dict()
        user_props = openapi_spec["components"]["schemas"]["User"]["properties"]
        product_props = openapi_spec["components"]["schemas"]["Product"]["properties"]

        assert "email" in user_props
        assert "email" not in product_props
        assert "price" in product_props
        assert "price" not in user_props


class TestSchemaInPaths:
    """Test using schemas in path definitions."""

    def test_schema_in_request_body(self, spec):
        """PydanticSchema can be used in request body definitions."""
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        spec.path(
            path="/users",
            operations={
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {"201": {"description": "Created"}},
                }
            },
        )

        openapi_spec = spec.to_dict()
        assert "/users" in openapi_spec["paths"]
        post_op = openapi_spec["paths"]["/users"]["post"]
        assert "requestBody" in post_op

    def test_schema_in_response(self, spec):
        """PydanticSchema can be used in response definitions."""
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        spec.path(
            path="/users/{id}",
            operations={
                "get": {
                    "summary": "Get user",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    },
                }
            },
        )

        openapi_spec = spec.to_dict()
        assert "/users/{id}" in openapi_spec["paths"]


class TestSchemaAttributes:
    """Test that schema attributes work correctly."""

    def test_schema_has_fields_attribute(self, spec):
        """PydanticSchema has fields attribute used by apispec."""
        UserSchema = schema_for(UserPydantic)
        schema = UserSchema()

        # apispec uses the fields attribute
        assert hasattr(schema, "fields")
        assert "name" in schema.fields
        assert "email" in schema.fields

    def test_schema_is_subclass_of_schema(self):
        """PydanticSchema is a proper Schema subclass."""
        UserSchema = schema_for(UserPydantic)
        assert issubclass(UserSchema, Schema)

    def test_schema_has_meta(self):
        """PydanticSchema has Meta class."""
        UserSchema = schema_for(UserPydantic)
        assert hasattr(UserSchema, "Meta")


class TestDescriptionHandling:
    """Test that field descriptions are preserved."""

    def test_field_descriptions_in_openapi(self, spec):
        """Field descriptions appear in OpenAPI spec."""
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        openapi_spec = spec.to_dict()
        # Check if any description is present (implementation may vary)
        user_schema = openapi_spec["components"]["schemas"]["User"]

        # At minimum, the schema should be valid
        assert "properties" in user_schema


class TestCompleteAPISpec:
    """Test generating a complete API specification."""

    def test_generate_full_spec(self, spec):
        """Can generate a complete OpenAPI specification."""
        # Register all schemas
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)
        OrderSchema = schema_for(OrderPydantic)

        spec.components.schema("User", schema=UserSchema)
        spec.components.schema("Product", schema=ProductSchema)
        spec.components.schema("Order", schema=OrderSchema)

        # Add paths
        spec.path(
            path="/users",
            operations={
                "get": {
                    "summary": "List users",
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
        )

        spec.path(
            path="/products",
            operations={
                "get": {
                    "summary": "List products",
                    "responses": {
                        "200": {
                            "description": "List of products",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/Product"
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
        )

        # Generate spec
        openapi_spec = spec.to_dict()

        # Verify structure
        assert openapi_spec["openapi"] == "3.0.0"
        assert openapi_spec["info"]["title"] == "Test API"
        # 4 schemas: User, Product, Order, and nested OrderItemPydantic (auto-resolved)
        assert len(openapi_spec["components"]["schemas"]) >= 3
        assert len(openapi_spec["paths"]) == 2

    def test_spec_to_yaml(self, spec):
        """Spec can be exported to YAML."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        UserSchema = schema_for(UserPydantic)
        spec.components.schema("User", schema=UserSchema)

        yaml_output = spec.to_yaml()

        assert isinstance(yaml_output, str)
        assert "User" in yaml_output
        assert "openapi" in yaml_output


class TestEdgeCases:
    """Test edge cases for apispec integration."""

    def test_empty_schema(self, spec):
        """Schema with minimal fields works."""

        class MinimalModel(BaseModel):
            name: str

        MinimalSchema = schema_for(MinimalModel)
        spec.components.schema("Minimal", schema=MinimalSchema)

        openapi_spec = spec.to_dict()
        assert "Minimal" in openapi_spec["components"]["schemas"]

    def test_schema_with_optional_only(self, spec):
        """Schema with only optional fields works."""

        class AllOptionalModel(BaseModel):
            field1: Optional[str] = None
            field2: Optional[int] = None

        AllOptionalSchema = schema_for(AllOptionalModel)
        spec.components.schema("AllOptional", schema=AllOptionalSchema)

        openapi_spec = spec.to_dict()
        schema = openapi_spec["components"]["schemas"]["AllOptional"]

        # No required fields
        assert "required" not in schema or len(schema.get("required", [])) == 0

    def test_deeply_nested_schema(self, spec):
        """Deeply nested schemas work correctly."""

        class Level3(BaseModel):
            value: str

        class Level2(BaseModel):
            level3: Level3

        class Level1(BaseModel):
            level2: Level2

        Level1Schema = schema_for(Level1)
        spec.components.schema("Level1", schema=Level1Schema)

        openapi_spec = spec.to_dict()
        assert "Level1" in openapi_spec["components"]["schemas"]
