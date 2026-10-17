from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MONEY_PATTERN = r"^\d{1,16}\.\d{2}$"


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID
    product_id: UUID
    quantity: int = Field(ge=1, le=1_000_000, strict=True)
    total: Annotated[str, StringConstraints(pattern=MONEY_PATTERN)]

    @field_validator("total")
    @classmethod
    def positive_total(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("El total debe ser positivo.")
        return value


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    total: str
    recorded_at: datetime

    @field_validator("total", mode="before")
    @classmethod
    def format_money(cls, value: object) -> str:
        return format(Decimal(str(value)), ".2f")


class TopProduct(BaseModel):
    product_id: UUID
    orders: int
    units: int
    revenue: str


class Summary(BaseModel):
    window_minutes: int
    orders: int
    units: int
    revenue: str
    top_products: list[TopProduct]
    database: Literal["aws", "gcp", "local"]


class DataReadiness(BaseModel):
    status: Literal["ready", "not_ready"]
    service: Literal["data-service"]
    checks: dict[Literal["database"], Literal["up", "down"]]
