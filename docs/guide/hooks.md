# Hooks & Validators

pydantic-marshmallow supports all standard Marshmallow hooks and validators.

!!! info "Official Documentation"
    For complete hook and validator reference, see:
    
    - [Marshmallow: Extending Schemas](https://marshmallow.readthedocs.io/en/stable/extending.html)
    - [Pydantic: Validators](https://docs.pydantic.dev/latest/concepts/validators/)

## Marshmallow Hooks

### Pre-Load Hook

Transform data before validation:

```python
from marshmallow import pre_load

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @pre_load
    def normalize_email(self, data, **kwargs):
        if "email" in data:
            data["email"] = data["email"].lower().strip()
        return data
```

### Post-Load Hook

Process data after validation:

```python
from marshmallow import post_load

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @post_load
    def log_user(self, user, **kwargs):
        print(f"Loaded user: {user.name}")
        return user
```

### Pre-Dump Hook

Transform data before serialization:

```python
from marshmallow import pre_dump

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @pre_dump
    def add_timestamp(self, user, **kwargs):
        user.last_accessed = datetime.now()
        return user
```

### Post-Dump Hook

Process data after serialization:

```python
from marshmallow import post_dump

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @post_dump
    def add_links(self, data, **kwargs):
        data["_links"] = {"self": f"/users/{data['id']}"}
        return data
```

## Field Validators

### Using Marshmallow's `@validates`

```python
from marshmallow import validates, ValidationError

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @validates("name")
    def validate_name(self, value):
        if value.lower() == "admin":
            raise ValidationError("Cannot use 'admin' as name")
```

### Using `pydantic_marshmallow.validates`

For backwards compatibility:

```python
from pydantic_marshmallow import validates

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @validates("name")
    def validate_name(self, value):
        if not value[0].isupper():
            raise ValidationError("Name must start with uppercase")
```

## Schema Validators

Validate across multiple fields:

```python
from marshmallow import validates_schema, ValidationError

class UserSchema(PydanticSchema[User]):
    class Meta:
        model = User

    @validates_schema
    def validate_password_match(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError("Passwords must match", field_name="_schema")
```

### Skip on Field Errors

By default, schema validators skip if field errors exist:

```python
@validates_schema(skip_on_field_errors=True)  # Default
def check_consistency(self, data, **kwargs):
    # Only runs if all fields are valid
    ...

@validates_schema(skip_on_field_errors=False)
def always_check(self, data, **kwargs):
    # Runs even if field errors exist
    ...
```

## Pydantic Validators

Pydantic's own validators still work within your models:

```python
from pydantic import field_validator, model_validator

class User(BaseModel):
    name: str
    email: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip().title()

    @model_validator(mode="after")
    def check_consistency(self):
        if "admin" in self.email.lower():
            raise ValueError("Admin email not allowed")
        return self
```

These validators run during Pydantic validation (step 3 in the load pipeline).

!!! tip "When to use which?"
    - **Pydantic validators**: Data transformation, type coercion, model-specific rules
    - **Marshmallow validators**: Request-specific validation, cross-field checks, API-level concerns
    
    See [Pydantic Validators docs](https://docs.pydantic.dev/latest/concepts/validators/) for the full API.

## Hook Execution Order

1. **@pre_load** - Transform input data
2. **Pydantic validation** - Type coercion and Pydantic validators
3. **@validates("field")** - Field-level validators
4. **@validates_schema** - Schema-level validators
5. **@post_load** - Post-process result
