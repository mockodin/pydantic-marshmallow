---
applyTo: '**/*.py'
---

# Test Coverage Requirements

## Setup

```bash
# Run tests with coverage
pytest tests/ --cov=pydantic_marshmallow --cov-report=term-missing

# Generate HTML report
pytest tests/ --cov=pydantic_marshmallow --cov-report=html
# Open htmlcov/index.html
```

## Coverage Targets

### Overall Coverage
- **Minimum**: All tests must pass
- **Target**: ≥90% line coverage for core bridge code
- PRs must not decrease overall coverage

### Per-Module Coverage
| Module | Target | Notes |
|:-------|:------:|:------|
| `bridge.py` | ≥90% | Core functionality, critical |
| `type_mapping.py` | ≥85% | Type conversion logic |
| `errors.py` | ≥80% | Error handling utilities |
| `validators.py` | ≥80% | Validator decorators |

### New Code Requirements
- **All new code must have tests** - no exceptions
- New type mappings require tests in `test_edge_cases.py`
- New hooks require tests in `test_hooks.py` or `test_advanced_hooks.py`
- Error paths require tests that trigger them

## Testing Patterns

### Schema Load/Dump Tests
```python
def test_feature_load(self):
    """Test loading with [feature]."""
    class Model(BaseModel):
        field: str

    schema = schema_for(Model)()
    result = schema.load({"field": "value"})

    assert isinstance(result, Model)
    assert result.field == "value"

def test_feature_dump(self):
    """Test dumping with [feature]."""
    model = Model(field="value")
    result = schema.dump(model)

    assert result == {"field": "value"}
```

### Validation Error Tests
```python
def test_validation_error(self):
    """Test validation error for [scenario]."""
    schema = schema_for(Model)()

    with pytest.raises(ValidationError) as exc:
        schema.load({"field": "invalid"})

    assert "field" in exc.value.messages
```

### Parameterized Tests
```python
@pytest.mark.parametrize("input_value,expected", [
    ("123", 123),
    (123, 123),
    ("0", 0),
])
def test_type_coercion(self, input_value, expected):
    """Test type coercion for various inputs."""
    result = schema.load({"value": input_value})
    assert result.value == expected
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures (schemas, models)
├── test_bridge.py           # Core schema load/dump tests
├── test_hooks.py            # Marshmallow hook tests
├── test_advanced_hooks.py   # Complex hook scenarios
├── test_validation.py       # Pydantic validation constraints
├── test_edge_cases.py       # Type edge cases
├── test_combinations.py     # Feature combinations
├── test_error_handling.py   # Error behavior tests
├── test_performance.py      # Performance benchmarks
├── test_compatibility.py    # Marshmallow/Pydantic version compatibility
├── test_computed_fields.py  # Pydantic computed_field support
├── test_dump_options.py     # Dump configuration tests
├── test_partial_and_unknown.py # Partial loading, unknown fields
└── test_sqlalchemy_integration.py # SQLAlchemy integration tests
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_bridge.py -v

# Specific test
pytest tests/test_bridge.py::TestPydanticSchemaBasic::test_from_model_basic -v

# With coverage for specific module
pytest tests/ --cov=pydantic_marshmallow.bridge --cov-report=term-missing
```
