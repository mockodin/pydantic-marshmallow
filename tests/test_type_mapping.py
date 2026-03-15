"""Tests for type_mapping module.

Covers:
- Thread-safe _processing_models (C1)
- Literal → OneOf validation (M1)
- Variable-length tuple type preservation (M2)
- IP type exact matching + hasattr guard (M3+M4)
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Literal
from unittest.mock import patch

import pytest
from marshmallow import fields as ma_fields, validate as ma_validate
from pydantic import BaseModel

from pydantic_marshmallow.bridge import PydanticSchema
from pydantic_marshmallow.type_mapping import (
    _processing_lock,
    _processing_models,
    type_to_marshmallow_field,
)

# ============================================================================
# C1: Thread-safe _processing_models
# ============================================================================


class SelfRefModel(BaseModel):
    name: str
    children: list[SelfRefModel] = []


class TestThreadSafeProcessingModels:
    """C1: _processing_models must be thread-safe."""

    def test_processing_set_uses_lock(self) -> None:
        """Verify the lock exists and is a threading.Lock."""
        assert isinstance(_processing_lock, type(threading.Lock()))

    def test_self_referential_model_no_infinite_recursion(self) -> None:
        """Recursion detection still works after adding locks."""
        field = type_to_marshmallow_field(SelfRefModel)
        assert isinstance(field, ma_fields.Nested)

    def test_processing_set_cleaned_up_after_success(self) -> None:
        """_processing_models is empty after successful conversion."""
        type_to_marshmallow_field(SelfRefModel)
        assert len(_processing_models) == 0

    def test_processing_set_cleaned_up_after_error(self) -> None:
        """_processing_models is cleaned up even when from_model raises."""

        class FailModel(BaseModel):
            x: int

        # Ensure clean state
        with _processing_lock:
            _processing_models.discard(FailModel)

        with (
            patch(
                "pydantic_marshmallow.bridge.PydanticSchema.from_model",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            type_to_marshmallow_field(FailModel)

        assert FailModel not in _processing_models

    def test_concurrent_schema_generation(self) -> None:
        """Multiple threads can generate schemas for different models safely."""

        class ModelA(BaseModel):
            a: str

        class ModelB(BaseModel):
            b: int

        results: dict[str, ma_fields.FieldABC] = {}
        errors: list[Exception] = []

        def convert(name: str, model: type) -> None:
            try:
                results[name] = type_to_marshmallow_field(model)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=convert, args=("a", ModelA))
        t2 = threading.Thread(target=convert, args=("b", ModelB))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        assert isinstance(results["a"], ma_fields.Nested)
        assert isinstance(results["b"], ma_fields.Nested)


# ============================================================================
# M1: Literal → OneOf validation
# ============================================================================


class TestLiteralOneOf:
    """M1: Literal types should produce Raw(validate=OneOf(...))."""

    @pytest.mark.parametrize(
        "literal_type,expected_choices",
        [
            (Literal["active"], {"active"}),
            (Literal["a", "b", "c"], {"a", "b", "c"}),
            (Literal[1, 2, 3], {1, 2, 3}),
        ],
        ids=["single_str", "multi_str", "int_values"],
    )
    def test_literal_produces_oneof(self, literal_type: type, expected_choices: set) -> None:
        """Literal types produce Raw field with OneOf validator."""
        field = type_to_marshmallow_field(literal_type)
        assert isinstance(field, ma_fields.Raw)
        oneof = next(v for v in field.validators if isinstance(v, ma_validate.OneOf))
        assert set(oneof.choices) == expected_choices

    def test_literal_in_model(self) -> None:
        """Literal field in a Pydantic model works end-to-end."""

        class StatusModel(BaseModel):
            status: Literal["active", "inactive"]

        schema_cls = PydanticSchema.from_model(StatusModel)
        schema = schema_cls()

        result = schema.load({"status": "active"})
        assert result.status == "active"


# ============================================================================
# M2: tuple[int, ...] preserves element type
# ============================================================================


class TestVariableLengthTuple:
    """M2: tuple[int, ...] should map to List(Integer()), not List(Raw())."""

    @pytest.mark.parametrize(
        "tuple_type,inner_field_type",
        [
            (tuple[int, ...], ma_fields.Integer),
            (tuple[str, ...], ma_fields.String),
        ],
        ids=["int_ellipsis", "str_ellipsis"],
    )
    def test_variable_length_preserves_type(self, tuple_type: type, inner_field_type: type) -> None:
        """Variable-length tuple maps to List with correct inner field type."""
        field = type_to_marshmallow_field(tuple_type)
        assert isinstance(field, ma_fields.List)
        assert isinstance(field.inner, inner_field_type)

    def test_fixed_length_tuple_unchanged(self) -> None:
        """tuple[int, str] still produces Tuple with specific fields."""
        field = type_to_marshmallow_field(tuple[int, str])
        assert isinstance(field, ma_fields.Tuple)

    def test_bare_tuple_unchanged(self) -> None:
        """tuple without args still produces List(Raw())."""
        field = type_to_marshmallow_field(tuple)
        # bare tuple hits TYPE_MAPPING or falls through
        assert isinstance(field, (ma_fields.List, ma_fields.Raw))


# ============================================================================
# M3 + M4: IP exact matching + hasattr guard
# ============================================================================


class TestIPTypeMatching:
    """M3+M4: IP matching uses exact names and guards hasattr(ma_fields, 'IP')."""

    def test_no_false_positive_on_substring(self) -> None:
        """Types with 'IP' as substring (ZIPCode, RecIPe) should NOT match."""
        fake_type = SimpleNamespace(__module__="pydantic.networks", __name__="ZIPCode")

        field = type_to_marshmallow_field(fake_type)
        # Should NOT be an IP field
        assert not isinstance(field, ma_fields.IP) if hasattr(ma_fields, "IP") else True

    @pytest.mark.parametrize("type_name", ["IPv4Address", "IPvAnyAddress"])
    def test_ip_type_maps_correctly(self, type_name: str) -> None:
        """Pydantic IP types map to IP field (or String fallback)."""
        fake_ip = SimpleNamespace(__module__="pydantic.networks", __name__=type_name)
        field = type_to_marshmallow_field(fake_ip)
        if hasattr(ma_fields, "IP"):
            assert isinstance(field, ma_fields.IP)
        else:
            assert isinstance(field, ma_fields.String)

    def test_hasattr_guard_fallback(self) -> None:
        """When ma_fields.IP doesn't exist, falls back to String."""
        fake_ipv6 = SimpleNamespace(__module__="pydantic.networks", __name__="IPv6Address")

        # Temporarily remove IP from ma_fields if it exists
        ip_attr = getattr(ma_fields, "IP", None)
        try:
            if ip_attr is not None:
                delattr(ma_fields, "IP")

            field = type_to_marshmallow_field(fake_ipv6)
            assert isinstance(field, ma_fields.String)
        finally:
            if ip_attr is not None:
                ma_fields.IP = ip_attr  # type: ignore[attr-defined]
