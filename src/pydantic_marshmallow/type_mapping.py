"""
Type mapping utilities for converting Python/Pydantic types to Marshmallow fields.

This module provides type-to-field conversions, leveraging Marshmallow's native
TYPE_MAPPING for basic types and adding support for generic collections.
"""

from __future__ import annotations

import threading
from enum import Enum as PyEnum
from functools import lru_cache
from types import UnionType
from typing import Any, Literal, Union, cast, get_args, get_origin

from marshmallow import Schema, fields as ma_fields
from marshmallow.validate import OneOf
from pydantic import BaseModel

# Track models being processed to detect recursion
# Protected by _processing_lock for thread safety (supports free-threaded Python 3.14+)
_processing_lock = threading.Lock()
_processing_models: set[type[Any]] = set()


# Cache for simple type -> field class lookups (str, int, datetime, etc.)
# These are the most common types and benefit most from caching.
# maxsize=512 handles large codebases with ~80KB memory overhead.
@lru_cache(maxsize=512)
def _get_simple_field_class(type_hint: type) -> type[Any]:
    """
    Cached lookup for simple, hashable types in Marshmallow's TYPE_MAPPING.

    This avoids repeated dict lookups and isinstance checks for common types
    like str, int, float, bool, datetime, etc.
    """
    return Schema.TYPE_MAPPING.get(type_hint, ma_fields.Raw)


def type_to_marshmallow_field(type_hint: Any) -> Any:
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
    # FAST PATH: Simple types (str, int, float, bool, datetime, etc.)
    # Check TYPE_MAPPING first to skip all the isinstance/origin checks.
    # This handles ~60-80% of fields in typical models, but we must not
    # short-circuit for Enums or Pydantic models, which have specialized handling.
    if (
        isinstance(type_hint, type)
        and type_hint in Schema.TYPE_MAPPING
        and not issubclass(type_hint, (PyEnum, BaseModel))
    ):
        # Cast needed for mypy: type_hint is confirmed to be a type at this point
        return _get_simple_field_class(cast(type, type_hint))()

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle NoneType
    if type_hint is type(None):
        return ma_fields.Raw(allow_none=True)

    # Handle Literal types — add OneOf so ecosystem tools (apispec, flask-smorest)
    # can infer enum constraints for OpenAPI generation
    if origin is Literal:
        if args:
            return ma_fields.Raw(validate=OneOf(args))
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
    # Use try-except because some type hints pass isinstance(x, type) but fail issubclass()
    try:
        if isinstance(type_hint, type) and issubclass(type_hint, PyEnum):
            return ma_fields.Enum(type_hint)
    except TypeError:
        pass  # Not a valid class for issubclass check

    # Handle nested Pydantic models - use Nested with a dynamically created schema
    # On Python 3.10, types.GenericAlias (e.g. list[str]) passes isinstance(x, type)
    # but fails issubclass(). Filter these out — they have an origin and are handled above.
    if isinstance(type_hint, type) and origin is None and issubclass(type_hint, BaseModel):
        # Import here to avoid circular imports
        from pydantic_marshmallow.bridge import PydanticSchema

        # Check if we're already processing this model (recursion detection)
        # Thread-safe: lock protects check+add, released before expensive work
        with _processing_lock:
            if type_hint in _processing_models:
                return ma_fields.Raw()
            _processing_models.add(type_hint)

        try:
            nested_schema = PydanticSchema.from_model(type_hint)
            return ma_fields.Nested(nested_schema)
        finally:
            with _processing_lock:
                _processing_models.discard(type_hint)

    # Handle list[T]
    if origin is list:
        inner = ma_fields.Raw()
        if args:
            inner = type_to_marshmallow_field(args[0])
        return ma_fields.List(inner)

    # Handle dict[K, V]
    if origin is dict:
        key_field = ma_fields.String()
        value_field = ma_fields.Raw()
        if args and len(args) >= 2:
            key_field = type_to_marshmallow_field(args[0])
            value_field = type_to_marshmallow_field(args[1])
        return ma_fields.Dict(keys=key_field, values=value_field)

    # Handle set[T] and frozenset[T] - convert to List in Marshmallow
    if origin in (set, frozenset):
        inner_set = ma_fields.Raw()
        if args:
            inner_set = type_to_marshmallow_field(args[0])
        return ma_fields.List(inner_set)

    # Handle Tuple - use Marshmallow's Tuple field if available
    if origin is tuple:
        if args:
            # Variable-length tuple: tuple[int, ...] → List(Integer())
            if len(args) == 2 and args[1] is Ellipsis:
                return ma_fields.List(type_to_marshmallow_field(args[0]))
            # Fixed-length tuple with specific types
            tuple_fields = [type_to_marshmallow_field(arg) for arg in args if arg is not ...]
            if tuple_fields:
                return ma_fields.Tuple(tuple_fields=tuple(tuple_fields))  # type: ignore[no-untyped-call,unused-ignore]
        return ma_fields.List(ma_fields.Raw())

    # Check for Pydantic special types by module
    type_module = getattr(type_hint, '__module__', '')
    type_name = getattr(type_hint, '__name__', str(type_hint))

    # Handle Pydantic networking types
    if 'pydantic' in type_module:
        if 'EmailStr' in type_name:
            return ma_fields.Email()
        url_types = ('Url', 'URL', 'HttpUrl', 'AnyUrl')
        if any(ut in type_name for ut in url_types):
            return ma_fields.URL()
        # Use exact name matching to avoid false positives (e.g. "ZIPCode", "RecIPe")
        ip_types = (
            'IPvAnyAddress', 'IPvAnyInterface', 'IPvAnyNetwork',
            'IPv4Address', 'IPv6Address', 'IPv4Interface', 'IPv6Interface',
            'IPv4Network', 'IPv6Network',
        )
        if type_name in ip_types:
            if hasattr(ma_fields, 'IP'):
                return ma_fields.IP()  # type: ignore[no-untyped-call,unused-ignore]
            return ma_fields.String()

    # Use Marshmallow's native TYPE_MAPPING for basic types
    # This ensures we stay in sync with Marshmallow's type handling
    resolved = origin if origin else type_hint
    if isinstance(resolved, type):
        return _get_simple_field_class(resolved)()
    return ma_fields.Raw()
