# Quick Start

Get up and running with pydantic-marshmallow in 5 minutes.

## Step 1: Define a Pydantic Model

```python
from pydantic import BaseModel, Field, EmailStr

class User(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)
```

## Step 2: Create a Marshmallow Schema

There are three ways to create a schema:

=== "schema_for() - Recommended"

    ```python
    from pydantic_marshmallow import schema_for

    UserSchema = schema_for(User)
    schema = UserSchema()
    ```

=== "PydanticSchema Class"

    ```python
    from pydantic_marshmallow import PydanticSchema

    class UserSchema(PydanticSchema[User]):
        class Meta:
            model = User

    schema = UserSchema()
    ```

=== "@pydantic_schema Decorator"

    ```python
    from pydantic_marshmallow import pydantic_schema

    @pydantic_schema
    class User(BaseModel):
        name: str
        email: EmailStr

    schema = User.Schema()
    ```

## Step 3: Load and Validate Data

```python
# Valid data
user = schema.load({
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})

print(type(user))  # <class 'User'>
print(user.name)   # "Alice"
```

## Step 4: Handle Validation Errors

```python
from marshmallow import ValidationError

try:
    user = schema.load({
        "name": "",  # Too short
        "email": "invalid",  # Not an email
        "age": -5  # Negative
    })
except ValidationError as e:
    print(e.messages)
    # {
    #     'name': ['String should have at least 1 character'],
    #     'email': ['value is not a valid email address'],
    #     'age': ['Input should be greater than or equal to 0']
    # }
```

## Step 5: Serialize Data

```python
# Serialize a Pydantic model instance
data = schema.dump(user)
# {"name": "Alice", "email": "alice@example.com", "age": 30}

# Serialize to JSON string
json_str = schema.dumps(user)
```

## Next Steps

- [Basic Usage](../guide/basic-usage.md) - Learn more about core features
- [Hooks & Validators](../guide/hooks.md) - Add custom validation logic
- [Ecosystem Integration](../guide/ecosystem.md) - Use with Flask, webargs, apispec
