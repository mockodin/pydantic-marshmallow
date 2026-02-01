# Changelog

All notable changes to pydantic-marshmallow will be documented here.

## [Unreleased]

### Added
- Initial release
- `PydanticSchema` class for bridging Pydantic models with Marshmallow
- `schema_for()` factory function
- `@pydantic_schema` decorator
- `HybridModel` for dual Pydantic/Marshmallow API
- Full Marshmallow hook support (`@pre_load`, `@post_load`, `@pre_dump`, `@post_dump`)
- Custom validators (`@validates`, `@validates_schema`)
- Partial loading support
- Unknown field handling (RAISE, EXCLUDE, INCLUDE)
- Field filtering (only, exclude, load_only, dump_only)
- Computed field support
- Nested model support
- Type coercion via Pydantic
- `BridgeValidationError` with valid_data support
- Dump options (exclude_none, exclude_unset, exclude_defaults)

### Ecosystem Compatibility
- Flask-Marshmallow
- webargs
- apispec
- flask-smorest
- flask-rebar
- marshmallow-sqlalchemy
- marshmallow-dataclass
- marshmallow-oneofschema
- connexion

## [0.1.0] - TBD

Initial release.
