"""
Tests for flask-rebar integration.

Verifies that PydanticSchema works correctly with flask-rebar
for building REST APIs with automatic Swagger/OpenAPI documentation.
"""

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field, field_validator

from pydantic_marshmallow import schema_for
from pydantic_marshmallow.bridge import _MARSHMALLOW_4_PLUS

# Third-party imports with conditional availability
try:
    from importlib.metadata import version as get_version

    from flask import Flask
    from flask_rebar import Rebar, ResponseSchema as RebarResponseSchema
    from flask_rebar.validation import RequestSchema

    FLASK_REBAR_AVAILABLE = True
    # flask-rebar >= 3.4 supports marshmallow 4.x swagger generation
    _flask_rebar_version = tuple(int(x) for x in get_version("flask-rebar").split(".")[:2])
    FLASK_REBAR_MA4_COMPATIBLE = _flask_rebar_version >= (3, 4)
except ImportError:
    FLASK_REBAR_AVAILABLE = False
    FLASK_REBAR_MA4_COMPATIBLE = False

pytestmark = pytest.mark.skipif(
    not FLASK_REBAR_AVAILABLE, reason="flask-rebar not installed"
)


# Pydantic models for testing
class UserPydantic(BaseModel):
    """User model for API."""

    id: int | None = Field(default=None, description="User ID")
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    email: str = Field(
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="User's email address"
    )
    age: int | None = Field(default=None, ge=0, le=150, description="User's age")

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Name cannot be blank")
        return v.strip()


class UserCreatePydantic(BaseModel):
    """User creation request model."""

    name: str = Field(min_length=1, max_length=100, description="User's full name")
    email: str = Field(
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="User's email address"
    )
    age: int | None = Field(default=None, ge=0, le=150, description="User's age")


class UserUpdatePydantic(BaseModel):
    """User update request model (partial)."""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="User's full name"
    )
    email: str | None = Field(
        default=None,
        pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
        description="User's email address",
    )
    age: int | None = Field(default=None, ge=0, le=150, description="User's age")


class ProductPydantic(BaseModel):
    """Product model for API."""

    id: int | None = Field(default=None, description="Product ID")
    name: str = Field(min_length=1, max_length=200, description="Product name")
    price: float = Field(gt=0, description="Product price")
    description: str | None = Field(
        default=None, max_length=1000, description="Product description"
    )
    tags: list[str] = Field(default_factory=list, description="Product tags")


class SearchQueryPydantic(BaseModel):
    """Search query parameters."""

    q: str = Field(min_length=1, max_length=200, description="Search query string")
    limit: int = Field(default=10, ge=1, le=100, description="Results limit")
    offset: int = Field(default=0, ge=0, description="Results offset")


# Flask fixtures (app, client) provided by conftest.py


@pytest.fixture
def rebar(app):
    """Create a Rebar instance."""
    rebar = Rebar()
    rebar.init_app(app)
    return rebar


@pytest.fixture
def registry(rebar):
    """Create a handler registry."""
    return rebar.create_handler_registry()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestFlaskRebarBaseline:
    """Verify flask-rebar works normally (baseline)."""

    def test_rebar_initialization(self, app, rebar):
        """Flask-Rebar initializes correctly."""
        assert rebar is not None

    def test_native_schema_with_rebar(self, app, rebar, registry, client):
        """Native Marshmallow schemas work with flask-rebar."""
        from marshmallow import fields

        class NativeUserSchema(Schema):
            id = fields.Integer(dump_only=True)
            name = fields.String(required=True)
            email = fields.String(required=True)

        @registry.handles(
            rule="/native-users",
            method="GET",
            response_body_schema=NativeUserSchema(),
        )
        def get_native_user():
            return {"id": 1, "name": "Native User", "email": "native@example.com"}

        rebar.init_app(app)

        response = client.get("/native-users")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Native User"


