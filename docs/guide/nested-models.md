# Nested Models

pydantic-marshmallow fully supports nested Pydantic models.

## Basic Nesting

```python
from pydantic import BaseModel
from pydantic_marshmallow import schema_for

class Address(BaseModel):
    street: str
    city: str
    country: str = "USA"

class User(BaseModel):
    name: str
    address: Address

schema = schema_for(User)()

user = schema.load({
    "name": "Alice",
    "address": {
        "street": "123 Main St",
        "city": "New York"
    }
})

print(user.address.city)  # "New York"
print(type(user.address))  # <class 'Address'>
```

## Lists of Nested Models

```python
class Company(BaseModel):
    name: str
    offices: list[Address] = []

schema = schema_for(Company)()

company = schema.load({
    "name": "Acme Inc",
    "offices": [
        {"street": "123 Main St", "city": "New York"},
        {"street": "456 Tech Blvd", "city": "San Francisco"}
    ]
})

print(len(company.offices))  # 2
```

## Optional Nested Models

```python
class User(BaseModel):
    name: str
    address: Address | None = None

schema = schema_for(User)()

# Address is optional
user = schema.load({"name": "Alice"})
print(user.address)  # None
```

## Deeply Nested Models

```python
class Street(BaseModel):
    name: str
    number: int

class Address(BaseModel):
    street: Street
    city: str

class User(BaseModel):
    name: str
    address: Address

schema = schema_for(User)()

user = schema.load({
    "name": "Alice",
    "address": {
        "street": {"name": "Main St", "number": 123},
        "city": "New York"
    }
})

print(user.address.street.number)  # 123
```

## Self-Referential Models

```python
from __future__ import annotations

class Node(BaseModel):
    value: int
    children: list[Node] = []

Node.model_rebuild()  # Required for forward references

schema = schema_for(Node)()

tree = schema.load({
    "value": 1,
    "children": [
        {"value": 2, "children": []},
        {"value": 3, "children": [
            {"value": 4}
        ]}
    ]
})
```

## Validation in Nested Models

Pydantic validation runs at all nesting levels:

```python
from pydantic import Field

class Address(BaseModel):
    city: str = Field(min_length=1)

class User(BaseModel):
    name: str
    address: Address

schema = schema_for(User)()

try:
    schema.load({
        "name": "Alice",
        "address": {"city": ""}  # Invalid - too short
    })
except ValidationError as e:
    print(e.messages)
    # {'address': {'city': ['String should have at least 1 character']}}
```
