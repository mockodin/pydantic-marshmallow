# pydantic-marshmallow

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Bridge Pydantic's power with Marshmallow's ecosystem. Use Pydantic models for validation with full Marshmallow compatibility.

📖 **[Documentation](https://mockodin.github.io/pydantic-marshmallow)** | 🐙 **[GitHub](https://github.com/mockodin/pydantic-marshmallow)**

## Features

- **Pydantic Validation**: Leverage Pydantic's Rust-powered validation engine
- **Marshmallow Compatibility**: Works with Flask-Marshmallow, webargs, apispec, SQLAlchemy, and more
- **Zero Drift**: Single source of truth - Pydantic model defines the schema
- **Full Hook Support**: `@pre_load`, `@post_load`, `@pre_dump`, `@post_dump`
- **Validators**: `@validates("field")` and `@validates_schema` decorators
- **Partial Loading**: `partial=True` or `partial=('field1', 'field2')`
- **Unknown Fields**: `unknown=RAISE/EXCLUDE/INCLUDE`
- **Computed Fields**: Pydantic `@computed_field` support in serialization

## Installation

```bash
pip install pydantic-marshmallow
```

## Quick Start

### Basic Usage

```python
from pydantic import BaseModel, EmailStr, Field
from pydantic_marshmallow import PydanticSchema

class User(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    age: int = Field(ge=0)

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

# Use like any Marshmallow schema
schema = UserSchema()
user = schema.load({"name": "Alice", "email": "alice@example.com", "age": 30})
print(user.name)  # "Alice" - it's a Pydantic User instance!

# Serialize back
data = schema.dump(user)
# {"name": "Alice", "email": "alice@example.com", "age": 30}
```

### Using the Decorator

```python
from pydantic_marshmallow import pydantic_schema

@pydantic_schema
class User(BaseModel):
    name: str
    email: EmailStr

# .Schema attribute is automatically added
schema = User.Schema()
user = schema.load({"name": "Alice", "email": "alice@example.com"})
```

### Factory Function

```python
from pydantic_marshmallow import schema_for

UserSchema = schema_for(User)
schema = UserSchema()
```

## Marshmallow Hooks

All standard Marshmallow hooks work:

```python
from marshmallow import pre_load, post_load, validates

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @pre_load
    def normalize_email(self, data, **kwargs):
        if "email" in data:
            data["email"] = data["email"].lower().strip()
        return data

    @post_load
    def log_user(self, user, **kwargs):
        print(f"Loaded user: {user.name}")
        return user

    @validates("name")
    def validate_name(self, value):
        if value.lower() == "admin":
            raise ValidationError("Cannot use 'admin' as name")
```

## Partial Loading

```python
# Allow all missing required fields
user = schema.load({"name": "Alice"}, partial=True)

# Allow specific missing fields
user = schema.load({"name": "Alice"}, partial=("email", "age"))
```

## Unknown Field Handling

```python
from marshmallow import EXCLUDE, INCLUDE, RAISE

# Reject unknown fields (default)
schema = UserSchema(unknown=RAISE)

# Ignore unknown fields
schema = UserSchema(unknown=EXCLUDE)

# Include unknown fields in result
schema = UserSchema(unknown=INCLUDE)
```

## Field Filtering

```python
# Only include specific fields
schema = UserSchema(only=("name", "email"))

# Exclude specific fields
schema = UserSchema(exclude=("age",))

# Load-only fields (not in dump output)
schema = UserSchema(load_only=("password",))

# Dump-only fields (not in load input)
schema = UserSchema(dump_only=("created_at",))
```

## Computed Fields

```python
from pydantic import computed_field

class User(BaseModel):
    first: str
    last: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

schema = schema_for(User)()
user = User(first="Alice", last="Smith")
data = schema.dump(user)
# {"first": "Alice", "last": "Smith", "full_name": "Alice Smith"}
```

## Dump Options

```python
# Exclude None values
schema.dump(user, exclude_none=True)

# Exclude unset fields
schema.dump(user, exclude_unset=True)

# Exclude fields with default values
schema.dump(user, exclude_defaults=True)
```

## Flask-Marshmallow Integration

```python
from flask import Flask
from flask_marshmallow import Marshmallow
from pydantic_marshmallow import schema_for

app = Flask(__name__)
ma = Marshmallow(app)

UserSchema = schema_for(User)

@app.route("/users", methods=["POST"])
def create_user():
    schema = UserSchema()
    user = schema.load(request.json)
    # user is a Pydantic User instance
    return schema.dump(user)
```

## webargs Integration

```python
from webargs.flaskparser import use_args
from pydantic_marshmallow import schema_for

UserSchema = schema_for(User)

@app.route("/users", methods=["POST"])
@use_args(UserSchema(), location="json")
def create_user(user):
    # user is a Pydantic User instance
    return {"message": f"Created {user.name}"}
```

## apispec Integration

```python
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

spec = APISpec(
    title="My API",
    version="1.0.0",
    openapi_version="3.0.0",
    plugins=[MarshmallowPlugin()],
)

spec.components.schema("User", schema=UserSchema)
```

## HybridModel

For models that need both Pydantic and Marshmallow APIs:

```python
from pydantic_marshmallow import HybridModel

class User(HybridModel):
    name: str
    email: EmailStr

# Use as Pydantic model
user = User(name="Alice", email="alice@example.com")

# Use Marshmallow-style loading
user = User.ma_load({"name": "Alice", "email": "alice@example.com"})

# Get the Marshmallow schema class
schema_class = User.marshmallow_schema()
```

## Error Handling

Validation errors are raised as `BridgeValidationError`, which extends Marshmallow's `ValidationError`:

```python
from pydantic_marshmallow import BridgeValidationError

try:
    user = schema.load({"name": "", "email": "invalid"})
except BridgeValidationError as e:
    print(e.messages)
    # {'name': ['String should have at least 1 character'],
    #  'email': ['value is not a valid email address']}
    print(e.valid_data)
    # {} - fields that passed validation
```

## API Reference

### PydanticSchema

A Marshmallow schema backed by a Pydantic model.

**Class Methods:**
- `from_model(model, **meta_options)` - Create a schema class from a Pydantic model

**Instance Methods:**
- `load(data, *, many, partial, unknown, return_instance)` - Deserialize data
- `dump(obj, *, many, exclude_none, exclude_unset, exclude_defaults)` - Serialize data
- `validate(data, *, many, partial)` - Validate without deserializing

**Hooks:**
- `on_bind_field(field_name, field_obj)` - Called when a field is bound
- `handle_error(error, data, *, many)` - Custom error handling

### Factory Functions

- `schema_for(model, **meta_options)` - Create a schema class from a model
- `pydantic_schema` - Decorator that adds `.Schema` to a model

### HybridModel

A Pydantic model with built-in Marshmallow support.

**Class Methods:**
- `marshmallow_schema()` - Get the Marshmallow schema class
- `ma_load(data, **kwargs)` - Load using Marshmallow
- `ma_loads(json_str, **kwargs)` - Load from JSON string

**Instance Methods:**
- `ma_dump(**kwargs)` - Dump using Marshmallow
- `ma_dumps(**kwargs)` - Dump to JSON string

## License

MIT