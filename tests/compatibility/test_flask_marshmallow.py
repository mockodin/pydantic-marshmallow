"""
Tests for Flask-Marshmallow integration.

Verifies that PydanticSchema works correctly with Flask-Marshmallow
in typical Flask application patterns.
"""

import pytest
from marshmallow import Schema
from pydantic import Field, field_validator

from pydantic_marshmallow import schema_for

# Import shared models from compatibility conftest
from .conftest import AddressPydantic, ProductPydantic, UserPydantic, UserWithAddressPydantic

# Third-party imports with conditional availability
try:
    from flask import Flask, jsonify
    from flask_marshmallow import Marshmallow

    FLASK_MARSHMALLOW_AVAILABLE = True
except ImportError:
    FLASK_MARSHMALLOW_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FLASK_MARSHMALLOW_AVAILABLE,
    reason="flask and flask-marshmallow not installed"
)


@pytest.fixture
def app():
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def ma(app):
    """Initialize Flask-Marshmallow with app."""
    return Marshmallow(app)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestFlaskMarshmallowBaseline:
    """Verify Flask-Marshmallow works normally (baseline)."""

    def test_flask_marshmallow_initialization(self, app, ma):
        """Flask-Marshmallow initializes correctly."""
        assert ma is not None
        assert hasattr(ma, "Schema")

    def test_native_schema_registration(self, app, ma):
        """Native Marshmallow schemas work with Flask-Marshmallow."""
        from marshmallow import fields as ma_fields

        # Use explicit field declarations (works on both MA 3.x and 4.x)
        class NativeUserSchema(ma.Schema):
            id = ma_fields.Integer()
            name = ma_fields.String()
            email = ma_fields.String()

        schema = NativeUserSchema()
        result = schema.dump({"id": 1, "name": "Test", "email": "test@example.com"})
        assert result["name"] == "Test"


