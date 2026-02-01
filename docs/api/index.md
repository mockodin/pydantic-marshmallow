# API Reference

Auto-generated API documentation from source code docstrings.

## Core Components

- [PydanticSchema](schema.md) - Main schema class
- [Validators](validators.md) - Validation decorators  
- [Errors](errors.md) - Error handling
- [HybridModel](hybrid.md) - Hybrid Pydantic/Marshmallow model

## Quick Links

### Schema Creation

| Function | Description |
|:---------|:------------|
| [`schema_for()`](schema.md#pydantic_marshmallow.schema_for) | Create schema from model |
| [`PydanticSchema.from_model()`](schema.md#pydantic_marshmallow.PydanticSchema.from_model) | Create schema class with options |
| [`@pydantic_schema`](schema.md#pydantic_marshmallow.pydantic_schema) | Decorator to add .Schema attribute |

### Validation

| Decorator | Description |
|:----------|:------------|
| [`@validates`](validators.md#validatesfield_name) | Field validator |
| [`@validates_schema`](validators.md#validates_schemakwargs) | Schema-level validator |

### Errors

| Class | Description |
|:------|:------------|
| [`BridgeValidationError`](errors.md#pydantic_marshmallow.BridgeValidationError) | Validation error with valid_data |
