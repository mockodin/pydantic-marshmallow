# Capability Matrix: Pydantic ↔ Marshmallow Bridge

This document maps features from both libraries and tracks bridge support.

**Last Updated**: February 2026  
**Tested Versions**: Marshmallow 3.x, Pydantic 2.x  
**Test Suite**: 375+ tests

## Legend
- ✅ Fully supported and tested
- ⚠️ Partial support or limitations
- ❌ Not yet supported
- N/A Not applicable

---

## 1. Marshmallow Features → Bridge Status

### Schema Methods

| Feature | Status | Notes |
|:--------|:------:|:------|
| `load(data)` | ✅ | Pydantic validates |
| `loads(json_str)` | ✅ | Via Marshmallow |
| `dump(obj)` | ✅ | Via model_dump |
| `dumps(obj)` | ✅ | Via Marshmallow |
| `validate(data)` | ✅ | Returns errors dict |
| `many=True` | ✅ | Collection handling |
| `partial=True/tuple` | ✅ | Partial loading supported |
| `unknown=RAISE` | ✅ | Default Pydantic behavior |
| `unknown=EXCLUDE` | ✅ | Silently ignores unknown |
| `unknown=INCLUDE` | ✅ | Keeps unknown in result |

### Schema Instance Parameters

| Feature | Status | Notes |
|:--------|:------:|:------|
| `only=tuple` | ✅ | Field filtering |
| `exclude=tuple` | ✅ | Field filtering |
| `load_only=tuple` | ✅ | Write-only fields |
| `dump_only=tuple` | ✅ | Read-only fields |
| `context={}` | ✅ | Validation context |

### Schema.Meta Options

| Feature | Status | Notes |
|:--------|:------:|:------|
| `model` | ✅ | Custom option for Pydantic model |
| `fields` | ✅ | Field whitelist |
| `exclude` | ✅ | Field blacklist |
| `dump_only` | ✅ | Via from_model() |
| `load_only` | ✅ | Via from_model() |
| `many` | ✅ | Default many behavior |
| `unknown` | ✅ | Unknown field handling |
| `render_module` | ✅ | Via Marshmallow |
| `index_errors` | ✅ | Collection error indices |
| `register` | ✅ | Via Marshmallow |
| `additional` | N/A | Model defines fields |
| `include` | N/A | Model defines fields |
| `dateformat` | N/A | Pydantic handles |
| `datetimeformat` | N/A | Pydantic handles |

### Hooks (Critical)

| Hook | Status | Notes |
|:-----|:------:|:------|
| `@pre_load` | ✅ | Runs BEFORE Pydantic validates |
| `@post_load` | ✅ | Runs AFTER model creation |
| `@pre_dump` | ✅ | Via Marshmallow |
| `@post_dump` | ✅ | Via Marshmallow |
| `@validates("field")` | ✅ | Field validators |
| `@validates_schema` | ✅ | Schema validators |
| `pass_many=True` | ✅ | Collection hooks work |
| `pass_original=True` | ✅ | Original data access |
| `skip_on_field_errors` | ✅ | Skip schema validation |

### Field Types

| Marshmallow Field | Pydantic Equivalent | Status |
|:------------------|:--------------------|:------:|
| `String` | `str` | ✅ |
| `Integer` | `int` | ✅ |
| `Float` | `float` | ✅ |
| `Decimal` | `Decimal` | ✅ |
| `Boolean` | `bool` | ✅ |
| `DateTime` | `datetime` | ✅ |
| `Date` | `date` | ✅ |
| `Time` | `time` | ✅ |
| `TimeDelta` | `timedelta` | ✅ |
| `UUID` | `UUID` | ✅ |
| `Email` | `EmailStr` | ✅ |
| `Url` | `HttpUrl`/`AnyUrl` | ✅ |
| `Nested` | Nested `BaseModel` | ✅ |
| `List` | `list[T]` | ✅ |
| `Dict` | `dict[K,V]` | ✅ |
| `Tuple` | `tuple[T,...]` | ✅ |
| `Raw` | `Any` | ✅ |
| `Constant` | `Literal[value]` | ✅ |
| `Enum` | `Enum` | ✅ |
| `IP/IPv4/IPv6` | `IPvAnyAddress` | ✅ |
| `AwareDateTime` | `AwareDatetime` | ✅ |
| `NaiveDateTime` | `NaiveDatetime` | ✅ |
| `Method` | Use `@computed_field` | N/A |
| `Function` | Use `@field_validator` | N/A |
| `Pluck` | Use `@computed_field` | N/A |

