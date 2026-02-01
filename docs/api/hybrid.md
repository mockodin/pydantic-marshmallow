# HybridModel

A Pydantic model with built-in Marshmallow support.

## Class

::: pydantic_marshmallow.HybridModel
    options:
      show_root_heading: true
      show_source: false
      members:
        - marshmallow_schema
        - ma_load
        - ma_loads
        - ma_dump
        - ma_dumps

## Usage

### Basic Usage

```python
from pydantic_marshmallow import HybridModel
from pydantic import Field

class User(HybridModel):
    name: str
    email: str
    age: int = Field(ge=0)

# Use as a Pydantic model
user = User(name="Alice", email="alice@example.com", age=30)
print(user.model_dump())  # Pydantic method

# Use Marshmallow methods
data = user.ma_dump()  # Marshmallow serialization
json_str = user.ma_dumps()  # Marshmallow JSON serialization

# Load via Marshmallow
user = User.ma_load({"name": "Bob", "email": "bob@example.com", "age": 25})
user = User.ma_loads('{"name": "Charlie", "email": "c@example.com", "age": 35}')
```

### Getting the Schema Class

For ecosystem integration:

```python
# Get the Marshmallow schema class
UserSchema = User.marshmallow_schema()

# Use with webargs
@use_args(UserSchema(), location="json")
def create_user(user):
    pass

# Use with apispec
spec.components.schema("User", schema=UserSchema)
```

### Validation

HybridModel uses Pydantic's strict behavior by default:

```python
class StrictUser(HybridModel):
    name: str
    age: int

# Marshmallow load uses Pydantic validation
try:
    user = StrictUser.ma_load({"name": "", "age": -5})
except ValidationError as e:
    print(e.messages)
```

## When to Use HybridModel

Use `HybridModel` when you need:

- Both Pydantic and Marshmallow APIs on the same class
- A drop-in replacement that works with existing Pydantic code
- Simple cases without custom schema configuration

Use `PydanticSchema` when you need:

- Custom hooks (`@pre_load`, `@post_load`, etc.)
- Custom validators on the schema
- Field filtering (`only`, `exclude`, `load_only`, `dump_only`)
- Full control over schema behavior
