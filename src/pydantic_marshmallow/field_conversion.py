"""
Field conversion utilities for Pydantic to Marshmallow field mapping.

This module centralizes the conversion of Pydantic model fields to Marshmallow fields,
eliminating duplication between the metaclass, instance setup, and factory methods.
"""

from __future__ import annotations

from typing import Any, get_args, get_origin

from marshmallow import fields as ma_fields
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from .type_mapping import type_to_marshmallow_field


def convert_pydantic_field(
    field_name: str,
    field_info: Any,
) -> ma_fields.Field:
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

    # Handle Optional types → allow_none
    origin = get_origin(annotation)
    if origin is type(None) or (origin and type(None) in get_args(annotation)):
        ma_field.allow_none = True

    return ma_field


def convert_computed_field(
    field_name: str,
    computed_info: Any,
) -> ma_fields.Field:
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
) -> dict[str, ma_fields.Field]:
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
    fields: dict[str, ma_fields.Field] = {}
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
    if include_computed and hasattr(model, 'model_computed_fields'):
        for field_name, computed_info in model.model_computed_fields.items():
            if field_name in exclude_set:
                continue
            if include is not None and field_name not in include:
                continue

            fields[field_name] = convert_computed_field(field_name, computed_info)

    return fields