### Field Options

| Option | Status | Pydantic Equivalent |
|:-------|:------:|:--------------------|
| `required` | ✅ | No default = required |
| `allow_none` | ✅ | `Optional[T]` |
| `load_default` | ✅ | `Field(default=...)` |
| `dump_default` | ✅ | Same as load_default |
| `data_key` | ✅ | `Field(alias=...)` |
| `attribute` | ✅ | `serialization_alias` |
| `validate` | ✅ | `@field_validator` |
| `load_only` | ✅ | `Field(exclude=True)` |
| `dump_only` | ✅ | init=False pattern |
| `error_messages` | ✅ | Via json_schema_extra |
| `metadata` | ✅ | `Field(json_schema_extra=...)` |

### Built-in Validators

| Validator | Status | Pydantic Equivalent |
|:----------|:------:|:--------------------|
| `Length(min, max)` | ✅ | `Field(min_length, max_length)` |
| `Range(min, max)` | ✅ | `Field(ge, le, gt, lt)` |
| `OneOf(choices)` | ✅ | `Literal[...]` or `Enum` |
| `NoneOf(values)` | ✅ | Via `@field_validator` |
| `Equal(value)` | ✅ | `Literal[value]` |
| `Regexp(pattern)` | ✅ | `Field(pattern=...)` |
| `Email()` | ✅ | `EmailStr` |
| `URL()` | ✅ | `HttpUrl` |
| `Predicate(method)` | ✅ | Via `@field_validator` |
| `And(*validators)` | ✅ | Multiple annotations |
| `ContainsOnly` | ✅ | Via `@field_validator` |
| `ContainsNoneOf` | ✅ | Via `@field_validator` |

### Error Handling

| Feature | Status | Notes |
|:--------|:------:|:------|
| `ValidationError.messages` | ✅ | Converted format |
| `ValidationError.valid_data` | ✅ | Partial data on errors |
| `ValidationError.data` | ✅ | Original input preserved |
| Nested error paths | ✅ | Full `loc` tuple support |
| Collection indices | ✅ | Index in path (items.0) |
| `_schema` errors | ✅ | Schema-level errors |
| Custom error messages | ✅ | Via json_schema_extra |

### Advanced Features

| Feature | Status | Notes |
|:--------|:------:|:------|
| `handle_error()` override | ✅ | Error handling hook |
| `on_bind_field()` override | ✅ | Field binding hook |
| `get_attribute()` override | ✅ | Attribute access |
| Context passing | ✅ | Via `context={}` param |
| Schema inheritance | ✅ | Class inheritance |
| Schema registry (string refs) | ✅ | Via Marshmallow |
| `from_dict()` dynamic schemas | ✅ | Via `create_model()` |

---

## 2. Pydantic Features → Available via Bridge

### Model Methods

| Feature | Status | Notes |
|:--------|:------:|:------|
| `model_validate()` | ✅ | Core of bridge |
| `model_validate_json()` | ✅ | Via loads() |
| `model_dump()` | ✅ | Via dump() |
| `model_dump_json()` | ✅ | Via dumps() |
| `model_copy()` | ✅ | Direct on model |
| `model_json_schema()` | ✅ | Direct on model |
| `model_construct()` | ✅ | Direct on model |
| `model_post_init()` | ✅ | Direct on model |
| `model_fields` | ✅ | Direct on model |

### ConfigDict Options

| Option | Status | Notes |
|:-------|:------:|:------|
| `extra='forbid'` | ✅ | Maps to unknown=RAISE |
| `extra='allow'` | ✅ | Maps to unknown=INCLUDE |
| `extra='ignore'` | ✅ | Maps to unknown=EXCLUDE |
| `frozen=True` | ✅ | Immutable models |
| `populate_by_name` | ✅ | Alias flexibility |
| `strict=True` | ✅ | No type coercion |
| `validate_assignment` | ✅ | On attribute set |
| `from_attributes` | ✅ | ORM mode |
| `allow_inf_nan` | ✅ | Float special values |
| `str_strip_whitespace` | ✅ | Auto-strip |
| `str_to_lower/upper` | ✅ | Case transform |
| `use_enum_values` | ✅ | Store raw values |
| `arbitrary_types_allowed` | ✅ | Custom types |
| `alias_generator` | ✅ | Auto-aliases |
| `ser_json_bytes` | ✅ | Bytes serialization |
| `coerce_numbers_to_str` | ✅ | Number→string |

### Validators

