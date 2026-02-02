"""
Bridge between Pydantic models and Marshmallow schemas.

Pydantic's Rust-based validation with full Marshmallow compatibility.
Flow: Input → Marshmallow pre_load → PYDANTIC VALIDATES → Marshmallow post_load → Output
"""

from __future__ import annotations

from collections.abc import Callable, Sequence, Set as AbstractSet
from typing import Any, ClassVar, Generic, TypeVar, cast, get_args, get_origin

from marshmallow import EXCLUDE, INCLUDE, RAISE, Schema, fields as ma_fields
from marshmallow.decorators import VALIDATES, VALIDATES_SCHEMA
from marshmallow.error_store import ErrorStore
from marshmallow.exceptions import ValidationError as MarshmallowValidationError
from marshmallow.schema import SchemaMeta
from marshmallow.utils import missing as ma_missing
from pydantic import BaseModel, ConfigDict, ValidationError as PydanticValidationError

from .errors import BridgeValidationError, convert_pydantic_errors, format_pydantic_error
from .field_conversion import convert_model_fields, convert_pydantic_field
from .validators import cache_validators

M = TypeVar("M", bound=BaseModel)

# Module-level cache for HybridModel schemas
_hybrid_schema_cache: dict[type[Any], type[PydanticSchema[Any]]] = {}

# Cache for schema_for/from_model - key is (model, frozen options)
# This avoids recreating schema classes for the same model+options
_schema_class_cache: dict[tuple[type[Any], tuple[tuple[str, Any], ...]], type[Any]] = {}

# Field validator registry: maps (schema_class, field_name) -> list of validator functions
_field_validators: dict[tuple[type[Any], str], list[Callable[..., Any]]] = {}
_schema_validators: dict[type[Any], list[Callable[..., Any]]] = {}

# PERFORMANCE: Cache model field names (with aliases) per model class
# This avoids repeated set() construction and iteration in the hot path
_model_field_names_cache: dict[type[BaseModel], frozenset[str]] = {}


def _get_model_field_names_with_aliases(model_class: type[BaseModel]) -> frozenset[str]:
    """
    Get cached frozenset of model field names including aliases.

    This caches the result per model class to avoid repeated computation
    in the load() hot path.
    """
    cached = _model_field_names_cache.get(model_class)
    if cached is not None:
        return cached

    field_names = set(model_class.model_fields.keys())
    for field_info in model_class.model_fields.values():
        if field_info.alias:
            field_names.add(field_info.alias)

    result = frozenset(field_names)
    _model_field_names_cache[model_class] = result
    return result


