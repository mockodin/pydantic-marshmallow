---
applyTo: '**/*.py'
---

# Implementation Guide

## Adding New Type Mappings

When Pydantic introduces a new type that needs Marshmallow field mapping:

### 1. Update `type_mapping.py`

```python
# In _type_to_marshmallow_field()
def _type_to_marshmallow_field(python_type: type, field_info: FieldInfo) -> fields.Field:
    # Add new type handling
    if python_type is NewType:
        return fields.NewMarshmallowField(**kwargs)
```

### 2. Add Tests

```python
# In tests/test_edge_cases.py
def test_new_type_field(self):
    """Test NewType field handling."""
    class Model(BaseModel):
        value: NewType

    schema = schema_for(Model)()

    result = schema.load({"value": "input"})
    assert result.value == expected_output

    dumped = schema.dump(result)
    assert dumped["value"] == "serialized"
```

### 3. Update Capability Matrix

Update the capability matrix in `Compatibility_Analysis.instructions.md` to mark the type as supported.

---

## Adding Hook Support

### Hook Execution Order (Critical)

```
Input Data
    │
    ▼
@pre_load (Marshmallow) ─── Transform input data
    │
    ▼
Pydantic Validation ─────── model_validate() runs
    │                       - Type coercion
    │                       - field_validator
    │                       - model_validator
    ▼
@validates("field") ─────── Marshmallow field validators
    │
    ▼
@validates_schema ───────── Marshmallow schema validators
    │
    ▼
@post_load (Marshmallow) ── Transform result
    │
    ▼
Output (Model Instance or Dict)
```

### Key Implementation Points

**In `bridge.py`:**

1. **`_do_load()` method** - Override Marshmallow's load to insert Pydantic validation
2. **`_invoke_processors()`** - Called to run hooks at correct points
3. **`_make_model()`** - Creates Pydantic model instance from validated data

**Hook ordering in `_do_load()`:**
```python
def _do_load(self, data, ...):
    # 1. Run @pre_load hooks
    data = self._invoke_load_processors(PRE_LOAD, data, ...)

    # 2. Pydantic validation (creates model or validates dict)
    result = self._validate_with_pydantic(data)

    # 3. Run @validates("field") hooks
    self._validate_fields(result)

    # 4. Run @validates_schema hooks
    self._validate_schema(result)

    # 5. Run @post_load hooks
    result = self._invoke_load_processors(POST_LOAD, result, ...)

    return result
```

---

## Error Handling

### Converting Pydantic Errors to Marshmallow Format

Pydantic errors come as:
```python
[
    {"loc": ("field", 0, "name"), "msg": "...", "type": "..."}
]
```

Marshmallow expects:
```python
{
    "field": {"0": {"name": ["error message"]}}
}
```

**Key methods:**
- `_convert_pydantic_errors()` - Convert error format
- `_loc_to_path()` - Convert tuple location to nested dict path

### BridgeValidationError

Extends Marshmallow's ValidationError with `valid_data`:

```python
class BridgeValidationError(ValidationError):
    def __init__(self, messages, valid_data=None, **kwargs):
        super().__init__(messages, **kwargs)
        self.valid_data = valid_data or {}
```

---

## Performance Considerations

### DO
- Cache field mappings at class creation (metaclass)
- Reuse schema instances
- Use `model_construct()` for partial loading (skips validation)

### DON'T
- Call `dir()` in hot paths
- Create new schemas per request
- Re-validate already-validated data

### Benchmarking

```python
# In benchmarks/
from benchmark_framework import benchmark, compare_baseline

@benchmark(iterations=1000)
def bench_simple_load():
    schema.load({"name": "test", "age": 30})
```

---

## Adding Ecosystem Integration

### 1. Create Test File

```python
# tests/compatibility/test_newtool.py
"""Tests for NewTool compatibility.

NewTool: https://github.com/example/newtool
"""

import pytest

try:
    import newtool
    HAS_NEWTOOL = True
except ImportError:
    HAS_NEWTOOL = False

pytestmark = pytest.mark.skipif(not HAS_NEWTOOL, reason="newtool not installed")


class TestNewToolCompatibility:
    def test_basic_integration(self):
        """Test basic NewTool integration."""
        pass
```

### 2. Add to pyproject.toml

```toml
[project.optional-dependencies]
newtool = ["newtool>=1.0"]
```

### 3. Update README and docs

---

## Debugging Tips

```python
# Inspect field mappings
schema = schema_for(MyModel)()
print(schema.fields)       # All Marshmallow fields
print(schema.dump_fields)  # Fields used for dump
print(schema.load_fields)  # Fields used for load

# Check Pydantic model
print(MyModel.model_fields)       # Field definitions
print(MyModel.model_config)       # Config options
print(MyModel.model_json_schema()) # JSON schema
```
