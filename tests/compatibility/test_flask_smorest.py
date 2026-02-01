"""
Tests for flask-smorest integration.

Verifies that PydanticSchema works correctly with flask-smorest
for building REST APIs with automatic OpenAPI documentation.
"""

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field, field_validator

from pydantic_marshmallow import schema_for

# Third-party imports with conditional availability
try:
    from flask import Flask
    from flask.views import MethodView
    from flask_smorest import Api, Blueprint

    FLASK_SMOREST_AVAILABLE = True
except ImportError:
    FLASK_SMOREST_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FLASK_SMOREST_AVAILABLE, reason="flask-smorest not installed"
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


class QueryArgsPydantic(BaseModel):
    """Query parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    search: str | None = Field(
        default=None, max_length=100, description="Search query"
    )


@pytest.fixture
def app():
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["API_TITLE"] = "Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    )
    return app


@pytest.fixture
def api(app):
    """Create a flask-smorest Api instance."""
    return Api(app)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestFlaskSmorestBaseline:
    """Verify flask-smorest works normally (baseline)."""

    def test_smorest_initialization(self, app, api):
        """Flask-Smorest initializes correctly."""
        assert api is not None

    def test_native_schema_with_smorest(self, app, api, client):
        """Native Marshmallow schemas work with flask-smorest."""
        from marshmallow import fields

        class NativeUserSchema(Schema):
            id = fields.Integer(dump_only=True)
            name = fields.String(required=True)
            email = fields.String(required=True)

        blp = Blueprint("native_users", __name__, url_prefix="/native-users")

        @blp.route("/")
        @blp.response(200, NativeUserSchema)
        def get_native_user():
            return {"id": 1, "name": "Native User", "email": "native@example.com"}

        api.register_blueprint(blp)

        response = client.get("/native-users/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Native User"


class TestPydanticSchemaWithSmorest:
    """Test PydanticSchema works with flask-smorest."""

    def test_response_schema(self, app, api, client):
        """PydanticSchema works as response schema."""
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint("response_users", __name__, url_prefix="/response-users")

        @blp.route("/<int:user_id>")
        @blp.response(200, UserSchema)
        def get_user(user_id):
            user = UserPydantic(
                id=user_id, name="Test User", email="test@example.com", age=25
            )
            return UserSchema().dump(user)

        api.register_blueprint(blp)

        response = client.get("/response-users/1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 1
        assert data["name"] == "Test User"

    def test_request_body_schema(self, app, api, client):
        """PydanticSchema works as request body schema."""
        UserCreateSchema = schema_for(UserCreatePydantic)
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint("request_users", __name__, url_prefix="/request-users")

        @blp.post("/")
        @blp.arguments(UserCreateSchema)
        @blp.response(201, UserSchema)
        def create_user(data):
            # data is a Pydantic model instance
            user = UserPydantic(id=1, name=data.name, email=data.email, age=data.age)
            return UserSchema().dump(user)

        api.register_blueprint(blp)

        response = client.post(
            "/request-users/",
            json={"name": "New User", "email": "new@example.com", "age": 30},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New User"

    def test_query_args_schema(self, app, api, client):
        """PydanticSchema works for query arguments."""
        QueryArgsSchema = schema_for(QueryArgsPydantic)
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint("query_users", __name__, url_prefix="/query-users")

        @blp.route("/")
        @blp.arguments(QueryArgsSchema, location="query")
        @blp.response(200, UserSchema(many=True))
        def list_users(args):
            # args is a Pydantic model instance
            return [
                UserSchema().dump(
                    UserPydantic(
                        id=i,
                        name=f"User {i}",
                        email=f"user{i}@example.com",
                    )
                )
                for i in range(args.page, args.page + args.per_page)
            ]

        api.register_blueprint(blp)

        response = client.get("/query-users/?page=1&per_page=5")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 5


class TestRequestValidation:
    """Test request validation with flask-smorest."""

    def test_invalid_request_body(self, app, api, client):
        """Invalid request bodies are rejected."""
        UserCreateSchema = schema_for(UserCreatePydantic)

        blp = Blueprint("valid_users", __name__, url_prefix="/valid-users")

        @blp.post("/")
        @blp.arguments(UserCreateSchema)
        @blp.response(201)
        def create_user_validated(data):
            return {"status": "created"}

        api.register_blueprint(blp)

        # Empty name should fail validation
        response = client.post(
            "/valid-users/",
            json={"name": "", "email": "test@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 422  # Validation error

    def test_missing_required_field(self, app, api, client):
        """Missing required fields are caught."""
        UserCreateSchema = schema_for(UserCreatePydantic)

        blp = Blueprint("required_users", __name__, url_prefix="/required-users")

        @blp.post("/")
        @blp.arguments(UserCreateSchema)
        @blp.response(201)
        def create_user_required(data):
            return {"status": "created"}

        api.register_blueprint(blp)

        # Missing email should fail
        response = client.post(
            "/required-users/",
            json={"name": "Test User"},
            content_type="application/json",
        )
        assert response.status_code == 422

    def test_constraint_validation(self, app, api, client):
        """Pydantic constraints are enforced."""
        QueryArgsSchema = schema_for(QueryArgsPydantic)

        blp = Blueprint("constraint_users", __name__, url_prefix="/constraint-users")

        @blp.route("/")
        @blp.arguments(QueryArgsSchema, location="query")
        @blp.response(200)
        def list_users_constrained(args):
            return {"page": args.page}

        api.register_blueprint(blp)

        # per_page > 100 should fail
        response = client.get("/constraint-users/?per_page=500")
        assert response.status_code == 422


class TestOpenAPIGeneration:
    """Test OpenAPI generation with flask-smorest."""

    def test_openapi_spec_available(self, app, api, client):
        """OpenAPI spec endpoint is available."""
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint("spec_users", __name__, url_prefix="/spec-users")

        @blp.route("/")
        @blp.response(200, UserSchema)
        def get_spec_user():
            return {"id": 1, "name": "User", "email": "user@example.com"}

        api.register_blueprint(blp)

        # Check openapi.json endpoint
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.get_json()
        assert "openapi" in spec
        assert "paths" in spec

    def test_schema_in_openapi_spec(self, app, api, client):
        """PydanticSchema appears in OpenAPI spec."""
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint("schema_users", __name__, url_prefix="/schema-users")

        @blp.route("/")
        @blp.response(200, UserSchema)
        def get_schema_user():
            return {"id": 1, "name": "User", "email": "user@example.com"}

        api.register_blueprint(blp)

        response = client.get("/openapi.json")
        spec = response.get_json()

        # Verify paths exist
        assert "/schema-users/" in spec["paths"]


class TestMethodView:
    """Test MethodView support with flask-smorest."""

    def test_method_view_with_pydantic_schema(self, app, api, client):
        """PydanticSchema works with MethodView."""
        UserSchema = schema_for(UserPydantic)
        UserCreateSchema = schema_for(UserCreatePydantic)

        blp = Blueprint("method_users", __name__, url_prefix="/method-users")

        @blp.route("/")
        class UserCollection(MethodView):
            @blp.response(200, UserSchema(many=True))
            def get(self):
                return [
                    UserSchema().dump(
                        UserPydantic(id=1, name="User 1", email="user1@example.com")
                    ),
                    UserSchema().dump(
                        UserPydantic(id=2, name="User 2", email="user2@example.com")
                    ),
                ]

            @blp.arguments(UserCreateSchema)
            @blp.response(201, UserSchema)
            def post(self, data):
                user = UserPydantic(id=3, name=data.name, email=data.email, age=data.age)
                return UserSchema().dump(user)

        api.register_blueprint(blp)

        # Test GET
        get_response = client.get("/method-users/")
        assert get_response.status_code == 200
        assert len(get_response.get_json()) == 2

        # Test POST
        post_response = client.post(
            "/method-users/",
            json={"name": "New User", "email": "new@example.com"},
            content_type="application/json",
        )
        assert post_response.status_code == 201
        assert post_response.get_json()["name"] == "New User"


class TestMultipleBlueprints:
    """Test multiple blueprints with different schemas."""

    def test_multiple_blueprints_in_api(self, app, api, client):
        """Multiple blueprints with PydanticSchema work together."""
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)

        users_blp = Blueprint("multi_users", __name__, url_prefix="/multi-users")
        products_blp = Blueprint(
            "multi_products", __name__, url_prefix="/multi-products"
        )

        @users_blp.route("/<int:user_id>")
        @users_blp.response(200, UserSchema)
        def get_multi_user(user_id):
            user = UserPydantic(id=user_id, name="User", email="user@example.com")
            return UserSchema().dump(user)

        @products_blp.route("/<int:product_id>")
        @products_blp.response(200, ProductSchema)
        def get_multi_product(product_id):
            product = ProductPydantic(
                id=product_id, name="Product", price=29.99, tags=["electronics"]
            )
            return ProductSchema().dump(product)

        api.register_blueprint(users_blp)
        api.register_blueprint(products_blp)

        # Test user endpoint
        user_response = client.get("/multi-users/1")
        assert user_response.status_code == 200
        assert user_response.get_json()["name"] == "User"

        # Test product endpoint
        product_response = client.get("/multi-products/1")
        assert product_response.status_code == 200
        assert product_response.get_json()["name"] == "Product"


class TestSchemaCompatibility:
    """Test schema compatibility with flask-smorest."""

    def test_schema_is_marshmallow_schema(self):
        """PydanticSchema is a proper Marshmallow Schema subclass."""
        UserSchema = schema_for(UserPydantic)
        assert issubclass(UserSchema, Schema)

        schema = UserSchema()
        assert isinstance(schema, Schema)

    def test_schema_has_required_attributes(self):
        """PydanticSchema has attributes required by flask-smorest."""
        UserSchema = schema_for(UserPydantic)
        schema = UserSchema()

        # flask-smorest uses these attributes
        assert hasattr(schema, "fields")
        assert hasattr(schema, "load")
        assert hasattr(schema, "dump")
        assert hasattr(schema, "Meta")


class TestETagSupport:
    """Test ETag support with flask-smorest."""

    def test_etag_with_pydantic_schema(self, app, api, client):
        """ETag works with PydanticSchema responses."""
        UserSchema = schema_for(UserPydantic)

        blp = Blueprint(
            "etag_users", __name__, url_prefix="/etag-users", description="ETag test"
        )

        # Note: @blp.etag must be OUTER decorator (before @blp.response)
        # so it runs after response wrapper sets appcontext["result_dump"]
        @blp.route("/<int:user_id>")
        @blp.etag
        @blp.response(200, UserSchema)
        def get_etag_user(user_id):
            # Return model instance - let flask-smorest handle serialization
            return UserPydantic(
                id=user_id, name="ETag User", email="etag@example.com"
            )

        api.register_blueprint(blp)

        response = client.get("/etag-users/1")
        assert response.status_code == 200
        # ETag should be in response headers
        assert "ETag" in response.headers
