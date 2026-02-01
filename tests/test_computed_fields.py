"""Tests for Pydantic computed_field support.

Tests @computed_field decorator integration with Marshmallow dump().
"""

from typing import Optional

import pytest
from pydantic import BaseModel, computed_field

from pydantic_marshmallow import schema_for


class TestComputedFieldBasic:
    """Basic computed field tests."""

    def test_computed_field_in_dump(self):
        """Computed fields are included in dump output."""
        class Rectangle(BaseModel):
            width: float
            height: float

            @computed_field
            @property
            def area(self) -> float:
                return self.width * self.height

        schema = schema_for(Rectangle)()
        rect = Rectangle(width=10, height=5)
        result = schema.dump(rect)

        assert result["area"] == 50.0
        assert result["width"] == 10
        assert result["height"] == 5

    def test_computed_field_with_many(self):
        """Computed fields work with many=True dump."""
        class Item(BaseModel):
            quantity: int
            price: float

            @computed_field
            @property
            def subtotal(self) -> float:
                return self.quantity * self.price

        schema = schema_for(Item)()
        items = [
            Item(quantity=2, price=10),
            Item(quantity=3, price=20),
        ]
        results = schema.dump(items, many=True)

        assert results[0]["subtotal"] == 20.0
        assert results[1]["subtotal"] == 60.0

    def test_computed_field_exclude(self):
        """Computed fields can be excluded from dump via include_computed=False."""
        class Product(BaseModel):
            price: float
            tax_rate: float

            @computed_field
            @property
            def total(self) -> float:
                return self.price * (1 + self.tax_rate)

        schema = schema_for(Product)()
        product = Product(price=100, tax_rate=0.1)

        # Include computed (default)
        result = schema.dump(product, include_computed=True)
        assert pytest.approx(result["total"], rel=1e-9) == 110.0

        # Exclude computed via Pydantic's model_dump
        result_no_computed = product.model_dump(include=set(Product.model_fields.keys()))
        assert "total" not in result_no_computed
        assert "price" in result_no_computed


class TestComputedFieldWithExclusions:
    """Computed fields with dump exclusion options."""

    def test_computed_field_exclude_none(self):
        """Computed field returning None is excluded with exclude_none=True."""
        class Product(BaseModel):
            price: float
            discount: Optional[float] = None

            @computed_field
            @property
            def final_price(self) -> Optional[float]:
                if self.discount is None:
                    return None
                return self.price * (1 - self.discount)

        schema = schema_for(Product)()
        product = Product(price=100)  # No discount

        # Computed field returns None, exclude_none should remove it
        result = schema.dump(product, exclude_none=True)
        assert "final_price" not in result
        assert "discount" not in result
        assert "price" in result

    def test_computed_field_with_discount(self):
        """Computed field with value is included when exclude_none=True."""
        class Product(BaseModel):
            price: float
            discount: Optional[float] = None

            @computed_field
            @property
            def final_price(self) -> Optional[float]:
                if self.discount is None:
                    return None
                return self.price * (1 - self.discount)

        schema = schema_for(Product)()
        product = Product(price=100, discount=0.2)  # 20% discount

        result = schema.dump(product, exclude_none=True)
        assert result["final_price"] == 80.0


class TestComputedFieldComplexTypes:
    """Computed fields returning complex types."""

    def test_computed_field_returns_dict(self):
        """Computed field can return a dict."""
        class User(BaseModel):
            first_name: str
            last_name: str

            @computed_field
            @property
            def name_parts(self) -> dict:
                return {"first": self.first_name, "last": self.last_name}

        schema = schema_for(User)()
        user = User(first_name="Alice", last_name="Smith")
        result = schema.dump(user)

        assert result["name_parts"] == {"first": "Alice", "last": "Smith"}

    def test_computed_field_returns_list(self):
        """Computed field can return a list."""
        class User(BaseModel):
            first_name: str
            last_name: str

            @computed_field
            @property
            def name_tokens(self) -> list:
                return [self.first_name, self.last_name]

        schema = schema_for(User)()
        user = User(first_name="Alice", last_name="Smith")
        result = schema.dump(user)

        assert result["name_tokens"] == ["Alice", "Smith"]

    def test_multiple_computed_fields(self):
        """Model can have multiple computed fields."""
        class Rectangle(BaseModel):
            width: float
            height: float

            @computed_field
            @property
            def area(self) -> float:
                return self.width * self.height

            @computed_field
            @property
            def perimeter(self) -> float:
                return 2 * (self.width + self.height)

            @computed_field
            @property
            def is_square(self) -> bool:
                return self.width == self.height

        schema = schema_for(Rectangle)()

        square = Rectangle(width=5, height=5)
        result = schema.dump(square)
        assert result["area"] == 25.0
        assert result["perimeter"] == 20.0
        assert result["is_square"] is True

        rect = Rectangle(width=4, height=6)
        result = schema.dump(rect)
        assert result["area"] == 24.0
        assert result["perimeter"] == 20.0
        assert result["is_square"] is False


class TestComputedFieldWithReturnInstance:
    """Computed fields with return_instance parameter."""

    def test_return_instance_false_includes_computed(self):
        """return_instance=False includes computed fields in dict output."""
        class User(BaseModel):
            first: str
            last: str

            @computed_field
            @property
            def full_name(self) -> str:
                return f"{self.first} {self.last}"

        schema = schema_for(User)()
        result = schema.load({"first": "Alice", "last": "Smith"}, return_instance=False)

        assert result["first"] == "Alice"
        assert result["last"] == "Smith"
        assert result["full_name"] == "Alice Smith"
