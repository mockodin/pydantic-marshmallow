"""
Field conversion utilities for Pydantic to Marshmallow field mapping.

This module centralizes the conversion of Pydantic model fields to Marshmallow fields,
eliminating duplication between the metaclass, instance setup, and factory methods.
"""

from __future__ import annotations

from types import UnionType
from typing import Any, Union, get_args, get_origin

from marshmallow import fields as ma_fields
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from .type_mapping import type_to_marshmallow_field


def _get_computed_fields(model_class: type[BaseModel]) -> dict[str, Any]:
    """Get computed fields dict from a Pydantic model class.

    Handles differences between Pydantic versions:
    - Pydantic 2.0.x: model_computed_fields is a property (only works on instances)
    - Pydantic 2.4+: model_computed_fields works directly on classes
    """
    # Try direct access first (works in newer Pydantic)
    result = getattr(model_class, 'model_computed_fields', None)
    if isinstance(result, dict):
        return result

    # For Pydantic 2.0.x: model_computed_fields is a property, call its getter
    if isinstance(result, property) and result.fget:
        prop_result = result.fget(model_class)
        if isinstance(prop_result, dict):
            return prop_result

    return {}


def convert_pydantic_field(
    field_name: str,
    field_info: Any,
) -> ma_fields.Field[Any]:
    """
    Convert a single Pydantic FieldInfo to a Marshmallow Field.

    Handles:
    - Type conversion via type_mapping
    - Required status (fields without defaults are required)
    - Default values (static and factory)
    - Field aliases (data_key)
    - Optional/None handling (allow_none)

    Args:
        field_name: Name of the field
        field_info: Pydantic FieldInfo object

    Returns:
        Configured Marshmallow field instance
    """
    annotation = field_info.annotation
    ma_field = type_to_marshmallow_field(annotation)

    # Apply default values and set required status
    if field_info.default is not PydanticUndefined:
        ma_field.load_default = field_info.default
        ma_field.dump_default = field_info.default
        ma_field.required = False
    elif field_info.default_factory is not None:
        ma_field.load_default = field_info.default_factory
        ma_field.required = False
    else:
        # No default - field is required
        ma_field.required = True

    # Handle alias → data_key
    if field_info.alias:
        ma_field.data_key = field_info.alias

    # Handle Optional types (X | None or Optional[X]) → allow_none
    origin = get_origin(annotation)
    args = get_args(annotation)
    is_union = origin is Union or origin is UnionType
    if origin is type(None) or (is_union and type(None) in args):
        ma_field.allow_none = True

    return ma_field


def convert_computed_field(
    field_name: str,
    computed_info: Any,
) -> ma_fields.Field[Any]:
    """
    Convert a Pydantic computed_field to a dump-only Marshmallow Field.

    Args:
        field_name: Name of the computed field
        computed_info: Pydantic ComputedFieldInfo object

    Returns:
        Dump-only Marshmallow field instance
    """
    return_type = getattr(computed_info, 'return_type', Any)
    ma_field = type_to_marshmallow_field(return_type)
    ma_field.dump_only = True
    return ma_field


def convert_model_fields(
    model: type[BaseModel],
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    include_computed: bool = True,
) -> dict[str, ma_fields.Field[Any]]:
    """
    Convert all fields from a Pydantic model to Marshmallow fields.

    This is the main entry point for field conversion, used by:
    - PydanticSchemaMeta.__new__()
    - PydanticSchema._setup_fields_from_model()
    - PydanticSchema.from_model()

    Args:
        model: Pydantic model class
        include: Optional whitelist of field names to include
        exclude: Optional blacklist of field names to exclude
        include_computed: Whether to include @computed_field properties

    Returns:
        Dict mapping field names to Marshmallow field instances
    """
    fields: dict[str, ma_fields.Field[Any]] = {}
    exclude_set = exclude or set()

    # Convert regular model fields
    for field_name, field_info in model.model_fields.items():
        # Apply filtering
        if field_name in exclude_set:
            continue
        if include is not None and field_name not in include:
            continue

        fields[field_name] = convert_pydantic_field(field_name, field_info)

    # Convert computed fields (dump-only)
    computed_fields = _get_computed_fields(model)
    if include_computed and computed_fields:
        for field_name, computed_info in computed_fields.items():
            if field_name in exclude_set:
                continue
            if include is not None and field_name not in include:
                continue

            fields[field_name] = convert_computed_field(field_name, computed_info)

    return fields
