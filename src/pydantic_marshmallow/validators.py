"""
Custom validator decorators for PydanticSchema.

These provide backwards-compatible validators that work alongside Marshmallow's
native @validates and @validates_schema decorators. In most cases, users should
prefer Marshmallow's native decorators (from marshmallow import validates).

Note: These custom decorators are provided for scenarios where additional
functionality beyond Marshmallow's native validators is needed.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, cast, overload

F = TypeVar("F", bound="ValidatorFunc")


class ValidatorFunc(Protocol):
    """Protocol for validator functions with metadata attributes."""

    _validates_field: str
    _validates_schema: bool
    _pass_many: bool
    _skip_on_field_errors: bool

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the validator function."""
        ...


class FieldValidatorFunc(Protocol):
    """Protocol for field validator functions."""

    _validates_field: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the field validator."""
        ...


class SchemaValidatorFunc(Protocol):
    """Protocol for schema validator functions."""

    _validates_schema: bool
    _pass_many: bool
    _skip_on_field_errors: bool

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the schema validator."""
        ...


# Registry for custom validators (used for backwards compatibility)
_field_validators: dict[tuple[type[Any], str], list[FieldValidatorFunc]] = {}
_schema_validators: dict[type[Any], list[SchemaValidatorFunc]] = {}


def validates(field_name: str) -> ValidatesDecorator:
    """
    Decorator to register a field validator on a PydanticSchema.

    The decorated method receives the field value and should raise
    ValidationError if validation fails. Compatible with Marshmallow's
    @validates decorator.

    Note: In most cases, prefer `from marshmallow import validates` which
    works natively with PydanticSchema via Marshmallow's hook system.

    Example:
        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @validates("name")
            def validate_name(self, value):
                if value.lower() == "admin":
                    raise ValidationError("Cannot use 'admin' as name")
    """
    return ValidatesDecorator(field_name)


class ValidatesDecorator:
    """Decorator class for @validates that preserves function types."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name

    def __call__(self, fn: F) -> F:
        """Decorate a function as a field validator."""
        # Use object.__setattr__ to set attributes on the function
        object.__setattr__(fn, "_validates_field", self.field_name)
        return fn


@overload
def validates_schema(fn: F) -> F:
    ...


@overload
def validates_schema(
    fn: None = None,
    *,
    pass_many: bool = False,
    skip_on_field_errors: bool = True,
) -> ValidatesSchemaDecorator:
    ...


def validates_schema(
    fn: F | None = None,
    *,
    pass_many: bool = False,
    skip_on_field_errors: bool = True,
) -> F | ValidatesSchemaDecorator:
    """
    Decorator to register a schema-level validator on a PydanticSchema.

    The decorated method receives the full data dict and should raise
    ValidationError if validation fails. Compatible with Marshmallow's
    @validates_schema decorator.

    Note: In most cases, prefer `from marshmallow import validates_schema`
    which works natively with PydanticSchema via Marshmallow's hook system.

    Args:
        fn: The validator function (when used without parentheses)
        pass_many: Whether to pass the full collection when many=True
        skip_on_field_errors: Skip this validator if field errors exist

    Example:
        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

            @validates_schema
            def validate_user(self, data, **kwargs):
                if data.get("password") != data.get("confirm_password"):
                    raise ValidationError("Passwords must match", "_schema")
    """
    decorator = ValidatesSchemaDecorator(pass_many, skip_on_field_errors)
    if fn is not None:
        return decorator(fn)
    return decorator


class ValidatesSchemaDecorator:
    """Decorator class for @validates_schema that preserves function types."""

    def __init__(self, pass_many: bool, skip_on_field_errors: bool) -> None:
        self.pass_many = pass_many
        self.skip_on_field_errors = skip_on_field_errors

    def __call__(self, func: F) -> F:
        """Decorate a function as a schema validator."""
        object.__setattr__(func, "_validates_schema", True)
        object.__setattr__(func, "_pass_many", self.pass_many)
        object.__setattr__(func, "_skip_on_field_errors", self.skip_on_field_errors)
        return func


class SchemaWithValidatorCache(Protocol):
    """Protocol for schema classes that have validator caches."""

    _field_validators_cache: dict[str, list[str]]
    _schema_validators_cache: list[str]


def cache_validators(cls: type[Any]) -> None:
    """
    Cache custom validators at class creation time.

    Scans the class for methods decorated with @validates and @validates_schema
    and caches them for efficient lookup during validation.

    Args:
        cls: The schema class to cache validators for (must have validator cache attrs)
    """
    # Set cache attributes on the class
    field_cache: dict[str, list[str]] = {}
    schema_cache: list[str] = []

    for attr_name in dir(cls):
        if attr_name.startswith('_'):
            continue
        try:
            attr = getattr(cls, attr_name, None)
        except AttributeError:
            continue

        if callable(attr):
            if hasattr(attr, "_validates_field"):
                # Cast to protocol type since hasattr confirmed the attribute exists
                field_validator = cast(FieldValidatorFunc, attr)
                field: str = field_validator._validates_field
                if field not in field_cache:
                    field_cache[field] = []
                field_cache[field].append(attr_name)
            elif hasattr(attr, "_validates_schema"):
                schema_cache.append(attr_name)

    # Assign to class - cast to type that has the cache attributes
    # PydanticSchema defines these as ClassVar, so they exist at runtime
    schema_cls = cast(type[SchemaWithValidatorCache], cls)
    schema_cls._field_validators_cache = field_cache
    schema_cls._schema_validators_cache = schema_cache
