"""
Type mapping utilities for converting Python/Pydantic types to Marshmallow fields.

This module provides type-to-field conversions, leveraging Marshmallow's native
TYPE_MAPPING for basic types and adding support for generic collections.
"""
from enum import Enum as PyEnum
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from marshmallow import Schema, fields as ma_fields
from pydantic import BaseModel

# Track models being processed to detect recursion
_processing_models: set[type[Any]] = set()


def type_to_marshmallow_field(type_hint: Any) -> ma_fields.Field:
    """
    Map a Python type to a Marshmallow field instance.

    Uses Marshmallow's native TYPE_MAPPING for basic types (str, int, datetime, etc.)
    and adds support for:
    - Generic collections (list[T], dict[K, V], set[T], frozenset[T])
    - Optional types (T | None)
    - Union types (X | Y)
    - Tuple types
    - Nested Pydantic models
    - Enums
    - Literal types
    - Pydantic special types (EmailStr, AnyUrl, etc.)

    Args:
        type_hint: A Python type annotation

    Returns:
        An appropriate Marshmallow field instance
    """
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle NoneType
    if type_hint is type(None):
        return ma_fields.Raw(allow_none=True)

    # Handle Literal types
    if origin is Literal:
        # For single-value Literal, could be a constant
        if args and len(args) == 1:
            # Use Raw with validation - Pydantic will enforce the literal
            return ma_fields.Raw()
        return ma_fields.Raw()

    # Handle Union (including Optional) - supports both Union[X, Y] and X | Y syntax
    if origin is Union or origin is UnionType:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            field = type_to_marshmallow_field(non_none_args[0])
            field.allow_none = True
            return field
        return ma_fields.Raw(allow_none=True)

    # Handle Enum types
    if isinstance(type_hint, type) and issubclass(type_hint, PyEnum):
        return ma_fields.Enum(type_hint)

    # Handle nested Pydantic models - use Nested with a dynamically created schema
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        # Import here to avoid circular imports
        from pydantic_marshmallow.bridge import PydanticSchema

        # Check if we're already processing this model (recursion detection)
        # Use a module-level set to track models being processed
        if type_hint in _processing_models:
            # Self-referential model - use Raw to avoid infinite recursion
            # Pydantic will still handle the validation correctly
            return ma_fields.Raw()

        try:
            _processing_models.add(type_hint)
            # Create a nested schema class for this model
            nested_schema = PydanticSchema.from_model(type_hint)
            return ma_fields.Nested(nested_schema)
        finally:
            _processing_models.discard(type_hint)

    # Handle list[T]
    if origin is list:
        inner: ma_fields.Field = ma_fields.Raw()
        if args:
            inner = type_to_marshmallow_field(args[0])
        return ma_fields.List(inner)

    # Handle dict[K, V]
    if origin is dict:
        key_field: ma_fields.Field = ma_fields.String()
        value_field: ma_fields.Field = ma_fields.Raw()
        if args and len(args) >= 2:
            key_field = type_to_marshmallow_field(args[0])
            value_field = type_to_marshmallow_field(args[1])
        return ma_fields.Dict(keys=key_field, values=value_field)

    # Handle set[T] and frozenset[T] - convert to List in Marshmallow
    if origin in (set, frozenset):
        inner_set: ma_fields.Field = ma_fields.Raw()
        if args:
            inner_set = type_to_marshmallow_field(args[0])
        return ma_fields.List(inner_set)

    # Handle Tuple - use Marshmallow's Tuple field if available
    if origin is tuple:
        if args:
            # Fixed-length tuple with specific types
            tuple_fields = [type_to_marshmallow_field(arg) for arg in args if arg is not ...]
            if tuple_fields:
                return ma_fields.Tuple(tuple_fields=tuple(tuple_fields))
        return ma_fields.List(ma_fields.Raw())

    # Check for Pydantic special types by module
    type_module = getattr(type_hint, '__module__', '')
    type_name = getattr(type_hint, '__name__', str(type_hint))

    # Handle Pydantic networking types
    if 'pydantic' in type_module:
        if 'EmailStr' in type_name or type_name == 'EmailStr':
            return ma_fields.Email()
        url_types = ('Url', 'URL', 'HttpUrl', 'AnyUrl')
        if any(ut in type_name for ut in url_types):
            return ma_fields.URL()
        if 'IP' in type_name:
            # IP field exists in marshmallow but may not have type stubs
            return ma_fields.IP()  # type: ignore[no-untyped-call]

    # Use Marshmallow's native TYPE_MAPPING for basic types
    # This ensures we stay in sync with Marshmallow's type handling
    resolved = origin if origin else type_hint
    field_cls = Schema.TYPE_MAPPING.get(resolved, ma_fields.Raw)
    return field_cls()
