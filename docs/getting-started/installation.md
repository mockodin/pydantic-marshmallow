# Installation

## Requirements

- Python 3.9+
- pydantic >= 2.0.0
- marshmallow >= 3.18.0

## Install from PyPI

```bash
pip install pydantic-marshmallow
```

## Install with Optional Dependencies

For development and testing:

```bash
pip install pydantic-marshmallow[dev]
```

This includes:

- pytest, pytest-cov for testing
- mypy for type checking
- ruff for linting
- Integration testing dependencies (flask-marshmallow, webargs, apispec, etc.)

## Install from Source

```bash
git clone https://github.com/mockodin/pydantic-marshmallow.git
cd pydantic-marshmallow
pip install -e ".[dev]"
```

## Verify Installation

```python
from pydantic_marshmallow import schema_for, PydanticSchema
print("Installation successful!")
```
