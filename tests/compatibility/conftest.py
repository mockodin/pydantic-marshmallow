"""Shared fixtures for compatibility tests.

Provides common Flask app, client, and model fixtures for all compatibility
test files to eliminate duplication.
"""

import pytest
from pydantic import BaseModel, EmailStr, Field, field_validator

from pydantic_marshmallow import schema_for

# =============================================================================
# Shared Pydantic Models for Compatibility Tests
# =============================================================================

class UserPydantic(BaseModel):
    """Standard user model for API compatibility tests."""
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int | None = Field(default=None, ge=0, le=150)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Name cannot be blank")
        return v.strip()


class UserCreatePydantic(BaseModel):
    """User creation payload model."""
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class UserUpdatePydantic(BaseModel):
    """User update payload model (all fields optional)."""
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    age: int | None = Field(None, ge=0)


class AddressPydantic(BaseModel):
    """Address model for nested structure tests."""
    street: str
    city: str
    country: str = "USA"
    zip_code: str | None = None


class UserWithAddressPydantic(BaseModel):
    """User with nested address for complex API tests."""
    name: str
    email: str
    address: AddressPydantic


class ProductPydantic(BaseModel):
    """Product model for e-commerce API tests."""
    id: int | None = None
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    in_stock: bool = True
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class OrderPydantic(BaseModel):
    """Order model for collection tests."""
    customer_name: str
    items: list[str]
    total: float = Field(ge=0)


class QueryArgsPydantic(BaseModel):
    """Query parameters model for GET requests."""
    page: int = Field(ge=1, default=1)
    per_page: int = Field(ge=1, le=100, default=20)
    sort_by: str | None = None
    order: str = Field(default="asc", pattern=r"^(asc|desc)$")


class SearchQueryPydantic(BaseModel):
    """Search query model for search endpoints."""
    q: str = Field(min_length=1)
    limit: int = Field(ge=1, le=100, default=10)
    offset: int = Field(ge=0, default=0)


class FilterParamsPydantic(BaseModel):
    """Filter parameters for list endpoints."""
    status: str | None = None
    category: str | None = None
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)


class ErrorResponsePydantic(BaseModel):
    """Standard error response model."""
    error: str
    code: int
    details: dict | None = None


# =============================================================================
# Test Data Constants
# =============================================================================

USER_DATA = {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "age": 30,
}

USER_CREATE_DATA = {
    "name": "Bob Jones",
    "email": "bob@example.com",
}

ADDRESS_DATA = {
    "street": "123 Main St",
    "city": "Boston",
    "country": "USA",
    "zip_code": "02101",
}

PRODUCT_DATA = {
    "name": "Widget",
    "price": 29.99,
    "in_stock": True,
    "description": "A useful widget",
}

ORDER_DATA = {
    "customer_name": "Alice",
    "items": ["item1", "item2"],
    "total": 49.99,
}

QUERY_ARGS_DATA = {
    "page": 1,
    "per_page": 20,
    "sort_by": "name",
    "order": "asc",
}

INVALID_USER_DATA = {
    "name": "",  # min_length violation
    "email": "invalid",  # email format
    "age": -1,  # ge=0 violation
}


# =============================================================================
# Schema Factories
# =============================================================================

@pytest.fixture
def user_schema():
    """Pre-built schema for UserPydantic."""
    return schema_for(UserPydantic)()


@pytest.fixture
def user_create_schema():
    """Pre-built schema for UserCreatePydantic."""
    return schema_for(UserCreatePydantic)()


@pytest.fixture
def product_schema():
    """Pre-built schema for ProductPydantic."""
    return schema_for(ProductPydantic)()


@pytest.fixture
def query_args_schema():
    """Pre-built schema for QueryArgsPydantic."""
    return schema_for(QueryArgsPydantic)()


# =============================================================================
# Flask App Fixtures (conditional import)
# =============================================================================

try:
    from flask import Flask

    @pytest.fixture
    def flask_app():
        """Basic Flask app for testing."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        return app

    @pytest.fixture
    def flask_client(flask_app):
        """Flask test client."""
        return flask_app.test_client()

    @pytest.fixture
    def flask_app_context(flask_app):
        """Flask app context for tests that need it."""
        with flask_app.app_context():
            yield flask_app

    # Common aliases for backward compatibility with test files
    @pytest.fixture
    def app(flask_app):
        """Alias for flask_app fixture."""
        return flask_app

    @pytest.fixture
    def client(flask_client):
        """Alias for flask_client fixture."""
        return flask_client

except ImportError:
    # Flask not installed - skip these fixtures
    pass


# =============================================================================
# Schema Class Factories
# =============================================================================

@pytest.fixture
def user_schema_class():
    """Return the UserPydantic schema class (not instance)."""
    return schema_for(UserPydantic)


@pytest.fixture
def user_create_schema_class():
    """Return the UserCreatePydantic schema class."""
    return schema_for(UserCreatePydantic)


@pytest.fixture
def product_schema_class():
    """Return the ProductPydantic schema class."""
    return schema_for(ProductPydantic)


@pytest.fixture
def nested_user_schema_class():
    """Return the UserWithAddressPydantic schema class."""
    return schema_for(UserWithAddressPydantic)