class PydanticSchemaMeta(SchemaMeta):
    """
    Custom metaclass that adds Pydantic model fields BEFORE Marshmallow processes them.

    This ensures Meta.fields and Meta.exclude work correctly with dynamically
    generated fields from Pydantic models.

    The metaclass handles:
    - Extracting the Pydantic model from Meta.model or generic parameters
    - Converting Pydantic model fields to Marshmallow fields at class creation
    - Respecting Meta.fields (whitelist) filtering during field generation
    - Converting @computed_field properties to dump-only Marshmallow fields

    Note:
        Meta.exclude is NOT applied here - it's handled by Marshmallow's standard
        metaclass after all fields are declared. This ensures proper inheritance
        behavior.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
    ) -> PydanticSchemaMeta:
        # Get model class from Meta or generic parameter
        model_class = None

        # Check Meta.model
        meta = attrs.get("Meta")
        if meta and hasattr(meta, "model") and meta.model:
            model_class = meta.model

        # Check generic parameter from bases
        if not model_class:
            for base in bases:
                if hasattr(base, "__orig_bases__"):
                    for orig_base in base.__orig_bases__:
                        origin = get_origin(orig_base)
                        is_pydantic_schema = (
                            origin
                            and hasattr(origin, "__name__")
                            and "PydanticSchema" in origin.__name__
                        )
                        if is_pydantic_schema:
                            args = get_args(orig_base)
                            is_model_subclass = (
                                args
                                and isinstance(args[0], type)
                                and issubclass(args[0], BaseModel)
                            )
                            if is_model_subclass:
                                model_class = args[0]
                                break
                # Direct generic base
                origin = get_origin(base)
                is_pydantic_schema = (
                    origin
                    and hasattr(origin, "__name__")
                    and "PydanticSchema" in origin.__name__
                )
                if is_pydantic_schema:
                    args = get_args(base)
                    if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                        model_class = args[0]
                        break

        # Add Pydantic fields to attrs BEFORE Marshmallow processes them
        if model_class:
            # Check if attrs already has pre-filtered fields (from from_model())
            # If so, don't add more - the fields were intentionally filtered
            existing_fields = [
                k for k, v in attrs.items() if isinstance(v, ma_fields.Field)
            ]
            has_prefiltered_fields = len(existing_fields) > 0

            # Get Meta.fields (whitelist) - only this filters out fields
            # Meta.exclude is handled by Marshmallow after fields are declared
            meta_fields = getattr(meta, 'fields', None) if meta else None
            include_set = set(meta_fields) if meta_fields else None

            for field_name, field_info in model_class.model_fields.items():
                # Skip if already declared in attrs
                if field_name in attrs:
                    continue

                # If attrs has pre-filtered fields (from from_model), don't add more
                if has_prefiltered_fields:
                    continue

                # Apply Meta.fields whitelist only
                # Note: Meta.exclude is handled by Marshmallow after ALL fields are added
                if include_set is not None and field_name not in include_set:
                    continue

                # Use centralized field conversion
                attrs[field_name] = convert_pydantic_field(field_name, field_info)

            # Add computed fields as dump_only
            if hasattr(model_class, 'model_computed_fields'):
                from .field_conversion import convert_computed_field

                for field_name, computed_info in model_class.model_computed_fields.items():
                    if field_name in attrs:
                        continue
                    # If attrs has pre-filtered fields, don't add computed fields
                    if has_prefiltered_fields:
                        continue
                    # Apply Meta.fields whitelist
                    if include_set is not None and field_name not in include_set:
                        continue

                    attrs[field_name] = convert_computed_field(field_name, computed_info)

        # Cast to satisfy type checker - SchemaMeta.__new__ returns SchemaMeta
        return cast(PydanticSchemaMeta, super().__new__(mcs, name, bases, attrs))


class PydanticSchema(Schema, Generic[M], metaclass=PydanticSchemaMeta):
    """
    A Marshmallow schema backed by a Pydantic model.

    This gives you:
    - Pydantic's validation, coercion, and error messages
    - Marshmallow's serialization and ecosystem integration
    - No drift - Pydantic does the heavy lifting

    Example:
        from pydantic import BaseModel, EmailStr, Field

        class User(BaseModel):
            name: str = Field(min_length=1)
            email: EmailStr
            age: int = Field(ge=0)

        class UserSchema(PydanticSchema[User]):
            class Meta:
                model = User

        # Or use the shortcut:
        UserSchema = PydanticSchema.from_model(User)

        # Now use like any Marshmallow schema
        schema = UserSchema()
        user = schema.load({"name": "Alice", "email": "alice@example.com", "age": 30})
        # user is a User instance!

    Supports:
        - `partial=True` or `partial=('field1', 'field2')` for partial loading
        - `unknown=EXCLUDE` or `unknown=INCLUDE` for unknown field handling
        - `only=('field1',)` and `exclude=('field2',)` for field filtering
        - `load_only=('field',)` and `dump_only=('field',)` for directional fields
        - `@validates("field")` decorator for field validators
        - `@validates_schema` decorator for schema validators
        - `validate(data)` method that returns errors dict without raising
    """

    # Validator caches - populated at class creation, not every load()
    _field_validators_cache: ClassVar[dict[str, list[str]]] = {}
    _schema_validators_cache: ClassVar[list[str]] = []

    class Meta:
        model: type[BaseModel] | None = None
        unknown = RAISE  # Match Pydantic's default strict behavior

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Cache validators when the schema class is defined.

        Field setup is now handled by PydanticSchemaMeta to ensure fields
        are visible to Marshmallow BEFORE it processes Meta.fields/exclude.
        """
        super().__init_subclass__(**kwargs)

        # Cache validators at class creation (PERFORMANCE OPTIMIZATION)
        cache_validators(cls)

    def __init__(
        self,
        *,
        only: Sequence[str] | None = None,
        exclude: Sequence[str] = (),
        context: dict[str, Any] | None = None,
        load_only: Sequence[str] = (),
        dump_only: Sequence[str] = (),
        partial: bool | Sequence[str] | AbstractSet[str] | None = None,
        unknown: str | None = None,
        many: bool | None = None,
        **kwargs: Any,
    ) -> None:
        # Store filtering options BEFORE calling super().__init__
        self._only_fields: set[str] | None = set(only) if only else None
        self._exclude_fields: set[str] = set(exclude) if exclude else set()
        self._load_only_fields: set[str] = set(load_only) if load_only else set()
        self._dump_only_fields: set[str] = set(dump_only) if dump_only else set()
        self._partial: bool | Sequence[str] | AbstractSet[str] | None = partial
        self._unknown_override: str | None = unknown
        self._context = context or {}

        # Pass all known kwargs to parent including context
        super().__init__(
            only=only,
            exclude=exclude,
            context=context,
            many=many,
            load_only=load_only,
            dump_only=dump_only,
            partial=partial,
            unknown=unknown,
            **kwargs,
        )
        self._model_class = self._get_model_class()
        if self._model_class:
            self._setup_fields_from_model()

        # Call on_bind_field for each field
        for field_name, field_obj in self.fields.items():
            self.on_bind_field(field_name, field_obj)

    def on_bind_field(self, field_name: str, field_obj: ma_fields.Field) -> None:
        """
        Hook called when a field is bound to the schema.

        Override this to customize field binding behavior. This is called
        for each field after schema initialization, compatible with
        Marshmallow's on_bind_field hook.

        Example:
            class MySchema(PydanticSchema[MyModel]):
                class Meta:
                    model = MyModel

                def on_bind_field(self, field_name, field_obj):
                    # Make all fields allow None
                    field_obj.allow_none = True
                    super().on_bind_field(field_name, field_obj)
        """
        # Default implementation does nothing

    def handle_error(
        self,
        error: MarshmallowValidationError,
        data: Any,
        *,
        many: bool,
        **kwargs: Any,
    ) -> None:
        """
        Custom error handler hook, compatible with Marshmallow.

        Override this method to customize error handling behavior.
        Called when validation errors occur during load/dump.

        By default, re-raises the error. Override to log, transform,
        or suppress errors.

        Example:
            class MySchema(PydanticSchema[MyModel]):
                class Meta:
                    model = MyModel

                def handle_error(self, error, data, *, many, **kwargs):
                    # Log the error
                    logger.error(f"Validation failed: {error.messages}")
                    # Re-raise (required to propagate the error)
                    raise error
        """
        raise error

    @property
    def context(self) -> dict[str, Any]:
        """Get the validation context."""
        return self._context

    @context.setter
    def context(self, value: dict[str, Any]) -> None:
        """Set the validation context."""
        self._context = value

    def _get_model_class(self) -> type[BaseModel] | None:
        """Get the Pydantic model class from Meta or generic parameter."""
        # Try Meta.model first
        if hasattr(self, "Meta") and hasattr(self.Meta, "model") and self.Meta.model:
            return self.Meta.model

        # Try to get from generic parameter
        self_type = type(self)
        orig_bases = getattr(self_type, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            if origin is PydanticSchema:
                args = get_args(base)
                if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                    return args[0]

        return None

    def _setup_fields_from_model(self) -> None:
        """
        Set up Marshmallow fields from Pydantic model for serialization.

        NOTE: For schemas created via from_model/schema_for, fields are already
        set up in the class dict. This method only adds fields that are missing
        and does NOT override load_fields/dump_fields which Marshmallow's __init__
        has already filtered based on only/exclude/load_only/dump_only.

        Also respects Meta.fields (whitelist) and Meta.exclude (blacklist).
        If declared_fields is not empty, we use it as the source of truth for
        which fields should exist (i.e., fields were filtered at class creation).
        """
        if not self._model_class:
            return

        # Get Meta.fields and Meta.exclude for filtering
        meta_fields = getattr(self.Meta, 'fields', None) if hasattr(self, 'Meta') else None
        meta_exclude = getattr(self.Meta, 'exclude', None) if hasattr(self, 'Meta') else None

        # Combine filtering: respect both only= param and Meta.fields
        allowed_fields: set[str] | None = None
        if self._only_fields is not None:
            allowed_fields = self._only_fields
        elif meta_fields is not None:
            allowed_fields = set(meta_fields)
        elif self.declared_fields:
            # If declared_fields is set (e.g., from from_model()), use it as whitelist
            # This means fields were already filtered at class creation time
            allowed_fields = set(self.declared_fields.keys())

        # Combine exclusion: respect both exclude= param and Meta.exclude
        excluded_fields = set(self._exclude_fields)
        if meta_exclude:
            excluded_fields.update(meta_exclude)

        for field_name, field_info in self._model_class.model_fields.items():
            # Skip if field is excluded
            if field_name in excluded_fields:
                continue
            # Skip if whitelist is set and field not in it
            if allowed_fields is not None and field_name not in allowed_fields:
                continue

            # Only add to self.fields if not already present
            # Do NOT touch load_fields/dump_fields - Marshmallow manages those
            if field_name not in self.fields:
                # Use centralized field conversion
                ma_field = convert_pydantic_field(field_name, field_info)
                self.fields[field_name] = ma_field
                # Only add to load_fields/dump_fields if filter allows
                if field_name not in self._dump_only_fields:
                    self.load_fields[field_name] = ma_field
                if field_name not in self._load_only_fields:
                    self.dump_fields[field_name] = ma_field

    def _validate_with_pydantic(
        self,
        data: dict[str, Any],
        partial: bool | Sequence[str] | AbstractSet[str] | None = None,
        original_data: Any | None = None,
        skip_model_dump: bool = False,
    ) -> tuple[dict[str, Any], M | None]:
        """
        Use Pydantic to validate and coerce the input data.

        Filters out marshmallow.missing sentinel values before Pydantic validation,
        allowing Pydantic to use its own defaults for missing fields.

        Args:
            data: Input data to validate
            partial: Partial validation mode
            original_data: Original input data for error reporting
            skip_model_dump: If True and not partial, skip model_dump() and return
                           empty dict. Use when validators don't need the dict.

        Returns:
            Tuple of (validated_data_dict, model_instance)
            The instance is returned to avoid redundant validation later.
        """
        if not self._model_class:
            return data, None

        # Filter out marshmallow.missing values - Pydantic should use its defaults
        clean_data = {
            k: v for k, v in data.items()
            if v is not ma_missing
        }

        try:
            # Handle partial loading - temporarily make fields optional
            if partial:
                # Create a partial model dynamically
                validated_data = self._validate_partial(clean_data, partial, original_data)
                return validated_data, None  # Partial returns dict, no instance
            else:
                # Let Pydantic do all the validation - KEEP THE INSTANCE
                instance = self._model_class.model_validate(clean_data)
                # OPTIMIZATION: Skip model_dump if not needed for validators
                if skip_model_dump:
                    return {}, cast(M, instance)
                # Return both the dict (for validators) and instance (for result)
                validated_data = instance.model_dump(by_alias=False)
                # Cast to M since model_validate returns the correct model type
                return validated_data, cast(M, instance)
        except PydanticValidationError as e:
            # Use centralized error conversion
            raise convert_pydantic_errors(e, self._model_class, original_data or data) from e

    def _validate_partial(
        self,
        data: dict[str, Any],
        partial: bool | Sequence[str] | AbstractSet[str],
        original_data: Any | None = None,
    ) -> dict[str, Any]:
        """Validate data with partial loading - missing required fields allowed."""
        if not self._model_class:
            return data

        # If partial is True, all fields are optional
        # If partial is a tuple/list, only those fields are optional
        partial_fields: set[str] = set()
        if partial is True:
            partial_fields = set(self._model_class.model_fields.keys())
        elif isinstance(partial, (list, tuple)):
            partial_fields = set(partial)

        # Check for required but missing fields (not in partial list)
        errors: dict[str, Any] = {}
        for field_name, field_info in self._model_class.model_fields.items():
            if field_name not in data and field_name not in partial_fields:
                # Check if field has a default
                from pydantic_core import PydanticUndefined
                if field_info.default is PydanticUndefined and field_info.default_factory is None:
                    errors[field_name] = ["Missing data for required field."]

        if errors:
            # Include valid_data even on partial validation errors
            valid_data = {
                k: v for k, v in data.items()
                if k not in errors and k in self._model_class.model_fields
            }
            raise BridgeValidationError(
                errors,
                data=original_data or data,
                valid_data=valid_data,
            )

        # For validation, we need to provide defaults for missing fields
        # Create a data dict with defaults for unprovided fields
        validation_data = {}
        for field_name, field_info in self._model_class.model_fields.items():
            if field_name in data:
                validation_data[field_name] = data[field_name]
            else:
                # Use default if available
                from pydantic_core import PydanticUndefined
                if field_info.default is not PydanticUndefined:
                    validation_data[field_name] = field_info.default
                elif field_info.default_factory is not None:
                    # Cast to satisfy type checker - Pydantic's factory takes no args
                    factory = cast(Callable[[], Any], field_info.default_factory)
                    validation_data[field_name] = factory()
                # else: field is in partial_fields, we'll skip validation for it

        # Validate provided fields by doing full validation with defaults filled in
        # Only validate if we have all required fields covered
        try:
            instance = self._model_class.model_validate(validation_data)
            # Return only the originally provided fields and their validated values
            result = {}
            for field_name in data:
                if field_name in self._model_class.model_fields:
                    result[field_name] = getattr(instance, field_name)
            return result
        except PydanticValidationError as e:
            # Convert to Marshmallow errors, only for provided fields
            errors = {}
            failed_fields: set[str] = set()
            for error in e.errors():
                loc = error.get("loc", ())
                if loc:
                    field_name = str(loc[0])
                    failed_fields.add(field_name)
                    # Only report errors for fields that were actually provided
                    if field_name in data:
                        if field_name not in errors:
                            errors[field_name] = []
                        errors[field_name].append(format_pydantic_error(error, self._model_class))

            if errors:
                valid_data = {
                    k: v for k, v in data.items()
                    if k not in failed_fields and k in self._model_class.model_fields
                }
                raise BridgeValidationError(
                    errors,
                    data=original_data or data,
                    valid_data=valid_data,
                ) from e

            # No errors for provided fields - return the validated values for provided fields
            return {k: v for k, v in data.items() if k in self._model_class.model_fields}

    def _do_load(
        self,
        data: Any,
        *,
        many: bool | None = None,
        partial: bool | Sequence[str] | AbstractSet[str] | None = None,
        unknown: str | None = None,
        postprocess: bool = True,
        return_instance: bool = True,
    ) -> Any:
        """
        Override Marshmallow's _do_load to ensure proper hook ordering:

        1. User's @pre_load hooks run FIRST (transform input)
        2. Field filtering (only/exclude) applied
        3. Pydantic validates the TRANSFORMED data
        4. @validates("field") decorators run
        5. @validates_schema decorators run
        6. User's @post_load hooks run LAST

        This ensures 100% Marshmallow hook compatibility.
        """
        # PERFORMANCE: Hoist frequently accessed attributes to local variables
        # This avoids repeated self.__dict__ lookups in the hot path
        model_class = self._model_class
        hooks = self._hooks

        # Resolve settings
        if many is None:
            many = self.many

        # Resolve partial - instance attribute takes precedence
        if partial is None:
            partial = self._partial

        # Resolve unknown setting
        unknown_setting = unknown if unknown is not None else self._unknown_override
        if unknown_setting is None:
            unknown_setting = getattr(self.Meta, "unknown", RAISE)

        # Handle many=True
        if many:
            if not isinstance(data, list):
                raise MarshmallowValidationError({"_schema": ["Expected a list."]})
            return [
                self._do_load(
                    item,
                    many=False,
                    partial=partial,
                    unknown=unknown_setting,
                    postprocess=postprocess,
                    return_instance=return_instance,
                )
                for item in data
            ]

        # Step 1: Run pre_load hooks ONLY if they exist (PERFORMANCE OPTIMIZATION)
        # Skipping _invoke_load_processors when empty saves ~5ms per 10k loads
        if hooks.get("pre_load"):
            processed_data_raw = self._invoke_load_processors(
                "pre_load",
                data,
                many=False,
                original_data=data,
                partial=partial,
            )
        else:
            processed_data_raw = data

        # Type narrowing: at this point (many=False path), data is always a dict
        processed_data: dict[str, Any] = cast(dict[str, Any], processed_data_raw)

        # Step 2: Handle unknown fields based on setting
        # PERFORMANCE: Use cached field names instead of computing every time
        model_field_names: frozenset[str] | None = None
        if model_class:
            model_field_names = _get_model_field_names_with_aliases(model_class)
            unkn_fields = set(processed_data.keys()) - model_field_names

            if unkn_fields:
                if unknown_setting == RAISE:
                    errors = {field: ["Unknown field."] for field in unkn_fields}
                    raise MarshmallowValidationError(errors)
                if unknown_setting == EXCLUDE:
                    # Remove unknown fields
                    processed_data = {
                        k: v for k, v in processed_data.items() if k in model_field_names
                    }
                # INCLUDE: keep unknown fields in the result (handled below)

        # Step 3: Pydantic validates the transformed data
        # Returns (validated_dict, instance) - instance reused to avoid double validation
        pydantic_instance: M | None = None
        validated_data: dict[str, Any]

        # OPTIMIZATION: Determine if we need model_dump() for validators/result
        # Skip expensive model_dump() when not needed
        has_validators = bool(
            hooks[VALIDATES]
            or hooks[VALIDATES_SCHEMA]
            or self._field_validators_cache
            or self._schema_validators_cache
        )
        needs_dict = (
            not return_instance  # Need dict for result
            or unknown_setting == INCLUDE  # Need dict to merge unknown fields
            or has_validators  # Need dict for validators
        )

        if model_class:
            try:
                validated_data, pydantic_instance = self._validate_with_pydantic(
                    processed_data,
                    partial=partial,
                    original_data=data,
                    skip_model_dump=not needs_dict,
                )
            except MarshmallowValidationError as pydantic_error:
                # Call handle_error for Pydantic validation errors
                self.handle_error(pydantic_error, data, many=False)
                # handle_error should re-raise; if it doesn't, we do
                raise

            # If INCLUDE, add unknown fields back to validated data
            if unknown_setting == INCLUDE and model_field_names is not None:
                for field in (set(processed_data.keys()) - model_field_names):
                    validated_data[field] = processed_data[field]
        else:
            validated_data = processed_data

        # Step 4: Run field validators (BOTH Marshmallow native AND our custom)
        # This ensures validators work regardless of import source
        # ErrorStore is marshmallow internal without type hints - cast constructor for type safety
        error_store_cls: Callable[[], Any] = cast(Callable[[], Any], ErrorStore)
        error_store: Any = error_store_cls()

        # 4a: Run Marshmallow's native @validates decorators (from hooks)
        if hooks[VALIDATES]:
            self._invoke_field_validators(
                error_store=error_store,
                data=validated_data,
                many=False,
            )

        # 4b: Run our custom @validates decorators (backwards compatibility)
        try:
            self._run_field_validators(validated_data)
        except MarshmallowValidationError as field_error:
            # Merge into error_store
            if isinstance(field_error.messages, dict):
                for key, msgs in field_error.messages.items():
                    error_store.store_error({key: msgs if isinstance(msgs, list) else [msgs]})

        has_field_errors = bool(error_store.errors)

        # Step 5: Run schema validators (BOTH Marshmallow native AND our custom)
        # 5a: Run Marshmallow's native @validates_schema decorators
        if hooks[VALIDATES_SCHEMA]:
            self._invoke_schema_validators(
                error_store=error_store,
                pass_many=True,
                data=validated_data,
                original_data=data,
                many=False,
                partial=partial,
                field_errors=has_field_errors,
            )
            self._invoke_schema_validators(
                error_store=error_store,
                pass_many=False,
                data=validated_data,
                original_data=data,
                many=False,
                partial=partial,
                field_errors=has_field_errors,
            )

        # 5b: Run our custom @validates_schema decorators (backwards compatibility)
        try:
            self._run_schema_validators(validated_data, has_field_errors=has_field_errors)
        except MarshmallowValidationError as schema_error:
            if isinstance(schema_error.messages, dict):
                for key, msgs in schema_error.messages.items():
                    error_store.store_error({key: msgs if isinstance(msgs, list) else [msgs]})

        # Raise combined errors if any
        if error_store.errors:
            error = MarshmallowValidationError(dict(error_store.errors))
            self.handle_error(error, data, many=False)

        # Step 6: Prepare result based on return_instance flag
        if model_class and return_instance:
            if not partial:
                # OPTIMIZATION: Reuse the instance from _validate_with_pydantic
                result = pydantic_instance if pydantic_instance is not None else validated_data
            else:
                # For partial loading, create model with provided fields set
                # Fill in defaults for unprovided fields to avoid AttributeError
                from pydantic_core import PydanticUndefined
                construct_data = {}
                fields_set = set()

                for field_name, field_info in model_class.model_fields.items():
                    if field_name in validated_data:
                        construct_data[field_name] = validated_data[field_name]
                        fields_set.add(field_name)
                    else:
                        # Use default for unprovided fields
                        if field_info.default is not PydanticUndefined:
                            construct_data[field_name] = field_info.default
                        elif field_info.default_factory is not None:
                            # Cast to satisfy type checker
                            factory = cast(Callable[[], Any], field_info.default_factory)
                            construct_data[field_name] = factory()
                        else:
                            # No default - leave as None to avoid issues
                            construct_data[field_name] = None

                result = cast(
                    M, model_class.model_construct(_fields_set=fields_set, **construct_data)
                )
        else:
            # Return dict instead of instance
            result = validated_data

        # Step 7: Run post_load hooks ONLY if they exist (PERFORMANCE OPTIMIZATION)
        if postprocess and hooks.get("post_load"):
            result = self._invoke_load_processors(
                "post_load",
                result,
                many=False,
                original_data=data,
                partial=partial,
            )

        return result

    def _run_field_validators(self, data: dict[str, Any]) -> None:
        """Run @validates("field") decorated methods."""
        errors: dict[str, list[str]] = {}

        # Check cached validators (built at class creation)
        # Cache structure: {field_name: [validator_method_names]}
        for field_name, validator_names in self._field_validators_cache.items():
            if field_name not in data:
                continue
            for attr_name in validator_names:
                attr = getattr(self, attr_name, None)
                if callable(attr) and hasattr(attr, "_validates_field"):
                    try:
                        attr(data[field_name])
                    except MarshmallowValidationError as e:
                        if field_name not in errors:
                            errors[field_name] = []
                        if isinstance(e.messages, dict):
                            errors[field_name].extend(e.messages.get(field_name, [str(e)]))
                        else:
                            # e.messages is list or set-like
                            errors[field_name].extend(e.messages)

        if errors:
            raise MarshmallowValidationError(errors)

    def _run_schema_validators(self, data: dict[str, Any], has_field_errors: bool = False) -> None:
        """Run @validates_schema decorated methods."""
        errors: dict[str, list[str]] = {}

        # Check cached validators (built at class creation)
        for attr_name in self._schema_validators_cache:
            attr = getattr(self, attr_name, None)
            if callable(attr) and hasattr(attr, "_validates_schema"):
                # Check skip_on_field_errors
                skip_on_errors = getattr(attr, "_skip_on_field_errors", True)
                if skip_on_errors and has_field_errors:
                    continue

                try:
                    attr(data)
                except MarshmallowValidationError as e:
                    if "_schema" not in errors:
                        errors["_schema"] = []
                    if isinstance(e.messages, dict):
                        for key, msgs in e.messages.items():
                            if key not in errors:
                                errors[key] = []
                            if isinstance(msgs, (list, set, frozenset)):
                                errors[key].extend(msgs)
                            else:
                                errors[key].append(str(msgs))
                    else:
                        # e.messages is list or set-like
                        errors["_schema"].extend(e.messages)

        if errors:
            raise MarshmallowValidationError(errors)

    def validate(
        self,
        data: Any,
        *,
        many: bool | None = None,
        partial: bool | Sequence[str] | AbstractSet[str] | None = None,
    ) -> dict[str, Any]:
        """
        Validate data without raising an exception.

        Returns a dict of errors (empty dict if valid).

        Example:
            errors = schema.validate({"name": "", "email": "invalid"})
            if errors:
                print(errors)  # {'name': ['...'], 'email': ['...']}
        """
        try:
            self.load(data, many=many, partial=partial)
            return {}
        except MarshmallowValidationError as e:
            return e.messages if isinstance(e.messages, dict) else {"_schema": e.messages}

    def load(
        self,
        data: Any,
        *,
        many: bool | None = None,
        partial: bool | Sequence[str] | AbstractSet[str] | None = None,
        unknown: str | None = None,
        return_instance: bool = True,
    ) -> Any:
        """
        Deserialize data to a Pydantic model instance or dict.

        Args:
            data: Input data to deserialize
            many: If True, expect a list of objects
            partial: If True or tuple of field names, allow missing required fields
            unknown: How to handle unknown fields (RAISE, EXCLUDE, INCLUDE)
            return_instance: If True (default), return Pydantic model instance.
                            If False, return dict.

        Returns:
            Pydantic model instance (return_instance=True) or dict (return_instance=False)

        Example:
            # Get Pydantic instance (default)
            user = schema.load(data)  # Returns User model

            # Get dict instead
            user_dict = schema.load(data, return_instance=False)  # Returns dict
        """
        return self._do_load(
            data,
            many=many,
            partial=partial,
            unknown=unknown,
            postprocess=True,
            return_instance=return_instance,
        )

    def dump(
        self,
        obj: Any,
        *,
        many: bool | None = None,
        include_computed: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> Any:
        """
        Serialize an object.

        Accepts either a Pydantic model instance or a dict.
        Pydantic computed_field values are included by default.

        Args:
            obj: Object or list of objects to serialize
            many: If True, expect a list of objects
            include_computed: If True (default), include @computed_field values
            exclude_unset: If True, exclude fields that were not explicitly set
            exclude_defaults: If True, exclude fields that equal their default value
            exclude_none: If True, exclude fields with None values

        Returns:
            Serialized dict or list of dicts

        Example:
            class User(BaseModel):
                first: str
                last: str
                nickname: str | None = None

                @computed_field
                @property
                def full_name(self) -> str:
                    return f"{self.first} {self.last}"

            user = User(first="Alice", last="Smith")
            schema.dump(user)
            # {'first': 'Alice', 'last': 'Smith', 'full_name': 'Alice Smith', 'nickname': None}
            schema.dump(user, exclude_none=True)
            # {'first': 'Alice', 'last': 'Smith', 'full_name': 'Alice Smith'}
            schema.dump(user, exclude_unset=True)
            # {'first': 'Alice', 'last': 'Smith', 'full_name': 'Alice Smith'}
        """
        # Resolve many - check self.many if not explicitly set
        if many is None:
            many = self.many

        # Handle many=True (list of objects)
        if many:
            return [
                self._dump_single(
                    item,
                    include_computed=include_computed,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none,
                )
                for item in obj
            ]

        return self._dump_single(
            obj,
            include_computed=include_computed,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    def _dump_single(
        self,
        obj: Any,
        *,
        include_computed: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> dict[str, Any]:
        """Dump a single object, handling computed fields and exclusion options."""
        computed_values = {}
        model_class = None
        fields_to_exclude: set[str] = set()

        if isinstance(obj, BaseModel):
            model_class = type(obj)

            # Track which fields should be excluded based on Pydantic rules
            if exclude_unset:
                # Fields not in model_fields_set were not explicitly set
                fields_to_exclude.update(
                    f for f in model_class.model_fields
                    if f not in obj.model_fields_set
                )

            if exclude_defaults:
                # Fields that equal their default value
                from pydantic_core import PydanticUndefined
                for field_name, field_info in model_class.model_fields.items():
                    value = getattr(obj, field_name)
                    if field_info.default is not PydanticUndefined:
                        if value == field_info.default:
                            fields_to_exclude.add(field_name)
                    elif field_info.default_factory is not None:
                        # Cast to satisfy type checker
                        factory = cast(Callable[[], Any], field_info.default_factory)
                        default_val = factory()
                        if value == default_val:
                            fields_to_exclude.add(field_name)

            if exclude_none:
                # Fields with None values
                for field_name in model_class.model_fields:
                    if getattr(obj, field_name) is None:
                        fields_to_exclude.add(field_name)

            # Extract computed field values BEFORE converting to dict
            if include_computed and hasattr(model_class, 'model_computed_fields'):
                for field_name in model_class.model_computed_fields:
                    value = getattr(obj, field_name)
                    # Apply exclusion rules to computed fields too
                    if exclude_none and value is None:
                        fields_to_exclude.add(field_name)  # Track for removal
                        continue
                    computed_values[field_name] = value

            # Convert to dict for Marshmallow
            # Use by_alias=False - Marshmallow handles aliases via data_key
            obj = obj.model_dump(by_alias=False)

        # Let Marshmallow handle the standard dump
        result: dict[str, Any] = cast(dict[str, Any], super().dump(obj, many=False))

        # Apply field exclusions
        if fields_to_exclude:
            result = {k: v for k, v in result.items() if k not in fields_to_exclude}

        # Merge in computed fields
        if computed_values:
            result.update(computed_values)

        return result

    @classmethod
    def from_model(
        cls,
        model: type[M],
        *,
        schema_name: str | None = None,
        **meta_options: Any,
    ) -> type[PydanticSchema[M]]:
        """
        Create a PydanticSchema class from a Pydantic model.

        Example:
            from pydantic import BaseModel

            class User(BaseModel):
                name: str
                email: str

            UserSchema = PydanticSchema.from_model(User)

            schema = UserSchema()
            user = schema.load({"name": "Alice", "email": "alice@example.com"})

        Args:
            model: The Pydantic model class
            schema_name: Optional name for the schema class
            **meta_options: Additional Meta options (fields, exclude, etc.)

        Returns:
            A PydanticSchema subclass
        """
        # Build cache key from model and options
        # Sort options to ensure consistent keys
        try:
            cache_key = (model, tuple(sorted(meta_options.items())))
            if cache_key in _schema_class_cache:
                return _schema_class_cache[cache_key]
        except TypeError:
            # Unhashable options (e.g., list values) - skip cache
            cache_key = None

        name = schema_name or f"{model.__name__}Schema"

        # Extract field filtering options
        only_fields = meta_options.get("fields")  # Field whitelist
        exclude_fields = meta_options.get("exclude", ())  # Field blacklist

        # Build Meta attributes
        # Don't pass 'fields' or 'exclude' to Marshmallow's Meta class since we handle
        # field filtering ourselves by not adding those fields to class_dict.
        meta_attrs = {"model": model}
        for key, value in meta_options.items():
            if key not in ('fields', 'exclude'):
                meta_attrs[key] = value

        Meta = type("Meta", (), meta_attrs)  # noqa: N806 - Class name convention

        # Use centralized field conversion
        include_set = set(only_fields) if only_fields else None
        exclude_set = set(exclude_fields) if exclude_fields else None

        fields = convert_model_fields(
            model,
            include=include_set,
            exclude=exclude_set,
            include_computed=True,
        )

        # Build class dict with Meta and converted fields
        class_dict: dict[str, Any] = {"Meta": Meta, **fields}

        schema_cls = type(name, (cls,), class_dict)

        # Cache the schema class
        if cache_key is not None:
            _schema_class_cache[cache_key] = schema_cls

        return schema_cls


def schema_for(model: type[M], **meta_options: Any) -> type[PydanticSchema[M]]:
    """
    Shortcut to create a Marshmallow schema from a Pydantic model.

    Example:
        from pydantic import BaseModel, EmailStr

        class User(BaseModel):
            name: str
            email: EmailStr

        UserSchema = schema_for(User)

        # Use it
        schema = UserSchema()
        user = schema.load({"name": "Alice", "email": "alice@example.com"})
        print(user.name)  # "Alice" - it's a User instance!
    """
    return PydanticSchema.from_model(model, **meta_options)


def pydantic_schema(cls: type[M]) -> type[M]:
    """
    Decorator that adds a `.Schema` attribute to a Pydantic model.

    This is the simplest way to use marshmallow-pydantic. Just decorate
    your Pydantic model and use `.Schema` anywhere Marshmallow is expected.

    Example:
        from pydantic import BaseModel, EmailStr
        from pydantic_marshmallow import pydantic_schema

        @pydantic_schema
        class User(BaseModel):
            name: str
            email: EmailStr

        # Use .Schema anywhere Marshmallow schemas are expected:
        schema = User.Schema()
        user = schema.load({"name": "Alice", "email": "alice@example.com"})
        # user is a User instance!

        # Works with webargs:
        @use_args(User.Schema(), location="json")
        def create_user(user): ...

        # Works with apispec:
        spec.components.schema("User", schema=User.Schema)

        # All Marshmallow hooks still work:
        class UserSchema(User.Schema):
            @pre_load
            def normalize(self, data, **kwargs):
                data["email"] = data["email"].lower()
                return data
    """
    # Dynamically add Schema attribute to class
    # Note: setattr is required here since cls is type[M] without Schema defined
    setattr(cls, "Schema", PydanticSchema.from_model(cls))  # noqa: B010
    return cls


class HybridModel(BaseModel):
    """
    A Pydantic model that can also work as a Marshmallow schema.

    This provides a single class that gives you both Pydantic model
    capabilities AND Marshmallow schema functionality.

    Example:
        class User(HybridModel):
            name: str
            email: EmailStr
            age: int = Field(ge=0)

        # Use as Pydantic model
        user = User(name="Alice", email="alice@example.com", age=30)

        # Use for Marshmallow-style loading
        user = User.ma_load({"name": "Alice", "email": "alice@example.com", "age": 30})

        # Get the Marshmallow schema
        schema = User.marshmallow_schema()
    """

    model_config = ConfigDict(extra="forbid")  # Match Marshmallow's default strict behavior

    @classmethod
    def marshmallow_schema(cls) -> type[PydanticSchema[Any]]:
        """Get or create the Marshmallow schema for this model."""
        if cls not in _hybrid_schema_cache:
            _hybrid_schema_cache[cls] = PydanticSchema.from_model(cls)
        return _hybrid_schema_cache[cls]

    @classmethod
    def ma_load(cls, data: dict[str, Any], **kwargs: Any) -> HybridModel:
        """Load data using the Marshmallow schema."""
        schema = cls.marshmallow_schema()()
        result = schema.load(data, **kwargs)
        return cast(HybridModel, result)

    @classmethod
    def ma_loads(cls, json_str: str, **kwargs: Any) -> HybridModel:
        """Load data from a JSON string using the Marshmallow schema."""
        schema = cls.marshmallow_schema()()
        result = schema.loads(json_str, **kwargs)
        return cast(HybridModel, result)

    def ma_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Dump this instance using the Marshmallow schema."""
        schema = self.__class__.marshmallow_schema()()
        result = schema.dump(self, **kwargs)
        return cast(dict[str, Any], result)

    def ma_dumps(self, **kwargs: Any) -> str:
        """Dump this instance to a JSON string using the Marshmallow schema."""
        schema = self.__class__.marshmallow_schema()()
        result = schema.dumps(self, **kwargs)
        return cast(str, result)
