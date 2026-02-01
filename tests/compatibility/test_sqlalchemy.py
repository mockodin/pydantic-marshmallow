"""
Tests for marshmallow-sqlalchemy integration.

Verifies that PydanticSchema works correctly alongside marshmallow-sqlalchemy
and in typical SQLAlchemy application patterns.
"""

import pytest
from marshmallow import Schema
from pydantic import BaseModel, Field

from pydantic_marshmallow import PydanticSchema, schema_for

# Third-party imports with conditional availability
try:
    from sqlalchemy import Column, Float, ForeignKey, Integer, String, create_engine
    from sqlalchemy.orm import Session, declarative_base, relationship

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

try:
    from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, SQLAlchemySchema

    MARSHMALLOW_SQLALCHEMY_AVAILABLE = SQLALCHEMY_AVAILABLE
except ImportError:
    MARSHMALLOW_SQLALCHEMY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MARSHMALLOW_SQLALCHEMY_AVAILABLE,
    reason="sqlalchemy and marshmallow-sqlalchemy not installed",
)


# SQLAlchemy models
if SQLALCHEMY_AVAILABLE:
    Base = declarative_base()

    class AuthorModel(Base):
        __tablename__ = "authors"
        id = Column(Integer, primary_key=True)
        name = Column(String(100), nullable=False)
        email = Column(String(200))
        books = relationship("BookModel", back_populates="author")

    class BookModel(Base):
        __tablename__ = "books"
        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        price = Column(Float, default=0.0)
        author_id = Column(Integer, ForeignKey("authors.id"))
        author = relationship("AuthorModel", back_populates="books")


# Pydantic models (for comparison/parallel use)
class AuthorPydantic(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1)
    email: str | None = None


class BookPydantic(BaseModel):
    id: int | None = None
    title: str = Field(min_length=1)
    price: float = Field(ge=0, default=0.0)
    author_id: int | None = None


@pytest.fixture
def engine():
    """Create an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a database session."""
    with Session(engine) as session:
        yield session


class TestSQLAlchemyAutoSchemaBaseline:
    """Verify SQLAlchemyAutoSchema works normally (baseline)."""

    def test_auto_schema_dump(self, session):
        """SQLAlchemyAutoSchema can dump ORM objects."""

        class AuthorSchema(SQLAlchemyAutoSchema):
            class Meta:
                model = AuthorModel
                include_relationships = True
                load_instance = True

        author = AuthorModel(name="Test Author", email="test@example.com")
        session.add(author)
        session.commit()

        schema = AuthorSchema()
        result = schema.dump(author)

        assert result["name"] == "Test Author"
        assert result["email"] == "test@example.com"
        assert "id" in result

    def test_auto_schema_load(self, session):
        """SQLAlchemyAutoSchema can load data into ORM objects."""

        class AuthorSchema(SQLAlchemyAutoSchema):
            class Meta:
                model = AuthorModel
                include_relationships = True
                load_instance = True
                sqla_session = session

        schema = AuthorSchema()
        author = schema.load({"name": "New Author", "email": "new@example.com"})

        assert isinstance(author, AuthorModel)
        assert author.name == "New Author"


class TestPydanticSchemaAlongsideSQLAlchemy:
    """Test PydanticSchema working alongside SQLAlchemy schemas."""

    def test_both_schemas_in_same_module(self, session):
        """PydanticSchema and SQLAlchemyAutoSchema can coexist."""

        # SQLAlchemy schema for ORM
        class AuthorSQLSchema(SQLAlchemyAutoSchema):
            class Meta:
                model = AuthorModel
                load_instance = True
                sqla_session = session

        # Pydantic schema for API validation
        AuthorAPISchema = schema_for(AuthorPydantic)

        # Both work independently
        sql_schema = AuthorSQLSchema()
        api_schema = AuthorAPISchema()

        # Load via SQLAlchemy schema (creates ORM instance)
        orm_author = sql_schema.load({"name": "SQL Author"})
        assert isinstance(orm_author, AuthorModel)

        # Load via Pydantic schema (creates Pydantic model)
        pyd_author = api_schema.load({"name": "API Author"})
        assert isinstance(pyd_author, AuthorPydantic)

    def test_pydantic_schema_with_orm_data(self, session):
        """PydanticSchema can process data from ORM objects."""
        # Create ORM object
        author = AuthorModel(name="ORM Author", email="orm@example.com")
        session.add(author)
        session.commit()

        # Use Pydantic schema to validate/transform
        AuthorAPISchema = schema_for(AuthorPydantic)
        schema = AuthorAPISchema()

        # Dump ORM data to dict, then load through Pydantic
        orm_data = {"id": author.id, "name": author.name, "email": author.email}
        pyd_author = schema.load(orm_data)

        assert pyd_author.name == "ORM Author"
        assert pyd_author.email == "orm@example.com"


