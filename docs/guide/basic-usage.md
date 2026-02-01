# Basic Usage

This guide covers the bridge-specific APIs. For underlying features, see:

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/)
- [Marshmallow Schemas](https://marshmallow.readthedocs.io/en/stable/quickstart.html)

## Creating Schemas

### Using `schema_for()`

The simplest way to create a schema:

```python
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

class User(BaseModel):
    name: str
    email: str

UserSchema = schema_for(User)
schema = UserSchema()
```

### Using `PydanticSchema` Class

For more control, subclass `PydanticSchema`:

```python
from pydantic_marshmallow import PydanticSchema

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User
```

### Using `from_model()` with Options

Create schemas with field filtering:

```python
# Only include specific fields
LimitedSchema = PydanticSchema.from_model(User, fields=("name", "email"))

# Exclude specific fields
FilteredSchema = PydanticSchema.from_model(User, exclude=("password",))
```

## Loading Data

### Basic Load

```python
schema = UserSchema()
user = schema.load({"name": "Alice", "email": "alice@example.com"})
```

### Load as Dict (not model instance)

```python
data = schema.load({"name": "Alice", "email": "alice@example.com"}, return_instance=False)
# Returns dict instead of User instance
```

### Load Many

```python
schema = UserSchema(many=True)
users = schema.load([
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"}
])
```

### Partial Loading

Allow missing required fields:

```python
# All fields optional
user = schema.load({"name": "Alice"}, partial=True)

# Only specific fields optional
user = schema.load({"name": "Alice"}, partial=("email",))
```

## Serializing Data

### Basic Dump

```python
data = schema.dump(user)
```

### Dump Options

```python
# Exclude None values
data = schema.dump(user, exclude_none=True)

# Exclude unset fields (never assigned)
data = schema.dump(user, exclude_unset=True)

# Exclude fields equal to their default
data = schema.dump(user, exclude_defaults=True)
```

### Dump to JSON

```python
json_str = schema.dumps(user)
```

## Unknown Field Handling

Control how unknown fields are handled (standard Marshmallow behavior):

```python
from marshmallow import RAISE, EXCLUDE, INCLUDE

# Reject unknown fields (default)
schema = UserSchema(unknown=RAISE)

# Silently remove unknown fields
schema = UserSchema(unknown=EXCLUDE)

# Include unknown fields in result
schema = UserSchema(unknown=INCLUDE)
```

See [Marshmallow: Handling Unknown Fields](https://marshmallow.readthedocs.io/en/stable/quickstart.html#handling-unknown-fields) for details.

## Validation Without Loading

Get validation errors without deserializing:

```python
errors = schema.validate({"name": "", "email": "invalid"})
if errors:
    print(errors)  # {'name': [...], 'email': [...]}
else:
    print("Valid!")
```
