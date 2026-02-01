# Examples

Complete examples demonstrating pydantic-marshmallow features.

## Basic Schema Creation

```python
from pydantic import BaseModel, Field, EmailStr
from pydantic_marshmallow import schema_for

class User(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)

UserSchema = schema_for(User)
schema = UserSchema()

# Load and validate
user = schema.load({
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})
print(f"Loaded: {user.name}")  # "Loaded: Alice"
```

## Custom Validators

```python
from pydantic import BaseModel, Field, field_validator
from pydantic_marshmallow import schema_for

class Product(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    sku: str

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        if not v.upper().startswith("SKU-"):
            raise ValueError("SKU must start with 'SKU-'")
        return v.upper()

schema = schema_for(Product)()
product = schema.load({"name": "Widget", "price": 29.99, "sku": "SKU-12345"})
print(f"SKU: {product.sku}")  # "SKU: SKU-12345"
```

## Type Coercion

```python
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

class Config(BaseModel):
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

print(f"Count: {config.count} ({type(config.count).__name__})")
# Count: 42 (int)
```

## Nested Models

```python
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

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
    "headquarters": {"street": "123 Main St", "city": "New York"},
    "offices": [
        {"street": "456 Tech Blvd", "city": "San Francisco"},
        {"street": "789 Innovation Dr", "city": "Boston"}
    ]
})

print(f"HQ: {company.headquarters.city}")  # "HQ: New York"
print(f"Offices: {[o.city for o in company.offices]}")
# Offices: ['San Francisco', 'Boston']
```

## HybridModel

```python
from pydantic import Field
from pydantic_marshmallow import HybridModel

class Order(HybridModel):
    order_id: str
    customer: str
    total: float = Field(ge=0)
    items: list[str] = []

# Use as Pydantic model
order = Order(
    order_id="ORD-001",
    customer="Alice",
    total=99.99,
    items=["Widget", "Gadget"]
)

# Pydantic methods
print(order.model_dump())

# Marshmallow methods
print(order.ma_dump())
json_str = order.ma_dumps()

# Load via Marshmallow
order2 = Order.ma_load({"order_id": "ORD-002", "customer": "Bob", "total": 149.99})
```

## Batch Loading

```python
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

class Task(BaseModel):
    title: str
    done: bool = False

schema = schema_for(Task)(many=True)

tasks = schema.load([
    {"title": "Write code", "done": True},
    {"title": "Write tests", "done": True},
    {"title": "Deploy", "done": False}
])

for task in tasks:
    status = "✓" if task.done else "○"
    print(f"  {status} {task.title}")
```

## JSON Serialization

```python
from datetime import datetime
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

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
```

## Computed Fields

```python
from pydantic import BaseModel, computed_field
from pydantic_marshmallow import schema_for

class User(BaseModel):
    first: str
    last: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

schema = schema_for(User)()
user = User(first="Alice", last="Smith")
data = schema.dump(user)
print(data)
# {'first': 'Alice', 'last': 'Smith', 'full_name': 'Alice Smith'}
```
