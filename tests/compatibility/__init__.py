"""
Third-party compatibility tests for pydantic-marshmallow.

These tests verify that PydanticSchema works correctly with various
Marshmallow ecosystem libraries. Each test module uses conditional
imports to skip tests when the third-party package is not installed.

Packages tested:
- flask-marshmallow: Flask integration
- webargs: Request parsing
- apispec: OpenAPI generation
- flask-rebar: Flask REST APIs with Swagger
- flask-smorest: Flask REST APIs with OpenAPI
- marshmallow-sqlalchemy: SQLAlchemy integration
- marshmallow-dataclass: Dataclass conversion
"""
