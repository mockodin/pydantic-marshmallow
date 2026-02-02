"""
Example: Using marshmallow-pydantic

This example shows how to use Pydantic models with Marshmallow's ecosystem.
"""

from datetime import datetime

from marshmallow import ValidationError
from pydantic import BaseModel, EmailStr, Field, field_validator

from pydantic_marshmallow import HybridModel, schema_for

# =============================================================================
# Example 1: Basic Usage with schema_for()
# =============================================================================

print("=" * 60)
print("Example 1: Basic Usage")
print("=" * 60)


class User(BaseModel):
    """A user model with Pydantic validation."""
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)


# Create a Marshmallow schema from the Pydantic model
UserSchema = schema_for(User)
schema = UserSchema()

# Load and validate data - Pydantic validation runs!
user = schema.load({
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})

print(f"Loaded user: {user}")
print(f"Type: {type(user)}")  # It's a User instance!
print(f"Name: {user.name}")
print()


# =============================================================================
# Example 2: Pydantic Validation in Action
# =============================================================================

print("=" * 60)
print("Example 2: Pydantic Validation")
print("=" * 60)


class Product(BaseModel):
    """Product with custom validator."""
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    sku: str

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        if not v.upper().startswith("SKU-"):
            raise ValueError("SKU must start with 'SKU-'")
        return v.upper()


ProductSchema = schema_for(Product)
schema = ProductSchema()

# Valid product - custom validator transforms SKU
product = schema.load({
    "name": "Widget",
    "price": 29.99,
    "sku": "SKU-12345"
})
print(f"Product SKU: {product.sku}")  # SKU-12345 (uppercased by validator)

# Invalid product - Pydantic validation catches it
try:
    schema.load({"name": "", "price": -5, "sku": "invalid"})
except ValidationError as e:
    print(f"Validation errors: {e.messages}")
print()


# =============================================================================
# Example 3: Type Coercion
# =============================================================================

print("=" * 60)
print("Example 3: Type Coercion")
print("=" * 60)


class Config(BaseModel):
    """Config with type coercion."""
    count: int
    enabled: bool
    threshold: float


schema = schema_for(Config)()

# Pydantic coerces strings to proper types
config = schema.load({
    "count": "42",        # string -> int
    "enabled": "true",    # string -> bool
    "threshold": "0.75"   # string -> float
})

print(f"Count: {config.count} (type: {type(config.count).__name__})")
print(f"Enabled: {config.enabled} (type: {type(config.enabled).__name__})")
print(f"Threshold: {config.threshold} (type: {type(config.threshold).__name__})")
print()


# =============================================================================
# Example 4: Nested Models
# =============================================================================

print("=" * 60)
print("Example 4: Nested Models")
print("=" * 60)


class Address(BaseModel):
    street: str
    city: str
    country: str = "USA"


class Company(BaseModel):
    name: str
    headquarters: Address
    offices: list[Address] = []


schema = schema_for(Company)()

company = schema.load({
    "name": "Acme Inc",
    "headquarters": {
        "street": "123 Main St",
        "city": "New York"
    },
    "offices": [
        {"street": "456 Tech Blvd", "city": "San Francisco"},
        {"street": "789 Innovation Dr", "city": "Boston"}
    ]
})

print(f"Company: {company.name}")
print(f"HQ: {company.headquarters.city}")
print(f"Offices: {[o.city for o in company.offices]}")
print()


# =============================================================================
# Example 5: HybridModel - Best of Both Worlds
# =============================================================================

print("=" * 60)
print("Example 5: HybridModel")
print("=" * 60)


class Order(HybridModel):
    """Order model that works as both Pydantic and Marshmallow."""
    order_id: str
    customer: str
    total: float = Field(ge=0)
    items: list[str] = Field(default_factory=list)


# Use as a Pydantic model
order = Order(
    order_id="ORD-001",
    customer="Alice",
    total=99.99,
    items=["Widget", "Gadget"]
)
print(f"Created order: {order.order_id}")

# Use Pydantic methods
print(f"Pydantic dump: {order.model_dump()}")

# Use Marshmallow methods
print(f"Marshmallow dump: {order.ma_dump()}")

# Load via Marshmallow
order2 = Order.ma_load({
    "order_id": "ORD-002",
    "customer": "Bob",
    "total": 149.99
})
print(f"Loaded order: {order2.order_id}")

# Get the schema class for ecosystem integration
OrderSchema = Order.marshmallow_schema()
print(f"Schema class: {OrderSchema}")
print()


# =============================================================================
# Example 6: JSON Serialization
# =============================================================================

print("=" * 60)
print("Example 6: JSON Serialization")
print("=" * 60)


class Event(BaseModel):
    name: str
    date: datetime
    attendees: int = 0


schema = schema_for(Event)()

# Load from JSON string
event = schema.loads('{"name": "Conference", "date": "2024-06-15T09:00:00", "attendees": 500}')
print(f"Event: {event.name} on {event.date}")

# Dump to JSON string
json_str = schema.dumps(event)
print(f"JSON: {json_str}")
print()


# =============================================================================
# Example 7: Many/Batch Loading
# =============================================================================

print("=" * 60)
print("Example 7: Batch Loading")
print("=" * 60)


class Task(BaseModel):
    title: str
    done: bool = False


schema = schema_for(Task)(many=True)

tasks = schema.load([
    {"title": "Write code", "done": True},
    {"title": "Write tests", "done": True},
    {"title": "Deploy", "done": False}
])

print(f"Loaded {len(tasks)} tasks")
for task in tasks:
    status = "✓" if task.done else "○"
    print(f"  {status} {task.title}")
print()


print("=" * 60)
print("All examples completed!")
print("=" * 60)
