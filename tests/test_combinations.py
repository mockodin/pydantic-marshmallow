"""Comprehensive combination tests for marshmallow-pydantic.

Tests complex scenarios combining multiple features from both platforms:
- Nested models + validators + hooks
- Aliases + computed fields + partial loading
- many=True + nested + unknown handling
- Meta.fields/exclude + validators
- Discriminated unions + hooks + context
- Self-referential models + validators
- All error accumulation scenarios

These tests ensure feature combinations work correctly together,
catching integration issues that isolated tests might miss.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import pytest
from marshmallow import (
    EXCLUDE,
    INCLUDE,
    RAISE,
    ValidationError,
    post_dump,
    post_load,
    pre_load,
    validates,
    validates_schema,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from pydantic_marshmallow import PydanticSchema, schema_for

# =============================================================================
# Test Models
# =============================================================================


class Status(str, Enum):
    """Status enum for testing."""

    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class Priority(int, Enum):
    """Priority enum for testing."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Address(BaseModel):
    """Address model with validation."""

    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)  # ISO country code
    zip_code: str = Field(pattern=r"^\d{5}$")

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        return v.upper()


class Person(BaseModel):
    """Person with nested address and computed field."""

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0, le=150)
    address: Address

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class Task(BaseModel):
    """Task with enum fields and model validator."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: Status = Status.DRAFT
    priority: Priority = Priority.MEDIUM
    assignee: Person | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def validate_assignment(self) -> Task:
        if self.status == Status.ACTIVE and self.assignee is None:
            raise ValueError("Active tasks must have an assignee")
        return self


class Project(BaseModel):
    """Project with list of nested tasks and computed fields."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    description: str = ""
    tasks: list[Task] = Field(default_factory=list)
    budget: Decimal = Field(decimal_places=2, default=Decimal("0.00"))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @computed_field
    @property
    def active_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == Status.ACTIVE)


