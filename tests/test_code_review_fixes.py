"""Tests for code review audit fixes (Critical, High, Medium)."""

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
from pydantic_marshmallow.validators import cache_validators, validates, validates_schema

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
# H5: Cache stampede double-check in from_model()
# ============================================================================


class TestCacheStampede:
    """H5: from_model() should double-check cache after acquiring lock."""

    def test_from_model_returns_cached_on_second_call(self) -> None:
        """Calling from_model twice returns the same class (cached)."""

        class CacheTestModel(BaseModel):
            x: int

        schema1 = PydanticSchema.from_model(CacheTestModel)
        schema2 = PydanticSchema.from_model(CacheTestModel)
        assert schema1 is schema2

    def test_concurrent_from_model_same_class(self) -> None:
        """Two threads calling from_model for same model get same class."""

        class ConcurrentModel(BaseModel):
            val: str

        results: list[type] = []
        errors: list[Exception] = []

        def create_schema() -> None:
            try:
                results.append(PydanticSchema.from_model(ConcurrentModel))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_schema) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 4
        # All threads should get the same cached class
        assert all(r is results[0] for r in results)


# ============================================================================
# M1: Literal → OneOf validation
# ============================================================================


class TestLiteralOneOf:
    """M1: Literal types should produce Raw(validate=OneOf(...))."""

    def test_literal_single_value(self) -> None:
        """Single-value Literal gets OneOf with one allowed value."""
        field = type_to_marshmallow_field(Literal["active"])
        assert isinstance(field, ma_fields.Raw)
        assert any(isinstance(v, ma_validate.OneOf) for v in field.validators)
        oneof = next(v for v in field.validators if isinstance(v, ma_validate.OneOf))
        assert set(oneof.choices) == {"active"}

    def test_literal_multi_value(self) -> None:
        """Multi-value Literal gets OneOf with all allowed values."""
        field = type_to_marshmallow_field(Literal["a", "b", "c"])
        oneof = next(v for v in field.validators if isinstance(v, ma_validate.OneOf))
        assert set(oneof.choices) == {"a", "b", "c"}

    def test_literal_int_values(self) -> None:
        """Literal with int values gets correct OneOf."""
        field = type_to_marshmallow_field(Literal[1, 2, 3])
        oneof = next(v for v in field.validators if isinstance(v, ma_validate.OneOf))
        assert set(oneof.choices) == {1, 2, 3}

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

    def test_variable_length_tuple_preserves_type(self) -> None:
        """tuple[int, ...] → List with Integer inner field."""
        field = type_to_marshmallow_field(tuple[int, ...])
        assert isinstance(field, ma_fields.List)
        assert isinstance(field.inner, ma_fields.Integer)

    def test_variable_length_tuple_str(self) -> None:
        """tuple[str, ...] → List with String inner field."""
        field = type_to_marshmallow_field(tuple[str, ...])
        assert isinstance(field, ma_fields.List)
        assert isinstance(field.inner, ma_fields.String)

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

    def test_ipv4_address_matches(self) -> None:
        """Pydantic IPv4Address type maps to IP or String field."""
        fake_ipv4 = SimpleNamespace(__module__="pydantic.networks", __name__="IPv4Address")

        field = type_to_marshmallow_field(fake_ipv4)
        if hasattr(ma_fields, "IP"):
            assert isinstance(field, ma_fields.IP)
        else:
            assert isinstance(field, ma_fields.String)

    def test_ipvanyaddress_matches(self) -> None:
        """Pydantic IPvAnyAddress type maps correctly."""
        fake_ipvany = SimpleNamespace(__module__="pydantic.networks", __name__="IPvAnyAddress")

        field = type_to_marshmallow_field(fake_ipvany)
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


# ============================================================================
# M6: Dual-decorated validators (elif → if)
# ============================================================================


class TestDualDecoratedValidators:
    """M6: A function decorated with both @validates and @validates_schema should be cached for both."""

    def test_dual_decorated_function(self) -> None:
        """Function with both _validates_field and _validates_schema is in both caches."""

        class DualSchema:
            _field_validators_cache: dict[str, list[str]] = {}
            _schema_validators_cache: list[str] = []

            @validates("name")
            @validates_schema
            def check_name(self, value: str, **kwargs: object) -> None:
                pass

        cache_validators(DualSchema)

        assert "name" in DualSchema._field_validators_cache
        assert "check_name" in DualSchema._field_validators_cache["name"]
        assert "check_name" in DualSchema._schema_validators_cache

    def test_field_only_decorator(self) -> None:
        """Function with only @validates is only in field cache."""

        class FieldOnlySchema:
            _field_validators_cache: dict[str, list[str]] = {}
            _schema_validators_cache: list[str] = []

            @validates("email")
            def check_email(self, value: str) -> None:
                pass

        cache_validators(FieldOnlySchema)

        assert "email" in FieldOnlySchema._field_validators_cache
        assert "check_email" not in FieldOnlySchema._schema_validators_cache

    def test_schema_only_decorator(self) -> None:
        """Function with only @validates_schema is only in schema cache."""

        class SchemaOnlySchema:
            _field_validators_cache: dict[str, list[str]] = {}
            _schema_validators_cache: list[str] = []

            @validates_schema
            def check_all(self, data: dict, **kwargs: object) -> None:
                pass

        cache_validators(SchemaOnlySchema)

        assert SchemaOnlySchema._field_validators_cache == {}
        assert "check_all" in SchemaOnlySchema._schema_validators_cache

