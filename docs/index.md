# pydantic-marshmallow

Bridge Pydantic's power with Marshmallow's ecosystem. Use Pydantic models for validation with full Marshmallow compatibility.

!!! abstract "Prerequisites"
    This library assumes familiarity with:
    
    - [Pydantic](https://docs.pydantic.dev/) - Data validation using Python type hints
    - [Marshmallow](https://marshmallow.readthedocs.io/) - Object serialization/deserialization

## Why pydantic-marshmallow?

- **Pydantic Validation**: Leverage Pydantic's Rust-powered validation engine
- **Marshmallow Compatibility**: Works with Flask-Marshmallow, webargs, apispec, SQLAlchemy, and more
- **Zero Drift**: Single source of truth - Pydantic model defines the schema
- **Full Hook Support**: `@pre_load`, `@post_load`, `@pre_dump`, `@post_dump`
- **Type Coercion**: Automatic string-to-int, string-to-bool, etc.

## Quick Example

```python
from pydantic import BaseModel, EmailStr, Field
from pydantic_marshmallow import schema_for

class User(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    age: int = Field(ge=0)

# Create a Marshmallow schema from the Pydantic model
UserSchema = schema_for(User)
schema = UserSchema()

# Load and validate data - Pydantic validation runs!
user = schema.load({"name": "Alice", "email": "alice@example.com", "age": 30})
print(user.name)  # "Alice" - it's a Pydantic User instance!

# Serialize back
data = schema.dump(user)
# {"name": "Alice", "email": "alice@example.com", "age": 30}
```

## Installation

```bash
pip install pydantic-marshmallow
```

## Next Steps

- [Installation](getting-started/installation.md) - Detailed installation instructions
- [Quick Start](getting-started/quickstart.md) - Get up and running in 5 minutes
- [API Reference](api/index.md) - Complete API documentation
