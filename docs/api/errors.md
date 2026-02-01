# Errors

Error classes and utilities for validation error handling.

## Classes

::: pydantic_marshmallow.BridgeValidationError
    options:
      show_root_heading: true
      show_source: false
      members:
        - messages
        - data
        - valid_data

## Usage

### Catching Validation Errors

```python
from pydantic_marshmallow import schema_for, BridgeValidationError

UserSchema = schema_for(User)
schema = UserSchema()

try:
    user = schema.load({
        "name": "",
        "email": "invalid",
        "age": -5
    })
except BridgeValidationError as e:
    # Error messages by field
    print(e.messages)
    # {'name': ['String should have at least 1 character'],
    #  'email': ['value is not a valid email address'],
    #  'age': ['Input should be greater than or equal to 0']}
    
    # Original input data
    print(e.data)
    # {'name': '', 'email': 'invalid', 'age': -5}
    
    # Fields that passed validation
    print(e.valid_data)
    # {}
```

### Marshmallow Compatibility

`BridgeValidationError` extends Marshmallow's `ValidationError`, so standard exception handling works:

```python
from marshmallow import ValidationError

try:
    user = schema.load(invalid_data)
except ValidationError as e:
    # Works with both Marshmallow and Bridge errors
    print(e.messages)
```

### Partial Validation

When using partial loading, `valid_data` contains fields that passed:

```python
try:
    user = schema.load(
        {"name": "Alice", "email": "invalid"},
        partial=True
    )
except BridgeValidationError as e:
    print(e.valid_data)
    # {'name': 'Alice'}  # email failed, but name was valid
```
