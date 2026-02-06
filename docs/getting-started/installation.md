# Installation

## Requirements

- Python 3.10+
- pydantic >= 2.0.0
- marshmallow >= 3.18.0 (3.x and 4.x supported)

## Marshmallow Version Compatibility

pydantic-marshmallow supports both Marshmallow 3.x and 4.x. The library
automatically detects the installed version and adapts its behavior:

| Marshmallow | Status | Notes |
|-------------|--------|-------|
| 3.18.0+ | ✅ Supported | Full compatibility |
| 4.0.0+ | ✅ Supported | Adapts to API changes (e.g., `context` parameter removal) |

!!! note "Upgrading Marshmallow"
    When upgrading from Marshmallow 3.x to 4.x, consult the
    [Marshmallow migration guide](https://marshmallow.readthedocs.io/en/stable/upgrading.html)
    for breaking changes that may affect your own code.

## Install from PyPI

=== "uv (recommended)"

    ```bash
    uv add pydantic-marshmallow
    ```

=== "pip"

    ```bash
    pip install pydantic-marshmallow
    ```

## Install with Optional Dependencies

For development and testing:

=== "uv (recommended)"

    ```bash
    uv add pydantic-marshmallow --extra dev
    ```

=== "pip"

    ```bash
    pip install pydantic-marshmallow[dev]
    ```

This includes:

- pytest, pytest-cov for testing
- mypy for type checking
- ruff for linting
- Integration testing dependencies (flask-marshmallow, webargs, apispec, etc.)

## Install from Source

=== "uv (recommended)"

    ```bash
    git clone https://github.com/mockodin/pydantic-marshmallow.git
    cd pydantic-marshmallow
    uv sync --all-extras
    ```

=== "pip"

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
