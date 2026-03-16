# Field Options

Control which fields are included in load/dump operations.

!!! note "Marshmallow Reference"
    These options mirror [Marshmallow's field filtering](https://marshmallow.readthedocs.io/en/stable/quickstart.html#specifying-which-fields-to-output). 
    The `exclude_*` dump options map to [Pydantic's model_dump()](https://docs.pydantic.dev/latest/concepts/serialization/#modelmodel_dump).

## Field Filtering

### `only` - Whitelist Fields

Include only specific fields:

```python
schema = UserSchema(only=("name", "email"))

# Load: only name and email are processed
# Dump: only name and email are output
```

### `exclude` - Blacklist Fields

Exclude specific fields:

```python
schema = UserSchema(exclude=("password", "internal_id"))
```

### `fields` via Meta

Set default field filtering at class level:

```python
class PublicUserSchema(PydanticSchema[User]):
    class Meta:
        model = User
        fields = ("name", "email", "age")  # Only these fields
```

### `exclude` via Meta

```python
class SafeUserSchema(PydanticSchema[User]):
    class Meta:
        model = User
        exclude = ("password", "secret_key")
```

## Directional Fields

### `load_only` - Input Only

Fields that are accepted during load but not included in dump:

```python
schema = UserSchema(load_only=("password",))

# password accepted in load()
# password NOT included in dump()
```

### `dump_only` - Output Only

Fields that are included in dump but not required during load:

```python
schema = UserSchema(dump_only=("created_at", "id"))

# created_at and id NOT required in load()
# created_at and id included in dump()
```

## Combining Options

Options can be combined:

```python
schema = UserSchema(
    only=("name", "email", "password", "created_at"),
    load_only=("password",),
    dump_only=("created_at",),
)
```

## Using `from_model()` with Options

```python
# Create a schema with specific fields
PublicSchema = PydanticSchema.from_model(
    User,
    fields=("name", "email"),
)

# Create a schema excluding sensitive fields
SafeSchema = PydanticSchema.from_model(
    User,
    exclude=("password", "api_key"),
)
```

## Dump Exclusion Options

Additional options for `dump()`:

```python
# Exclude fields with None values
data = schema.dump(user, exclude_none=True)

# Exclude fields that weren't explicitly set
data = schema.dump(user, exclude_unset=True)

# Exclude fields equal to their default value
data = schema.dump(user, exclude_defaults=True)
```

### Example

```python
class User(BaseModel):
    name: str
    nickname: str | None = None
    role: str = "user"

user = User(name="Alice")  # nickname and role use defaults

schema.dump(user)
# {"name": "Alice", "nickname": None, "role": "user"}

schema.dump(user, exclude_none=True)
# {"name": "Alice", "role": "user"}

schema.dump(user, exclude_defaults=True)
# {"name": "Alice"}

schema.dump(user, exclude_unset=True)
# {"name": "Alice"}
```

## Metadata Forwarding

Pydantic `Field()` metadata is automatically forwarded to Marshmallow fields, enabling ecosystem tools like **apispec** and **flask-smorest** to generate accurate OpenAPI schemas.

!!! info "Metadata is merged"
    Forwarded metadata is **merged** into any existing Marshmallow field metadata
    (e.g., metadata set by the type mapping), not replaced.

Supported metadata:

| Pydantic `Field()` | Marshmallow `field.metadata` key |
|---------------------|----------------------------------|
| `description="..."` | `"description"` |
| `title="..."` | `"title"` |
| `examples=[...]` | `"examples"` |
| `json_schema_extra={...}` | `"json_schema_extra"` |

```python
from pydantic import BaseModel, Field
from pydantic_marshmallow import PydanticSchema

class Product(BaseModel):
    name: str = Field(description="Product display name", title="Name")
    price: float = Field(description="Price in USD", examples=[9.99, 19.99])

ProductSchema = PydanticSchema.from_model(Product)
schema = ProductSchema()

# Metadata is available on the Marshmallow field
print(schema.fields["name"].metadata)
# {"description": "Product display name", "title": "Name"}

# apispec reads this automatically for OpenAPI generation
```

## Constraint-to-Validator Mapping

Pydantic field constraints are mapped to Marshmallow validators so that ecosystem tools can generate accurate OpenAPI schemas with `minLength`, `maxLength`, `minimum`, `maximum`, and `pattern`.

!!! note "Validation is still Pydantic's job"
    These validators are **never invoked during `load()`** — Pydantic owns all validation.
    They exist solely for schema introspection by tools like apispec.

!!! info "Validators are appended"
    Constraint validators are **appended** to any existing field validators
    (e.g., `OneOf` for `Literal` types), not replaced.

| Pydantic Constraint | Marshmallow Validator | OpenAPI Output |
|--------------------|-----------------------|----------------|
| `min_length` / `max_length` | `Length(min=, max=)` | `minLength` / `maxLength` |
| `ge` / `le` / `gt` / `lt` | `Range(min=, max=)` | `minimum` / `maximum` / `exclusiveMinimum` / `exclusiveMaximum` |
| `pattern` | `Regexp(regex)` | `pattern` |

```python
from pydantic import BaseModel, Field
from pydantic_marshmallow import PydanticSchema

class User(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
    email: str = Field(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")

UserSchema = PydanticSchema.from_model(User)
schema = UserSchema()

# Validators are set on the Marshmallow fields
print(schema.fields["name"].validators)
# [Length(min=1, max=100)]

print(schema.fields["age"].validators)
# [Range(min=0, max=150)]
```