| Feature | Status | Notes |
|:--------|:------:|:------|
| `@field_validator(mode='before')` | ✅ | Pre-validation |
| `@field_validator(mode='after')` | ✅ | Post-validation |
| `@field_validator(mode='wrap')` | ✅ | Wrap validation |
| `@field_validator(mode='plain')` | ✅ | Replace validation |
| `@model_validator(mode='before')` | ✅ | Pre all fields |
| `@model_validator(mode='after')` | ✅ | Post all fields |
| `@computed_field` | ✅ | Computed properties |
| `@field_serializer` | ✅ | Custom serialization |
| `@model_serializer` | ✅ | Full model serialization |

### Field Options (Field())

| Option | Status | Notes |
|:-------|:------:|:------|
| `default` | ✅ | Default value |
| `default_factory` | ✅ | Callable default |
| `alias` | ✅ | Load/dump alias → data_key |
| `validation_alias` | ✅ | Load-only alias |
| `serialization_alias` | ✅ | Dump-only alias → attribute |
| `title` | ✅ | JSON schema |
| `description` | ✅ | JSON schema |
| `examples` | ✅ | JSON schema |
| `gt/ge/lt/le` | ✅ | Numeric constraints |
| `multiple_of` | ✅ | Divisibility |
| `min_length/max_length` | ✅ | String/list length |
| `pattern` | ✅ | Regex |
| `strict` | ✅ | No coercion |
| `frozen` | ✅ | Immutable field |
| `exclude` | ✅ | Skip in dump → load_only |
| `discriminator` | ✅ | Union discriminator |
| `repr` | ✅ | repr() inclusion |
| `init` | ✅ | __init__ inclusion |
| `kw_only` | ✅ | Keyword-only |
| `deprecated` | ✅ | Mark deprecated |

### Type System

| Feature | Status | Notes |
|:--------|:------:|:------|
| Standard library types | ✅ | All supported |
| `Optional[T]` / `T \| None` | ✅ | Nullable |
| `Union[A, B]` | ✅ | Multiple types |
| `Literal[...]` | ✅ | Exact values |
| `Annotated[T, ...]` | ✅ | Type metadata |
| Generic models | ✅ | TypeVar support |
| Recursive models | ✅ | Self-reference |
| `EmailStr` | ✅ | Email validation |
| `HttpUrl` / `AnyUrl` | ✅ | URL validation |
| `SecretStr` | ✅ | Hidden values |
| `Json[T]` | ✅ | Parse JSON |
| Constrained types | ✅ | All constraints |
| Custom types | ✅ | pydantic-core |

### Aliases

| Feature | Status | Notes |
|:--------|:------:|:------|
| `alias` | ✅ | Single alias → data_key |
| `validation_alias` | ✅ | Input-only |
| `serialization_alias` | ✅ | Output-only |
| `AliasPath` | ✅ | Nested paths |
| `AliasChoices` | ✅ | Multiple inputs |
| `AliasGenerator` | ✅ | Auto-generate |
| `to_camel`/`to_snake` | ✅ | Case converters |

### Discriminated Unions

| Feature | Status | Notes |
|:--------|:------:|:------|
| `Field(discriminator=...)` | ✅ | String discriminator |
| `Discriminator` callable | ✅ | Custom discriminator |
| `Tag` annotation | ✅ | Tagged unions |

---

## 3. Bridge-Specific Features

### Core APIs

| Feature | Status | Notes |
|:--------|:------:|:------|
| `PydanticSchema[M]` | ✅ | Generic schema |
| `schema_for(Model)` | ✅ | Factory function |
| `@pydantic_schema` | ✅ | Decorator |
| `HybridModel` | ✅ | Dual-interface |
| `HybridModel.ma_load()` | ✅ | Marshmallow load |
| `HybridModel.ma_dump()` | ✅ | Marshmallow dump |

### Ecosystem Compatibility

| Tool | Status | Notes |
|:-----|:------:|:------|
| Flask-Rebar | ✅ | Schema subclass |
| webargs | ✅ | Schema subclass |
| apispec | ✅ | Schema subclass |
| Flask-Marshmallow | ✅ | Schema subclass |
| Flask-Smorest | ✅ | Schema subclass |
| marshmallow-sqlalchemy | ✅ | Works alongside |

---

## 4. Version Compatibility

| pydantic-marshmallow | Marshmallow | Pydantic | Python |
|:---------------------|:------------|:---------|:-------|
| 0.1.x | 3.18+ | 2.0+ | 3.9-3.14 |

**CI tests against:** Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 on Ubuntu/Windows/macOS
