"""
Tests for webargs integration.

Verifies that PydanticSchema works correctly with webargs
for request parsing and validation.
"""

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field, field_validator

from pydantic_marshmallow import schema_for

# Third-party imports with conditional availability
try:
    from flask import Flask, jsonify
    from webargs import fields as webargs_fields
    from webargs.flaskparser import parser, use_args, use_kwargs

    WEBARGS_AVAILABLE = True
except ImportError:
    WEBARGS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not WEBARGS_AVAILABLE, reason="flask and webargs not installed"
)


# Pydantic models for testing
class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    """User creation schema."""

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(min_length=8)
    age: int | None = Field(default=None, ge=13, le=150)

    @field_validator("password")
    @classmethod
    def password_must_have_digit(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    """User update schema (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int | None = Field(default=None, ge=13, le=150)


class FilterParams(BaseModel):
    """Filter parameters for list endpoints."""

    status: str | None = Field(default=None, pattern=r"^(active|inactive|pending)$")
    sort_by: str = Field(default="created_at")
    order: str = Field(default="desc", pattern=r"^(asc|desc)$")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class ItemCreate(BaseModel):
    """Item creation for testing JSON body."""

    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0, default=0)
    metadata: dict | None = None


# Flask fixtures (app, client) provided by conftest.py


class TestWebargsBaseline:
    """Verify webargs works normally (baseline)."""

    def test_webargs_parser_available(self):
        """webargs parser is available."""
        assert parser is not None
        assert use_args is not None
        assert use_kwargs is not None

    def test_native_marshmallow_schema_with_webargs(self, app, client):
        """Native Marshmallow schemas work with webargs."""

        class NativeSearchSchema(Schema):
            query = webargs_fields.String(required=True)
            limit = webargs_fields.Integer(load_default=10)

        native_schema = NativeSearchSchema()

        @app.route("/native-search")
        @use_args(native_schema, location="query")
        def native_search(args):
            return jsonify(args)

        response = client.get("/native-search?query=test&limit=5")
        assert response.status_code == 200
        data = response.get_json()
        assert data["query"] == "test"
        assert data["limit"] == 5


class TestPydanticSchemaWithWebargs:
    """Test PydanticSchema works with webargs decorators."""

    def test_use_args_with_query_params(self, app, client):
        """PydanticSchema works with @use_args for query params."""
        SearchSchema = schema_for(SearchQuery)
        search_schema = SearchSchema()

        @app.route("/search")
        @use_args(search_schema, location="query")
        def search(args):
            # args is the Pydantic model instance
            return jsonify(
                {"query": args.query, "limit": args.limit, "offset": args.offset}
            )

        response = client.get("/search?query=python&limit=25&offset=10")
        assert response.status_code == 200
        data = response.get_json()
        assert data["query"] == "python"
        assert data["limit"] == 25
        assert data["offset"] == 10

    def test_use_args_with_defaults(self, app, client):
        """PydanticSchema uses default values correctly."""
        SearchSchema = schema_for(SearchQuery)
        search_schema = SearchSchema()

        @app.route("/search-defaults")
        @use_args(search_schema, location="query")
        def search_defaults(args):
            return jsonify(
                {"query": args.query, "limit": args.limit, "offset": args.offset}
            )

        response = client.get("/search-defaults?query=test")
        assert response.status_code == 200
        data = response.get_json()
        assert data["query"] == "test"
        assert data["limit"] == 10  # default
        assert data["offset"] == 0  # default

    def test_use_args_with_json_body(self, app, client):
        """PydanticSchema works with @use_args for JSON body."""
        ItemSchema = schema_for(ItemCreate)
        item_schema = ItemSchema()

        @app.route("/items", methods=["POST"])
        @use_args(item_schema, location="json")
        def create_item(args):
            return (
                jsonify(
                    {"name": args.name, "price": args.price, "quantity": args.quantity}
                ),
                201,
            )

        response = client.post(
            "/items",
            json={"name": "Widget", "price": 19.99, "quantity": 5},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Widget"
        assert data["price"] == 19.99
        assert data["quantity"] == 5


class TestValidationWithWebargs:
    """Test Pydantic validation works through webargs."""

    def test_validation_error_on_invalid_params(self, app, client):
        """Pydantic validation errors are raised through webargs."""
        SearchSchema = schema_for(SearchQuery)
        search_schema = SearchSchema()

        @app.route("/search-validated")
        @use_args(search_schema, location="query")
        def search_validated(args):
            return jsonify({"query": args.query})

        # Missing required field
        response = client.get("/search-validated")
        assert response.status_code == 422  # webargs validation error

    def test_constraint_validation(self, app, client):
        """Pydantic constraints are enforced through webargs."""
        SearchSchema = schema_for(SearchQuery)
        search_schema = SearchSchema()

        @app.route("/search-constrained")
        @use_args(search_schema, location="query")
        def search_constrained(args):
            return jsonify({"limit": args.limit})

        # limit > 100 should fail
        response = client.get("/search-constrained?query=test&limit=500")
        assert response.status_code == 422

    def test_custom_validator_with_webargs(self, app, client):
        """Custom Pydantic validators work through webargs."""
        UserSchema = schema_for(UserCreate)
        user_schema = UserSchema()

        @app.route("/users", methods=["POST"])
        @use_args(user_schema, location="json")
        def create_user(args):
            return jsonify({"name": args.name}), 201

        # Valid password (has digit)
        response = client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "secure123",
            },
            content_type="application/json",
        )
        assert response.status_code == 201

        # Invalid password (no digit) - should fail custom validator
        response = client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "nodigits",
            },
            content_type="application/json",
        )
        assert response.status_code == 422


class TestFilterAndPagination:
    """Test filter/pagination patterns common in REST APIs."""

    def test_filter_params_from_query(self, app, client):
        """Filter params are parsed from query string."""
        FilterSchema = schema_for(FilterParams)
        filter_schema = FilterSchema()

        @app.route("/items")
        @use_args(filter_schema, location="query")
        def list_items(args):
            return jsonify(
                {
                    "status": args.status,
                    "sort_by": args.sort_by,
                    "order": args.order,
                    "page": args.page,
                    "per_page": args.per_page,
                }
            )

        response = client.get(
            "/items?status=active&sort_by=name&order=asc&page=2&per_page=50"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "active"
        assert data["sort_by"] == "name"
        assert data["order"] == "asc"
        assert data["page"] == 2
        assert data["per_page"] == 50

    def test_filter_params_with_defaults(self, app, client):
        """Filter params use defaults when not provided."""
        FilterSchema = schema_for(FilterParams)
        filter_schema = FilterSchema()

        @app.route("/items-defaults")
        @use_args(filter_schema, location="query")
        def list_items_defaults(args):
            return jsonify(
                {
                    "status": args.status,
                    "sort_by": args.sort_by,
                    "order": args.order,
                    "page": args.page,
                    "per_page": args.per_page,
                }
            )

        response = client.get("/items-defaults")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] is None
        assert data["sort_by"] == "created_at"
        assert data["order"] == "desc"
        assert data["page"] == 1
        assert data["per_page"] == 20

    def test_invalid_filter_value(self, app, client):
        """Invalid filter values are rejected."""
        FilterSchema = schema_for(FilterParams)
        filter_schema = FilterSchema()

        @app.route("/items-validated")
        @use_args(filter_schema, location="query")
        def list_items_validated(args):
            return jsonify({"status": args.status})

        # Invalid status value
        response = client.get("/items-validated?status=invalid")
        assert response.status_code == 422


class TestPartialUpdates:
    """Test partial update patterns with optional fields."""

    def test_partial_update_with_some_fields(self, app, client):
        """Partial updates work with only some fields provided."""
        UserUpdateSchema = schema_for(UserUpdate)
        update_schema = UserUpdateSchema()

        @app.route("/users/<int:user_id>", methods=["PATCH"])
        @use_args(update_schema, location="json")
        def update_user(args, user_id):
            # Only return non-None fields
            updates = {k: v for k, v in args.model_dump().items() if v is not None}
            return jsonify({"user_id": user_id, "updates": updates})

        response = client.patch(
            "/users/1", json={"name": "New Name"}, content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["user_id"] == 1
        assert data["updates"] == {"name": "New Name"}

    def test_partial_update_with_empty_body(self, app, client):
        """Partial updates work with empty body (no changes)."""
        UserUpdateSchema = schema_for(UserUpdate)
        update_schema = UserUpdateSchema()

        @app.route("/users-empty/<int:user_id>", methods=["PATCH"])
        @use_args(update_schema, location="json")
        def update_user_empty(args, user_id):
            updates = {k: v for k, v in args.model_dump().items() if v is not None}
            return jsonify({"user_id": user_id, "updates": updates})

        response = client.patch(
            "/users-empty/1", json={}, content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["updates"] == {}


class TestSchemaTypeCompatibility:
    """Test that PydanticSchema is type-compatible with webargs."""

    def test_schema_is_marshmallow_schema(self):
        """PydanticSchema is recognized as Marshmallow Schema."""
        SearchSchema = schema_for(SearchQuery)
        assert issubclass(SearchSchema, Schema)

        schema = SearchSchema()
        assert isinstance(schema, Schema)

    def test_schema_has_load_method(self):
        """PydanticSchema has required load method."""
        SearchSchema = schema_for(SearchQuery)
        schema = SearchSchema()

        assert hasattr(schema, "load")
        assert callable(schema.load)

    def test_schema_has_fields(self):
        """PydanticSchema has fields attribute."""
        SearchSchema = schema_for(SearchQuery)
        schema = SearchSchema()

        assert hasattr(schema, "fields")
        assert "query" in schema.fields
        assert "limit" in schema.fields


class TestMultipleLocations:
    """Test parsing from multiple locations."""

    def test_query_and_json_together(self, app, client):
        """Can parse from both query params and JSON body."""
        FilterSchema = schema_for(FilterParams)
        ItemSchema = schema_for(ItemCreate)

        filter_schema = FilterSchema()
        item_schema = ItemSchema()

        @app.route("/items-filtered", methods=["POST"])
        @use_args(filter_schema, location="query")
        @use_args(item_schema, location="json")
        def create_item_filtered(filter_args, item_args):
            return (
                jsonify(
                    {
                        "filter": {
                            "page": filter_args.page,
                            "per_page": filter_args.per_page,
                        },
                        "item": {"name": item_args.name, "price": item_args.price},
                    }
                ),
                201,
            )

        response = client.post(
            "/items-filtered?page=2&per_page=50",
            json={"name": "Widget", "price": 9.99},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["filter"]["page"] == 2
        assert data["item"]["name"] == "Widget"


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_query_string(self, app, client):
        """Handles empty query string with defaults."""
        FilterSchema = schema_for(FilterParams)
        filter_schema = FilterSchema()

        @app.route("/items-edge")
        @use_args(filter_schema, location="query")
        def list_items_edge(args):
            return jsonify({"page": args.page})

        response = client.get("/items-edge")
        assert response.status_code == 200
        data = response.get_json()
        assert data["page"] == 1  # default

    def test_extra_fields_ignored(self, app, client):
        """Extra fields in request are ignored."""
        SearchSchema = schema_for(SearchQuery)
        search_schema = SearchSchema()

        @app.route("/search-extra")
        @use_args(search_schema, location="query")
        def search_extra(args):
            return jsonify({"query": args.query})

        response = client.get("/search-extra?query=test&extra_field=ignored")
        assert response.status_code == 200
        data = response.get_json()
        assert data["query"] == "test"
        assert "extra_field" not in data