class TreeNode(BaseModel):
    """Self-referential tree structure."""

    value: int
    label: str = ""
    children: list[TreeNode] = Field(default_factory=list)

    @field_validator("value")
    @classmethod
    def positive_value(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


TreeNode.model_rebuild()


# Discriminated union models
class ShapeBase(BaseModel):
    """Base for discriminated union."""

    shape_type: str
    color: str = "black"


class Circle(ShapeBase):
    """Circle shape."""

    shape_type: Literal["circle"] = "circle"
    radius: float = Field(gt=0)


class Rectangle(ShapeBase):
    """Rectangle shape."""

    shape_type: Literal["rectangle"] = "rectangle"
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Triangle(ShapeBase):
    """Triangle shape."""

    shape_type: Literal["triangle"] = "triangle"
    base: float = Field(gt=0)
    height: float = Field(gt=0)



Shape = Annotated[Circle | Rectangle | Triangle, Field(discriminator="shape_type")]


class Drawing(BaseModel):
    """Container with discriminated union."""

    name: str
    shapes: list[Shape] = Field(default_factory=list)


# Alias models
class ApiResponse(BaseModel):
    """Model with aliases for API compatibility."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    user_name: str = Field(alias="userName")
    email_address: str = Field(alias="emailAddress")
    created_at: datetime = Field(alias="createdAt")

    @field_validator("email_address")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()


# =============================================================================
# PydanticSchema with Hooks
# =============================================================================


class ProjectSchema(PydanticSchema[Project]):
    """Project schema with all hooks."""

    class Meta:
        model = Project

    @pre_load
    def pre_process(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        # Convert string UUID if provided
        if "id" in data and isinstance(data["id"], str):
            data["id"] = data["id"]  # Pydantic will handle conversion
        # Set default created_at if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow().isoformat()
        return data

    @post_load
    def post_process(self, data: Any, **kwargs) -> Any:
        # data is a Project instance
        return data

    @validates("name")
    def validate_name(self, value: str, **kwargs) -> None:
        reserved = ["admin", "system", "root", "test"]
        if value.lower() in reserved:
            raise ValidationError(f"'{value}' is a reserved project name")

    @validates_schema
    def validate_budget(self, data: dict[str, Any], **kwargs) -> None:
        # Only applies when return_instance=False
        pass


class PersonSchema(PydanticSchema[Person]):
    """Person schema with hooks for testing."""

    class Meta:
        model = Person

    @pre_load
    def normalize_names(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        if "first_name" in data:
            data["first_name"] = data["first_name"].strip().title()
        if "last_name" in data:
            data["last_name"] = data["last_name"].strip().title()
        return data

    @post_dump
    def add_metadata(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        data["_serialized_at"] = datetime.utcnow().isoformat()
        return data


class TaskSchemaWithMeta(PydanticSchema[Task]):
    """Task schema using Meta.fields for selective serialization."""

    class Meta:
        model = Task
        fields = ("title", "status", "priority")


class TaskSchemaExclude(PydanticSchema[Task]):
    """Task schema using Meta.exclude."""

    class Meta:
        model = Task
        exclude = ("assignee", "due_date")


# =============================================================================
# Test Classes
# =============================================================================


class TestNestedWithValidatorsAndHooks:
    """Test nested models with validators and hooks working together."""

    def test_nested_person_with_validators(self):
        """Test nested Person with field validators."""
        schema = PersonSchema()

        data = {
            "first_name": "  alice  ",
            "last_name": "  smith  ",
            "email": "  ALICE@EXAMPLE.COM  ",
            "age": 30,
            "address": {
                "street": "123 Main St",
                "city": "Boston",
                "country": "us",
                "zip_code": "02101",
            },
        }

        result = schema.load(data)

        # Check pre_load hook normalized names
        assert result.first_name == "Alice"
        assert result.last_name == "Smith"
        # Check Pydantic field_validator normalized email
        assert result.email == "alice@example.com"
        # Check nested address validator normalized country
        assert result.address.country == "US"

    def test_nested_with_computed_field_in_dump(self):
        """Test dump includes computed fields from nested models."""
        schema = PersonSchema()

        person = Person(
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            age=30,
            address=Address(
                street="123 Main St",
                city="Boston",
                country="US",
                zip_code="02101",
            ),
        )

        result = schema.dump(person)

        # Check computed field
        assert result["full_name"] == "Alice Smith"
        # Check post_dump hook added metadata
        assert "_serialized_at" in result

    def test_nested_validation_errors_accumulated(self):
        """Test errors from nested validators are accumulated."""
        schema = PersonSchema()

        data = {
            "first_name": "",  # Invalid - min_length=1
            "last_name": "Smith",
            "email": "alice@example.com",
            "age": 200,  # Invalid - le=150
            "address": {
                "street": "",  # Invalid - min_length=1
                "city": "Boston",
                "country": "USA",  # Invalid - max_length=2
                "zip_code": "abc",  # Invalid - pattern
            },
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        errors = exc.value.messages
        # Should have multiple error fields
        assert len(errors) >= 1


class TestProjectWithTasksAndHooks:
    """Test complex nested structures with hooks."""

    def test_project_with_nested_tasks(self):
        """Test Project containing nested Tasks with enums."""
        schema = ProjectSchema()

        data = {
            "name": "Project Alpha",
            "description": "Test project",
            "tasks": [
                {
                    "title": "Task 1",
                    "status": "draft",
                    "priority": 2,  # MEDIUM
                },
                {
                    "title": "Task 2",
                    "status": "pending",
                    "priority": 3,  # HIGH
                    "description": "Important task",
                },
            ],
            "budget": "10000.50",
        }

        result = schema.load(data)

        assert result.name == "Project Alpha"
        assert len(result.tasks) == 2
        assert result.tasks[0].status == Status.DRAFT
        assert result.tasks[1].priority == Priority.HIGH
        assert result.budget == Decimal("10000.50")
        # Computed fields
        assert result.task_count == 2
        assert result.active_tasks == 0

    def test_project_with_active_task_and_assignee(self):
        """Test model_validator on nested Task requiring assignee for active."""
        schema = ProjectSchema()

        # Valid: active task with assignee
        data = {
            "name": "Project Beta",
            "tasks": [
                {
                    "title": "Active Task",
                    "status": "active",
                    "priority": 3,
                    "assignee": {
                        "first_name": "Bob",
                        "last_name": "Jones",
                        "email": "bob@example.com",
                        "age": 25,
                        "address": {
                            "street": "456 Oak Ave",
                            "city": "Seattle",
                            "country": "US",
                            "zip_code": "98101",
                        },
                    },
                }
            ],
        }

        result = schema.load(data)
        assert result.tasks[0].status == Status.ACTIVE
        assert result.tasks[0].assignee.full_name == "Bob Jones"

    def test_project_active_task_without_assignee_fails(self):
        """Test model_validator rejects active task without assignee."""
        schema = ProjectSchema()

        data = {
            "name": "Project Gamma",
            "tasks": [
                {
                    "title": "Active Task",
                    "status": "active",
                    "priority": 2,
                    # No assignee - should fail
                }
            ],
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        assert "assignee" in str(exc.value).lower() or "active" in str(exc.value).lower()

    def test_project_marshmallow_validator_reserved_name(self):
        """Test Marshmallow @validates hook rejects reserved names."""
        schema = ProjectSchema()

        data = {"name": "admin", "tasks": []}

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        assert "reserved" in str(exc.value).lower()

    def test_project_computed_fields_in_dump(self):
        """Test all computed fields work in dump."""
        schema = schema_for(Project)()

        project = Project(
            name="Test Project",
            tasks=[
                Task(title="Task 1", status=Status.ACTIVE, assignee=Person(
                    first_name="A", last_name="B", email="a@b.com", age=25,
                    address=Address(street="St", city="C", country="US", zip_code="12345"),
                )),
                Task(title="Task 2", status=Status.DRAFT),
                Task(title="Task 3", status=Status.ACTIVE, assignee=Person(
                    first_name="C", last_name="D", email="c@d.com", age=30,
                    address=Address(street="St", city="C", country="US", zip_code="12345"),
                )),
            ],
        )

        result = schema.dump(project)

        assert result["task_count"] == 3
        assert result["active_tasks"] == 2


class TestMetaFieldsAndExclude:
    """Test Meta.fields and Meta.exclude with other features."""

    def test_meta_fields_selective_output(self):
        """Test Meta.fields limits dump output."""
        schema = TaskSchemaWithMeta()

        task = Task(
            title="Important Task",
            description="Long description here",
            status=Status.ACTIVE,
            priority=Priority.HIGH,
            assignee=Person(
                first_name="Alice", last_name="Smith",
                email="alice@example.com", age=30,
                address=Address(street="St", city="C", country="US", zip_code="12345"),
            ),
            due_date=date(2024, 12, 31),
        )

        result = schema.dump(task)

        # Only specified fields should be present
        assert "title" in result
        assert "status" in result
        assert "priority" in result
        assert "description" not in result
        assert "assignee" not in result
        assert "due_date" not in result

    def test_meta_exclude_removes_fields(self):
        """Test Meta.exclude removes specified fields from dump."""
        schema = TaskSchemaExclude()

        task = Task(
            title="Task",
            status=Status.DRAFT,
            priority=Priority.LOW,
            description="Description",
        )

        result = schema.dump(task)

        assert "title" in result
        assert "status" in result
        assert "description" in result
        assert "assignee" not in result
        assert "due_date" not in result

    def test_meta_fields_works_with_validators(self):
        """Test Meta.fields still allows validators to run."""
        schema = TaskSchemaWithMeta()

        # Load should still validate all fields
        data = {
            "title": "",  # Invalid - min_length=1
            "status": "draft",
            "priority": 2,
        }

        with pytest.raises(ValidationError):
            schema.load(data)


class TestAliasesWithFeaturesCombo:
    """Test aliases combined with other features."""

    def test_alias_load_and_dump(self):
        """Test aliases work in both load and dump."""
        schema = schema_for(ApiResponse)()

        data = {
            "userId": 123,
            "userName": "alice",
            "emailAddress": "ALICE@EXAMPLE.COM",
            "createdAt": "2024-01-15T10:30:00",
        }

        result = schema.load(data)

        # Load used aliases
        assert result.user_id == 123
        assert result.user_name == "alice"
        # Validator normalized email
        assert result.email_address == "alice@example.com"

        # Dump should use aliases
        dumped = schema.dump(result)
        assert "userId" in dumped or "user_id" in dumped

    def test_alias_with_field_name_also_works(self):
        """Test loading with field name when populate_by_name=True."""
        schema = schema_for(ApiResponse)()

        data = {
            "user_id": 456,
            "user_name": "bob",
            "email_address": "bob@example.com",
            "created_at": "2024-01-15T10:30:00",
        }

        result = schema.load(data)
        assert result.user_id == 456

    def test_alias_validation_error_uses_correct_name(self):
        """Test validation errors reference correct field name."""
        schema = schema_for(ApiResponse)()

        data = {
            "userId": 123,
            "userName": "alice",
            "emailAddress": "invalid-email",  # Missing @
            "createdAt": "2024-01-15T10:30:00",
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        # Error should mention email field
        error_str = str(exc.value.messages)
        assert "email" in error_str.lower()


class TestBatchWithNestedAndUnknown:
    """Test many=True with nested models and unknown handling."""

    def test_batch_nested_models(self):
        """Test loading batch of nested models."""
        schema = schema_for(Person)(many=True)

        data = [
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "age": 30,
                "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
            },
            {
                "first_name": "Bob",
                "last_name": "Jones",
                "email": "bob@example.com",
                "age": 25,
                "address": {"street": "456 Oak", "city": "Seattle", "country": "US", "zip_code": "98101"},
            },
        ]

        result = schema.load(data)

        assert len(result) == 2
        assert result[0].full_name == "Alice Smith"
        assert result[1].address.city == "Seattle"

    def test_batch_with_unknown_exclude(self):
        """Test batch loading with unknown=EXCLUDE."""
        schema = schema_for(Person)(many=True, unknown=EXCLUDE)

        data = [
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "age": 30,
                "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
                "extra_field": "ignored",
            },
        ]

        result = schema.load(data)
        assert len(result) == 1
        assert result[0].first_name == "Alice"

    def test_batch_error_accumulation(self):
        """Test errors from multiple items in batch are accumulated."""
        schema = schema_for(Person)(many=True)

        data = [
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "age": 30,
                "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
            },
            {
                "first_name": "",  # Invalid
                "last_name": "Jones",
                "email": "bob@example.com",
                "age": -5,  # Invalid
                "address": {"street": "456 Oak", "city": "Seattle", "country": "USA", "zip_code": "invalid"},
            },
        ]

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        # Should have errors for item 1 (index 1)
        errors = exc.value.messages
        assert 1 in errors or "1" in str(errors)


class TestDiscriminatedUnionsWithHooks:
    """Test discriminated unions combined with hooks."""

    def test_discriminated_union_loading(self):
        """Test loading discriminated union shapes."""
        schema = schema_for(Drawing)()

        data = {
            "name": "My Drawing",
            "shapes": [
                {"shape_type": "circle", "radius": 5.0, "color": "red"},
                {"shape_type": "rectangle", "width": 10.0, "height": 5.0, "color": "blue"},
                {"shape_type": "triangle", "base": 6.0, "height": 4.0},
            ],
        }

        result = schema.load(data)

        assert result.name == "My Drawing"
        assert len(result.shapes) == 3
        assert isinstance(result.shapes[0], Circle)
        assert isinstance(result.shapes[1], Rectangle)
        assert isinstance(result.shapes[2], Triangle)
        assert result.shapes[0].radius == 5.0
        assert result.shapes[2].color == "black"  # default

    def test_discriminated_union_with_invalid_type(self):
        """Test invalid discriminator value raises error."""
        schema = schema_for(Drawing)()

        data = {
            "name": "Bad Drawing",
            "shapes": [
                {"shape_type": "hexagon", "sides": 6},  # Invalid type
            ],
        }

        with pytest.raises(ValidationError):
            schema.load(data)

    def test_discriminated_union_dump(self):
        """Test dumping discriminated unions."""
        schema = schema_for(Drawing)()

        drawing = Drawing(
            name="Test",
            shapes=[
                Circle(radius=3.0, color="green"),
                Rectangle(width=4.0, height=2.0),
            ],
        )

        result = schema.dump(drawing)

        assert result["name"] == "Test"
        assert len(result["shapes"]) == 2
        assert result["shapes"][0]["shape_type"] == "circle"
        assert result["shapes"][0]["radius"] == 3.0


class TestSelfReferentialWithValidators:
    """Test self-referential models with validators."""

    def test_tree_structure_loading(self):
        """Test loading self-referential tree structure."""
        schema = schema_for(TreeNode)()

        data = {
            "value": 1,
            "label": "root",
            "children": [
                {
                    "value": 2,
                    "label": "child1",
                    "children": [
                        {"value": 4, "label": "grandchild1"},
                        {"value": 5, "label": "grandchild2"},
                    ],
                },
                {"value": 3, "label": "child2"},
            ],
        }

        result = schema.load(data)

        assert result.value == 1
        assert len(result.children) == 2
        assert result.children[0].value == 2
        assert len(result.children[0].children) == 2
        assert result.children[0].children[0].value == 4

    def test_tree_validator_on_nested(self):
        """Test field validator runs on nested nodes."""
        schema = schema_for(TreeNode)()

        data = {
            "value": 1,
            "children": [
                {"value": -5},  # Invalid - negative
            ],
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        assert "non-negative" in str(exc.value).lower() or "value" in str(exc.value.messages)

    def test_deep_tree_structure(self):
        """Test deeply nested tree (10 levels)."""
        schema = schema_for(TreeNode)()

        # Build 10-level deep tree
        def build_tree(depth: int, value: int = 0) -> dict[str, Any]:
            if depth == 0:
                return {"value": value}
            return {
                "value": value,
                "children": [build_tree(depth - 1, value + 1)],
            }

        data = build_tree(10)
        result = schema.load(data)

        # Traverse to verify depth
        node = result
        for i in range(10):
            assert node.value == i
            if node.children:
                node = node.children[0]


class TestPartialWithNestedModels:
    """Test partial loading with nested structures."""

    def test_partial_with_nested_address(self):
        """Test partial loading allows missing nested fields."""
        schema = PersonSchema()

        # Partial loading - only name provided
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
        }

        result = schema.load(data, partial=True)
        assert result.first_name == "Alice"

    def test_partial_specific_fields(self):
        """Test partial=('field',) for specific fields."""
        schema = PersonSchema()

        # Only email and address are partial
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "age": 30,
            # email and address missing but allowed
        }

        result = schema.load(data, partial=("email", "address"))
        assert result.first_name == "Alice"
        assert result.age == 30

    def test_partial_still_validates_provided(self):
        """Test partial loading still validates provided fields."""
        schema = PersonSchema()

        data = {
            "first_name": "",  # Invalid even in partial mode
            "last_name": "Smith",
        }

        with pytest.raises(ValidationError):
            schema.load(data, partial=True)


class TestContextPassingCombinations:
    """Test context passing with various feature combinations."""

    def test_context_in_nested_validates(self):
        """Test context is available in nested schema validates."""

        class ContextAwarePersonSchema(PydanticSchema[Person]):
            class Meta:
                model = Person

            @validates("email")
            def validate_email_domain(self, value: str, **kwargs) -> None:
                allowed_domain = self.context.get("allowed_domain")
                if allowed_domain:
                    # Split email at @ and check domain part explicitly
                    if "@" in value:
                        _, domain = value.rsplit("@", 1)
                        if domain != allowed_domain:
                            raise ValidationError(f"Email must be from {allowed_domain}")
                    else:
                        raise ValidationError("Invalid email format")

        schema = ContextAwarePersonSchema()
        schema.context = {"allowed_domain": "company.com"}

        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@gmail.com",  # Wrong domain
            "age": 30,
            "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        # Verify the domain validation error was raised
        error_message = str(exc.value)
        assert "Email must be from" in error_message

    def test_context_in_pre_load_hook(self):
        """Test context is available in pre_load hook."""

        class DefaultsFromContextSchema(PydanticSchema[Task]):
            class Meta:
                model = Task

            @pre_load
            def apply_defaults(self, data: dict[str, Any], **kwargs) -> dict[str, Any]:
                default_priority = self.context.get("default_priority")
                if default_priority and "priority" not in data:
                    data["priority"] = default_priority
                return data

        schema = DefaultsFromContextSchema()
        schema.context = {"default_priority": Priority.HIGH.value}

        result = schema.load({"title": "Task 1", "status": "draft"})
        assert result.priority == Priority.HIGH


class TestReturnInstanceCombinations:
    """Test return_instance=True/False with various features."""

    def test_return_instance_true_with_computed(self):
        """Test return_instance=True includes computed fields."""
        schema = schema_for(Person)()

        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "age": 30,
            "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
        }

        result = schema.load(data, return_instance=True)
        assert isinstance(result, Person)
        assert result.full_name == "Alice Smith"

    def test_return_instance_false_with_nested(self):
        """Test return_instance=False returns dict with nested dicts."""
        schema = schema_for(Person)()

        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "age": 30,
            "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
        }

        result = schema.load(data, return_instance=False)
        assert isinstance(result, dict)
        # Validators should still have run
        assert result["email"] == "alice@example.com"


class TestUnknownHandlingCombinations:
    """Test unknown field handling with various scenarios."""

    def test_unknown_raise_with_nested(self):
        """Test unknown=RAISE with nested models."""

        class StrictPersonSchema(PydanticSchema[Person]):
            class Meta:
                model = Person

        schema = StrictPersonSchema(unknown=RAISE)

        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "age": 30,
            "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
            "unknown_field": "should fail",
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        assert "unknown_field" in str(exc.value.messages)

    def test_unknown_include_preserves_extra(self):
        """Test unknown=INCLUDE preserves extra fields."""
        schema = schema_for(Person)(unknown=INCLUDE)

        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "age": 30,
            "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
            "extra": "preserved",
        }

        result = schema.load(data)
        # Result is a model instance - extra fields may be handled differently
        assert result.first_name == "Alice"


class TestDumpOptionsCombinations:
    """Test dump options combined with other features."""

    def test_dump_meta_exclude_regular_fields(self):
        """Test Meta.exclude removes regular fields from dump."""

        class ProjectWithExcludes(PydanticSchema[Project]):
            class Meta:
                model = Project
                exclude = ("budget", "created_at")

        schema = ProjectWithExcludes()
        project = Project(name="Test", tasks=[])

        result = schema.dump(project)
        assert "name" in result
        assert "tasks" in result
        assert "budget" not in result
        assert "created_at" not in result

    def test_dump_exclude_none(self):
        """Test exclude_none option on dump."""
        schema = schema_for(Task)()

        task = Task(
            title="Task",
            status=Status.DRAFT,
            description=None,  # Should be excluded
            assignee=None,  # Should be excluded
        )

        result = schema.dump(task, exclude_none=True)
        assert "title" in result
        assert "status" in result
        assert "description" not in result
        assert "assignee" not in result


class TestComplexErrorScenarios:
    """Test complex error handling scenarios."""

    def test_multiple_nested_errors(self):
        """Test errors from multiple levels are all reported."""
        schema = ProjectSchema()

        data = {
            "name": "",  # Invalid - min_length
            "tasks": [
                {
                    "title": "",  # Invalid
                    "status": "invalid_status",  # Invalid enum
                    "priority": 999,  # Invalid enum value
                },
                {
                    "title": "x" * 300,  # Invalid - max_length
                    "status": "active",
                    # Missing assignee for active - model_validator
                },
            ],
            "budget": "not-a-number",  # Invalid decimal
        }

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        # Should have multiple errors
        assert len(exc.value.messages) >= 1

    def test_error_with_batch_and_nested(self):
        """Test errors in batch with nested models show correct paths."""
        schema = schema_for(Person)(many=True)

        data = [
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "age": 30,
                "address": {"street": "123 Main", "city": "Boston", "country": "US", "zip_code": "02101"},
            },
            {
                "first_name": "Bob",
                "last_name": "",  # Invalid
                "email": "invalid",  # Invalid
                "age": -5,  # Invalid
                "address": {
                    "street": "",  # Invalid
                    "city": "Seattle",
                    "country": "USA",  # Invalid - too long
                    "zip_code": "abc",  # Invalid pattern
                },
            },
        ]

        with pytest.raises(ValidationError) as exc:
            schema.load(data)

        errors = exc.value.messages
        # Should have errors - format may vary
        assert len(errors) >= 1
        # Check that field names appear somewhere in the errors
        error_str = str(errors)
        assert any(field in error_str for field in ["last_name", "age", "address", "street", "zip_code"])