class TestPydanticSchemaWithFlask:
    """Test PydanticSchema works with Flask."""

    def test_schema_for_with_flask_app(self, app):
        """schema_for creates schemas usable in Flask context."""
        UserSchema = schema_for(UserPydantic)

        with app.app_context():
            schema = UserSchema()
            user = schema.load(
                {"name": "Test User", "email": "test@example.com", "age": 25}
            )

            assert user.name == "Test User"
            assert user.email == "test@example.com"
            assert user.age == 25

    def test_json_serialization_in_flask(self, app, client):
        """PydanticSchema output is JSON-serializable for Flask responses."""
        UserSchema = schema_for(UserPydantic)

        @app.route("/user")
        def get_user():
            user = UserPydantic(
                id=1, name="Flask User", email="flask@example.com", age=30
            )
            schema = UserSchema()
            return jsonify(schema.dump(user))

        response = client.get("/user")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Flask User"
        assert data["email"] == "flask@example.com"

    def test_request_validation(self, app, client):
        """PydanticSchema validates incoming request data."""
        UserSchema = schema_for(UserPydantic)

        @app.route("/users", methods=["POST"])
        def create_user():
            from flask import request
            from marshmallow import ValidationError

            schema = UserSchema()
            try:
                user = schema.load(request.get_json())
                return jsonify(schema.dump(user)), 201
            except ValidationError as e:
                return jsonify({"error": e.messages}), 400

        # Valid request
        response = client.post(
            "/users",
            json={"name": "New User", "email": "new@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 201

        # Invalid request (empty name)
        response = client.post(
            "/users",
            json={"name": "", "email": "invalid@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 400


class TestPydanticSchemaInheritance:
    """Test schema inheritance patterns with Flask-Marshmallow."""

    def test_schema_is_marshmallow_schema(self, ma):
        """PydanticSchema is a proper Marshmallow Schema subclass."""
        UserSchema = schema_for(UserPydantic)
        assert issubclass(UserSchema, Schema)

        schema = UserSchema()
        assert isinstance(schema, Schema)

    def test_schema_has_expected_attributes(self):
        """PydanticSchema has all expected Marshmallow attributes."""
        UserSchema = schema_for(UserPydantic)

        # Check class-level attributes
        assert hasattr(UserSchema, "Meta")
        assert hasattr(UserSchema, "_declared_fields")
        assert hasattr(UserSchema, "load")
        assert hasattr(UserSchema, "dump")
        assert hasattr(UserSchema, "loads")
        assert hasattr(UserSchema, "dumps")

    def test_schema_meta_options(self):
        """Schema Meta options are accessible."""
        UserSchema = schema_for(UserPydantic)
        assert hasattr(UserSchema, "Meta")
        assert hasattr(UserSchema.Meta, "model")
        assert UserSchema.Meta.model is UserPydantic


class TestNestedSchemas:
    """Test nested Pydantic models with Flask."""

    def test_nested_model_serialization(self, app, client):
        """Nested Pydantic models serialize correctly."""
        UserWithAddressSchema = schema_for(UserWithAddressPydantic)

        @app.route("/user-with-address")
        def get_user_with_address():
            user = UserWithAddressPydantic(
                name="Nested User",
                email="nested@example.com",
                address=AddressPydantic(
                    street="123 Main St",
                    city="Boston",
                    country="USA",
                    zip_code="02101",
                ),
            )
            schema = UserWithAddressSchema()
            return jsonify(schema.dump(user))

        response = client.get("/user-with-address")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Nested User"
        assert data["address"]["city"] == "Boston"
        assert data["address"]["zip_code"] == "02101"

    def test_nested_model_deserialization(self, app):
        """Nested Pydantic models deserialize correctly."""
        UserWithAddressSchema = schema_for(UserWithAddressPydantic)

        with app.app_context():
            schema = UserWithAddressSchema()
            user = schema.load(
                {
                    "name": "Test Nested",
                    "email": "test@example.com",
                    "address": {
                        "street": "456 Oak Ave",
                        "city": "Seattle",
                        "country": "USA",
                    },
                }
            )

            assert user.name == "Test Nested"
            assert user.address.street == "456 Oak Ave"
            assert user.address.city == "Seattle"


class TestListFields:
    """Test list/array fields with Flask."""

    def test_list_field_serialization(self, app, client):
        """List fields serialize correctly."""
        ProductSchema = schema_for(ProductPydantic)

        @app.route("/product")
        def get_product():
            product = ProductPydantic(
                id=1, name="Widget", price=19.99, tags=["sale", "featured", "new"]
            )
            schema = ProductSchema()
            return jsonify(schema.dump(product))

        response = client.get("/product")
        assert response.status_code == 200
        data = response.get_json()
        assert data["tags"] == ["sale", "featured", "new"]

    def test_list_field_deserialization(self, app):
        """List fields deserialize correctly."""
        ProductSchema = schema_for(ProductPydantic)

        with app.app_context():
            schema = ProductSchema()
            product = schema.load(
                {"name": "Gadget", "price": 29.99, "tags": ["electronics", "gadgets"]}
            )

            assert product.tags == ["electronics", "gadgets"]


class TestValidationInFlaskContext:
    """Test Pydantic validation works in Flask context."""

    def test_field_validation_works(self, app):
        """Pydantic field validators run in Flask context."""
        UserSchema = schema_for(UserPydantic)

        from pydantic_marshmallow import BridgeValidationError

        with app.app_context():
            schema = UserSchema()

            # Valid data
            user = schema.load({"name": "Valid User", "email": "valid@example.com"})
            assert user.name == "Valid User"

            # Invalid age (negative)
            with pytest.raises(BridgeValidationError):
                schema.load(
                    {"name": "User", "email": "user@example.com", "age": -5}
                )

    def test_custom_validator_works(self, app):
        """Custom Pydantic validators run in Flask context."""
        UserSchema = schema_for(UserPydantic)

        from pydantic_marshmallow import BridgeValidationError

        with app.app_context():
            schema = UserSchema()

            # Name with only spaces should trigger custom validator
            with pytest.raises(BridgeValidationError):
                schema.load(
                    {
                        "name": "   ",  # Should fail custom validator
                        "email": "test@example.com",
                    }
                )


class TestMultipleSchemasInApp:
    """Test multiple PydanticSchema instances in same app."""

    def test_multiple_schemas_coexist(self, app, client):
        """Multiple PydanticSchema instances work together."""
        UserSchema = schema_for(UserPydantic)
        ProductSchema = schema_for(ProductPydantic)

        @app.route("/user/<int:user_id>")
        def get_user(user_id):
            user = UserPydantic(id=user_id, name="User", email="user@example.com")
            return jsonify(UserSchema().dump(user))

        @app.route("/product/<int:product_id>")
        def get_product(product_id):
            product = ProductPydantic(id=product_id, name="Product", price=9.99)
            return jsonify(ProductSchema().dump(product))

        # Test both endpoints
        user_response = client.get("/user/1")
        assert user_response.status_code == 200
        assert user_response.get_json()["id"] == 1

        product_response = client.get("/product/2")
        assert product_response.status_code == 200
        assert product_response.get_json()["id"] == 2


class TestErrorHandling:
    """Test error handling in Flask context."""

    def test_validation_error_response(self, app, client):
        """Validation errors can be properly formatted for API responses."""
        UserSchema = schema_for(UserPydantic)

        from pydantic_marshmallow import BridgeValidationError

        @app.route("/validate-user", methods=["POST"])
        def validate_user():
            from flask import request

            schema = UserSchema()
            try:
                user = schema.load(request.get_json())
                return jsonify(schema.dump(user))
            except BridgeValidationError as e:
                # Convert to API error response
                return jsonify({"status": "error", "errors": e.messages}), 422

        # Send invalid data
        response = client.post(
            "/validate-user",
            json={"name": "", "email": "not-an-email"},
            content_type="application/json",
        )

        assert response.status_code == 422
        data = response.get_json()
        assert data["status"] == "error"
        assert "errors" in data