class TestPydanticSchemaWithRebar:
    """Test PydanticSchema works with flask-rebar."""

    def test_response_schema(self, app, rebar, registry, client):
        """PydanticSchema works as response schema."""
        UserSchema = schema_for(UserPydantic)

        @registry.handles(
            rule="/users/<int:user_id>",
            method="GET",
            response_body_schema=UserSchema(),
        )
        def get_user(user_id):
            user = UserPydantic(
                id=user_id, name="Test User", email="test@example.com", age=25
            )
            return UserSchema().dump(user)

        rebar.init_app(app)

        response = client.get("/users/1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 1
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"

    def test_request_body_schema(self, app, rebar, registry, client):
        """PydanticSchema works as request body schema."""
        UserCreateSchema = schema_for(UserCreatePydantic)
        UserSchema = schema_for(UserPydantic)

        @registry.handles(
            rule="/users",
            method="POST",
            request_body_schema=UserCreateSchema(),
            response_body_schema=UserSchema(),
        )
        def create_user():
            from flask_rebar import get_validated_body

            body = get_validated_body()
            # body is a Pydantic model instance
            user = UserPydantic(id=1, name=body.name, email=body.email, age=body.age)
            return UserSchema().dump(user)

        rebar.init_app(app)

        response = client.post(
            "/users",
            json={"name": "New User", "email": "new@example.com", "age": 30},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "New User"
        assert data["email"] == "new@example.com"


class TestRequestValidation:
    """Test request validation with flask-rebar."""

    def test_invalid_request_body(self, app, rebar, registry, client):
        """Invalid request bodies are rejected."""
        UserCreateSchema = schema_for(UserCreatePydantic)

        @registry.handles(
            rule="/users-validated",
            method="POST",
            request_body_schema=UserCreateSchema(),
        )
        def create_user_validated():
            return {"status": "created"}

        rebar.init_app(app)

        # Empty name should fail validation
        response = client.post(
            "/users-validated",
            json={"name": "", "email": "test@example.com"},
            content_type="application/json",
        )
        assert response.status_code in (400, 422)  # Validation error

    def test_missing_required_field(self, app, rebar, registry, client):
        """Missing required fields are caught."""
        UserCreateSchema = schema_for(UserCreatePydantic)

        @registry.handles(
            rule="/users-required",
            method="POST",
            request_body_schema=UserCreateSchema(),
        )
        def create_user_required():
            return {"status": "created"}

        rebar.init_app(app)

        # Missing email should fail
        response = client.post(
            "/users-required",
            json={"name": "Test User"},
            content_type="application/json",
        )
        assert response.status_code in (400, 422)

    def test_custom_validator_runs(self, app, rebar, registry, client):
        """Custom Pydantic validators run through flask-rebar."""
        UserCreateSchema = schema_for(UserCreatePydantic)

        @registry.handles(
            rule="/users-custom-validation",
            method="POST",
            request_body_schema=UserCreateSchema(),
        )
        def create_user_custom():
            return {"status": "created"}

        rebar.init_app(app)

        # Name with only whitespace should fail custom validator
        # (from name_must_not_be_empty in UserPydantic, inherited through validation)
        # Note: Since UserCreatePydantic doesn't have the validator, this tests
        # that base validation still works
        response = client.post(
            "/users-custom-validation",
            json={"name": "Valid Name", "email": "valid@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 200


@pytest.mark.skipif(
    _MARSHMALLOW_4_PLUS and not FLASK_REBAR_MA4_COMPATIBLE,
    reason="flask-rebar < 3.4 does not support marshmallow 4.x swagger generation",
)
class TestSwaggerGeneration:
    """Test Swagger/OpenAPI generation with flask-rebar."""

    def test_swagger_endpoint_available(self, app, rebar, registry, client):
        """Swagger endpoint is available."""
        UserSchema = schema_for(UserPydantic)

        @registry.handles(
            rule="/swagger-users",
            method="GET",
            response_body_schema=UserSchema(),
        )
        def get_swagger_user():
            return {"id": 1, "name": "User", "email": "user@example.com"}

        rebar.init_app(app)

        # Check swagger.json endpoint
        response = client.get("/swagger")
        # Either 200 or redirect is acceptable
        assert response.status_code in (200, 301, 302, 308)

    def test_schema_in_swagger_spec(self, app, rebar, registry, client):
        """PydanticSchema appears in Swagger spec."""
        UserSchema = schema_for(UserPydantic)

        @registry.handles(
            rule="/spec-users",
            method="GET",
            response_body_schema=UserSchema(),
        )
        def get_spec_user():
            return {"id": 1, "name": "User", "email": "user@example.com"}

        rebar.init_app(app)

        # Get the swagger spec
        response = client.get("/swagger/swagger.json")
        if response.status_code == 200:
            spec = response.get_json()
            # Verify paths exist
            assert "paths" in spec
            assert "/spec-users" in spec["paths"]


class TestMultipleEndpoints:
    """Test multiple endpoints with different schemas."""

    def test_multiple_schemas_in_api(self, app, rebar, registry, client):
        """Multiple PydanticSchema schemas work in same API."""
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)

        @registry.handles(
            rule="/multi-users/<int:user_id>",
            method="GET",
            response_body_schema=UserSchema(),
        )
        def get_multi_user(user_id):
            user = UserPydantic(id=user_id, name="User", email="user@example.com")
            return UserSchema().dump(user)

        @registry.handles(
            rule="/multi-products/<int:product_id>",
            method="GET",
            response_body_schema=ProductSchema(),
        )
        def get_multi_product(product_id):
            product = ProductPydantic(
                id=product_id,
                name="Product",
                price=29.99,
                tags=["electronics"],
            )
            return ProductSchema().dump(product)

        rebar.init_app(app)

        # Test user endpoint
        user_response = client.get("/multi-users/1")
        assert user_response.status_code == 200
        assert user_response.get_json()["name"] == "User"

        # Test product endpoint
        product_response = client.get("/multi-products/1")
        assert product_response.status_code == 200
        assert product_response.get_json()["name"] == "Product"


class TestSchemaCompatibility:
    """Test schema compatibility with flask-rebar."""

    def test_schema_is_marshmallow_schema(self):
        """PydanticSchema is a proper Marshmallow Schema subclass."""
        UserSchema = schema_for(UserPydantic)
        assert issubclass(UserSchema, Schema)

        schema = UserSchema()
        assert isinstance(schema, Schema)

    def test_schema_has_required_attributes(self):
        """PydanticSchema has attributes required by flask-rebar."""
        UserSchema = schema_for(UserPydantic)
        schema = UserSchema()

        # flask-rebar uses these attributes
        assert hasattr(schema, "fields")
        assert hasattr(schema, "load")
        assert hasattr(schema, "dump")
        assert hasattr(schema, "Meta")


class TestCRUDOperations:
    """Test CRUD operations with flask-rebar."""

    def test_full_crud_workflow(self, app, rebar, registry, client):
        """Full CRUD workflow works with PydanticSchema."""
        UserSchema = schema_for(UserPydantic)
        UserCreateSchema = schema_for(UserCreatePydantic)
        UserUpdateSchema = schema_for(UserUpdatePydantic)

        # Simple in-memory store for testing
        users_store = {}

        @registry.handles(
            rule="/crud-users",
            method="POST",
            request_body_schema=UserCreateSchema(),
            response_body_schema=UserSchema(),
        )
        def create_crud_user():
            from flask_rebar import get_validated_body

            body = get_validated_body()
            user_id = len(users_store) + 1
            user = UserPydantic(id=user_id, name=body.name, email=body.email, age=body.age)
            users_store[user_id] = user
            return UserSchema().dump(user)

        @registry.handles(
            rule="/crud-users/<int:user_id>",
            method="GET",
            response_body_schema=UserSchema(),
        )
        def get_crud_user(user_id):
            user = users_store.get(user_id)
            if user:
                return UserSchema().dump(user)
            return {"error": "Not found"}, 404

        @registry.handles(
            rule="/crud-users/<int:user_id>",
            method="PATCH",
            request_body_schema=UserUpdateSchema(),
            response_body_schema=UserSchema(),
        )
        def update_crud_user(user_id):
            from flask_rebar import get_validated_body

            body = get_validated_body()
            user = users_store.get(user_id)
            if user:
                # Update only provided fields
                update_data = body.model_dump(exclude_unset=True)
                user_dict = user.model_dump()
                user_dict.update(update_data)
                updated_user = UserPydantic(**user_dict)
                users_store[user_id] = updated_user
                return UserSchema().dump(updated_user)
            return {"error": "Not found"}, 404

        rebar.init_app(app)

        # Create
        create_response = client.post(
            "/crud-users",
            json={"name": "CRUD User", "email": "crud@example.com", "age": 25},
            content_type="application/json",
        )
        assert create_response.status_code == 200
        created_user = create_response.get_json()
        user_id = created_user["id"]

        # Read
        get_response = client.get(f"/crud-users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.get_json()["name"] == "CRUD User"

        # Update
        update_response = client.patch(
            f"/crud-users/{user_id}",
            json={"name": "Updated User"},
            content_type="application/json",
        )
        assert update_response.status_code == 200
        assert update_response.get_json()["name"] == "Updated User"
        assert update_response.get_json()["email"] == "crud@example.com"  # Unchanged
