# Validators

Validator decorators for PydanticSchema, re-exported from Marshmallow for convenience.

!!! tip "Import from either location"
    ```python
    # Both work identically:
    from pydantic_marshmallow import validates, validates_schema
    from marshmallow import validates, validates_schema
    ```

## Decorators

### `@validates(field_name)`

Registers a method as a validator for a specific field. The method receives the field value and can raise `ValidationError` if validation fails.

**Parameters:**

- `field_name` (str): Name of the field to validate

### `@validates_schema(**kwargs)`

Registers a method as a schema-level validator that receives the full data dictionary.

**Parameters:**

- `skip_on_field_errors` (bool): Skip validation if field-level errors exist (default: True)
- `pass_many` (bool): Pass the full collection when `many=True` (default: False)

## Usage Examples

### Field Validator

```python
from pydantic_marshmallow import PydanticSchema, validates
from marshmallow import ValidationError

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @validates("name")
    def validate_name(self, value):
        if value.lower() == "admin":
            raise ValidationError("Cannot use 'admin' as name")
```

### Schema Validator

```python
from pydantic_marshmallow import PydanticSchema, validates_schema
from marshmallow import ValidationError

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError("Passwords must match", field_name="_schema")
```

### With Options

```python
@validates_schema(skip_on_field_errors=False)
def always_validate(self, data, **kwargs):
    # Runs even if field-level validation failed
    pass

@validates_schema(pass_many=True)
def validate_collection(self, data, **kwargs):
    # Receives full collection when many=True
    pass
```
