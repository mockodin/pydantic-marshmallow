---
applyTo: '**/*.py'
---

# pydantic-marshmallow Development Guidelines

## Project Overview

This is a **pure Python library** that bridges Pydantic models with the Marshmallow ecosystem:
- **Input**: Pydantic models with validators
- **Output**: Marshmallow-compatible schemas
- **Value**: Use Pydantic's Rust-powered validation with Flask-Rebar, webargs, apispec, etc.

## Quick Start

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Test
pytest tests/ -v

# Type check
mypy src/

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## Pre-Commit Verification

**Before committing:** Run `pytest tests/ -v && mypy src/ && ruff check src/ tests/`

See [Git.instructions.md](Git.instructions.md) for full CI/CD workflow.

## Architecture

```
src/pydantic_marshmallow/
├── __init__.py         # Public API exports
├── bridge.py           # Core PydanticSchema, schema_for(), HybridModel
├── field_conversion.py # Advanced field conversion logic
├── type_mapping.py     # Python types → Marshmallow fields
├── validators.py       # Validator decorator utilities
└── errors.py           # BridgeValidationError

tests/
├── conftest.py         # Shared fixtures
├── test_bridge.py      # Core schema tests
├── test_hooks.py       # Marshmallow hook tests
├── test_validation.py  # Validation constraint tests
├── test_compatibility.py # Version compatibility tests
└── test_*.py           # Other test modules

benchmarks/
├── benchmark_framework.py  # Statistical benchmarking utilities
├── run_benchmarks.py       # CLI for running benchmarks
```

## Code Quality Standards

### Type Annotations
- **All** functions and methods must have type hints
- Use modern syntax: `list[str]` not `List[str]`, `str | None` not `Optional[str]`
- Use `from __future__ import annotations` for forward references

### Docstrings
Use Google-style docstrings:
```python
def function_name(param: str) -> bool:
    """Brief description.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.

    Raises:
        ValueError: When parameter is invalid.
    """
```

### Naming Conventions
- `snake_case` for functions, variables, module names
- `PascalCase` for class names
- `UPPER_CASE` for constants
- Prefix private methods with `_`

### Testing Requirements
- **All new code must have tests**
- Test both success and error cases
- Use `pytest.raises()` for exception testing
- Use parameterized tests for multiple similar cases

## Key Implementation Details

### Hook Ordering (Critical)
```
Input → @pre_load → PYDANTIC VALIDATES → @validates → @validates_schema → @post_load → Output
```

### PydanticSchemaMeta
Custom metaclass that adds Pydantic fields BEFORE Marshmallow processes Meta.fields/exclude.
This ensures field filtering works correctly with dynamically generated fields.

### Error Handling
- Convert Pydantic ValidationError → Marshmallow ValidationError format
- Preserve field paths: `loc` tuple → dotted path (e.g., "items.0.name")
- Include `valid_data` for partial success scenarios

## Common Tasks

### Adding a New Pydantic Type Mapping
1. Edit `type_mapping.py`
2. Add case in `_type_to_marshmallow_field()`
3. Add test in `tests/test_edge_cases.py`

### Adding a New Marshmallow Hook
1. Ensure hook is called in `_do_load()` in `bridge.py`
2. Add test in `tests/test_hooks.py` or `tests/test_advanced_hooks.py`

### Adding Ecosystem Integration
1. Add test in `tests/test_compatibility.py` or create dedicated test file
2. Update README.md with usage example
3. Add optional dependency to `pyproject.toml` if needed

## Dependencies

**Runtime:**
- pydantic >= 2.0
- marshmallow >= 3.18

**Development:**
- pytest, pytest-cov
- mypy
- ruff
