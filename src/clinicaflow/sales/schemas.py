from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SaleCreate(BaseModel):
    customer_id: int = Field(gt=0)
    description: str = Field(min_length=2, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    sale_date: date
    status: Literal["pending", "paid", "cancelled"] = "pending"
    notes: str | None = None


class SaleResponse(BaseModel):
    id: int
    customer_id: int
    description: str
    amount: Decimal
    sale_date: date
    status: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