class TestTypeHierarchyCompatibility:
    """Test that PydanticSchema maintains proper type hierarchy."""

    def test_is_schema_subclass(self):
        """PydanticSchema is a proper Schema subclass."""
        assert issubclass(PydanticSchema, Schema)

    def test_instance_check(self):
        """PydanticSchema instances pass isinstance checks."""
        AuthorSchema = schema_for(AuthorPydantic)
        schema = AuthorSchema()
        assert isinstance(schema, Schema)

    def test_schema_class_attributes(self):
        """PydanticSchema has expected Schema class attributes."""
        AuthorSchema = schema_for(AuthorPydantic)

        # Has Meta
        assert hasattr(AuthorSchema, "Meta")
        # Has fields
        assert hasattr(AuthorSchema, "_declared_fields")
        # Has load/dump methods
        assert hasattr(AuthorSchema, "load")
        assert hasattr(AuthorSchema, "dump")
        assert hasattr(AuthorSchema, "loads")
        assert hasattr(AuthorSchema, "dumps")


class TestMixedWorkflows:
    """Test common mixed ORM/API validation workflows."""

    def test_api_input_to_orm(self, session):
        """Validate API input with Pydantic, then create ORM object."""
        # Validate incoming API data
        AuthorAPISchema = schema_for(AuthorPydantic)
        api_schema = AuthorAPISchema()

        validated = api_schema.load(
            {"name": "API Input Author", "email": "api@example.com"}
        )

        # Create ORM object from validated data
        orm_author = AuthorModel(name=validated.name, email=validated.email)
        session.add(orm_author)
        session.commit()

        assert orm_author.id is not None
        assert orm_author.name == "API Input Author"

    def test_orm_output_to_api(self, session):
        """Fetch ORM object, serialize through Pydantic schema."""
        # Create ORM object
        author = AuthorModel(name="DB Author", email="db@example.com")
        session.add(author)
        session.commit()

        # Serialize through Pydantic schema for API response
        AuthorAPISchema = schema_for(AuthorPydantic)
        schema = AuthorAPISchema()

        # Create Pydantic model from ORM data
        pyd_author = AuthorPydantic(
            id=author.id, name=author.name, email=author.email
        )

        # Dump for API response
        response = schema.dump(pyd_author)

        assert response["name"] == "DB Author"
        assert response["email"] == "db@example.com"

    def test_validation_before_orm_save(self, session):
        """Use Pydantic validation before saving to database."""
        AuthorAPISchema = schema_for(AuthorPydantic)
        schema = AuthorAPISchema()

        # Invalid data should be rejected
        from pydantic_marshmallow import BridgeValidationError

        with pytest.raises(BridgeValidationError):
            schema.load({"name": ""})  # min_length=1 violation

        # Valid data passes
        validated = schema.load({"name": "Valid Author"})
        assert validated.name == "Valid Author"


class TestNestedSchemas:
    """Test nested schema scenarios."""

    def test_pydantic_nested_models(self, session):
        """Pydantic schema with nested models works."""

        class BookWithAuthor(BaseModel):
            title: str
            author: AuthorPydantic

        BookWithAuthorSchema = schema_for(BookWithAuthor)
        schema = BookWithAuthorSchema()

        result = schema.load(
            {"title": "Great Book", "author": {"name": "Great Author"}}
        )

        assert result.title == "Great Book"
        assert result.author.name == "Great Author"
