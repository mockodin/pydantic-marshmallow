"""
Error handling utilities for the Marshmallow-Pydantic bridge.

This module provides:
- BridgeValidationError: Exception with valid_data tracking for partial success
- Error path building and formatting utilities for Pydantic→Marshmallow conversion
"""

from __future__ import annotations

from typing import Any

from marshmallow.exceptions import ValidationError as MarshmallowValidationError
from pydantic import BaseModel, ValidationError as PydanticValidationError
from pydantic_core import ErrorDetails


class BridgeValidationError(MarshmallowValidationError):
    """
    Validation error that bridges Marshmallow and Pydantic error formats.

    Extends Marshmallow's ValidationError to track partially valid data,
    enabling graceful handling of multi-field validation failures.

    Attributes:
        messages: Dict of field -> error messages (Marshmallow format)
        valid_data: Dict of successfully validated fields
        data: Original input data
    """

    def __init__(
        self,
        message: str | list[Any] | dict[str, Any],
        field_name: str = "_schema",
        data: Any | None = None,
        valid_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.data = data
        self.valid_data = valid_data or {}
        super().__init__(message, field_name, data, valid_data=valid_data or {}, **kwargs)


def build_error_path(loc: tuple[Any, ...]) -> str:
    """
    Build a dotted error path from Pydantic's location tuple.

    Converts Pydantic's error location format to Marshmallow's dotted path format.
    Handles collection indices like ("items", 0, "name") -> "items.0.name".

    Args:
        loc: Pydantic error location tuple (e.g., ('addresses', 0, 'zip_code'))

    Returns:
        Dotted path string (e.g., 'addresses.0.zip_code')
    """
    if len(loc) == 1:
        return str(loc[0])
    return ".".join(str(part) for part in loc)


def format_pydantic_error(
    error: ErrorDetails,
    model_class: type[BaseModel] | None = None,
) -> str:
    """
    Format a Pydantic error dict into a user-friendly message.

    Checks for custom error messages in field metadata when model_class is provided.

    Args:
        error: Pydantic ErrorDetails with 'msg', 'type', 'loc' keys
        model_class: Optional Pydantic model for custom message lookup

    Returns:
        Formatted error message string
    """
    msg: str = error.get("msg", "Validation error")
    error_type: str = error.get("type", "")
    loc = error.get("loc", ())

    # Check for custom error message in model field metadata
    if model_class and loc:
        field_name = str(loc[0])
        field_info = model_class.model_fields.get(field_name)
        if field_info and field_info.json_schema_extra:
            extra = field_info.json_schema_extra
            if isinstance(extra, dict):
                custom_messages = extra.get("error_messages")
                if isinstance(custom_messages, dict):
                    if error_type in custom_messages:
                        custom_msg = custom_messages[error_type]
                        if isinstance(custom_msg, str):
                            return custom_msg
                    if "default" in custom_messages:
                        default_msg = custom_messages["default"]
                        if isinstance(default_msg, str):
                            return default_msg

    return msg


def convert_pydantic_errors(
    pydantic_error: PydanticValidationError,
    model_class: type[BaseModel] | None = None,
    original_data: dict[str, Any] | None = None,
) -> BridgeValidationError:
    """
    Convert a Pydantic ValidationError to BridgeValidationError.

    Transforms Pydantic's error format to Marshmallow-compatible format,
    tracking which fields failed and which succeeded.

    Args:
        pydantic_error: The Pydantic ValidationError to convert
        model_class: The Pydantic model class (for custom messages)
        original_data: The original input data

    Returns:
        BridgeValidationError with Marshmallow-formatted messages and valid_data
    """
    errors: dict[str, Any] = {}
    failed_fields: set[str] = set()

    for error in pydantic_error.errors():
        loc = error.get("loc", ())
        msg = format_pydantic_error(error, model_class)

        if loc:
            field_path = build_error_path(loc)
            failed_fields.add(str(loc[0]))  # Track top-level field

            if field_path in errors:
                if isinstance(errors[field_path], list):
                    errors[field_path].append(msg)
                else:
                    errors[field_path] = [errors[field_path], msg]
            else:
                errors[field_path] = [msg]
        else:
            errors["_schema"] = [*errors.get("_schema", []), msg]

    # Build valid_data: fields that weren't in the error list
    valid_data: dict[str, Any] = {}
    if original_data and model_class:
        for field_name in original_data:
            if field_name not in failed_fields and field_name in model_class.model_fields:
                valid_data[field_name] = original_data[field_name]

    return BridgeValidationError(
        errors,
        data=original_data,
        valid_data=valid_data,
    )
