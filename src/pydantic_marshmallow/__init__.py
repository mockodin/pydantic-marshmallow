"""
pydantic-marshmallow: Bridge Pydantic's power with Marshmallow's ecosystem.

This package provides seamless integration between Pydantic models and Marshmallow
schemas, enabling you to use Pydantic's powerful validation while maintaining
compatibility with the Marshmallow ecosystem (Flask-Marshmallow, webargs, apispec, etc.).

Core Components:
    PydanticSchema: A Marshmallow schema backed by a Pydantic model
    HybridModel: A Pydantic model with built-in Marshmallow support
    schema_for: Factory function to create schemas from models
    pydantic_schema: Decorator to add .Schema attribute to models
    BridgeValidationError: Exception with valid_data tracking

Basic Usage:
    >>> from pydantic import BaseModel, EmailStr
    >>> from pydantic_marshmallow import PydanticSchema
    >>>
    >>> class User(BaseModel):
    ...     name: str
    ...     email: EmailStr
    >>>
    >>> class UserSchema(PydanticSchema[User]):
    ...     class Meta:
    ...         model = User
    >>>
    >>> schema = UserSchema()
    >>> user = schema.load({"name": "Alice", "email": "alice@example.com"})
    >>> print(user.name)  # "Alice" - it's a Pydantic User instance!

With Decorator:
    >>> from pydantic_marshmallow import pydantic_schema
    >>>
    >>> @pydantic_schema
    ... class User(BaseModel):
    ...     name: str
    ...     email: EmailStr
    >>>
    >>> user = User.Schema().load({"name": "Alice", "email": "alice@example.com"})

Features:
    - Full Pydantic validation, coercion, and error messages
    - Marshmallow hooks: @pre_load, @post_load, @pre_dump, @post_dump
    - Marshmallow validators: @validates, @validates_schema
    - Partial loading: partial=True or partial=('field1', 'field2')
    - Unknown field handling: unknown=RAISE/EXCLUDE/INCLUDE
    - Field filtering: only=, exclude=, load_only=, dump_only=
    - Pydantic @computed_field support in dumps
    - Works with Flask-Marshmallow, webargs, apispec, and more
"""

# Re-export Marshmallow's validators - these work with PydanticSchema
# Also export hooks for convenience
from marshmallow import EXCLUDE, INCLUDE, RAISE, post_dump, post_load, pre_dump, pre_load, validates, validates_schema

from .bridge import HybridModel, PydanticSchema, pydantic_schema, schema_for
from .errors import BridgeValidationError

# Note: We re-export Marshmallow's @validates and @validates_schema above.
# Our bridge's _do_load calls Marshmallow's native validator system,
# so `from marshmallow import validates` works correctly with PydanticSchema.

# Version is managed by setuptools-scm from git tags
from importlib.metadata import version as _version

__version__ = _version("pydantic-marshmallow")
__all__ = [
    "EXCLUDE",
    "INCLUDE",
    "RAISE",
    "BridgeValidationError",
    "HybridModel",
    "PydanticSchema",
    "post_dump",
    "post_load",
    "pre_dump",
    "pre_load",
    "pydantic_schema",
    "schema_for",
    "validates",
    "validates_schema",
]
