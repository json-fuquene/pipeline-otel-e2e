from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

CATALOG_PRICE_PATTERN = r"^\d{1,10}\.\d{2}$"


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: int = Field(ge=1, le=1_000_000, strict=True)


class CatalogProduct(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    price: Annotated[str, StringConstraints(pattern=CATALOG_PRICE_PATTERN)]
    created_at: datetime

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("El nombre de catálogo no es válido.")
        return value

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("El precio de catálogo no es válido.") from error
        if amount <= 0:
            raise ValueError("El precio de catálogo no es válido.")
        return value

    @field_validator("created_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("La fecha de catálogo no está expresada en UTC.")
        return value


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    unit_price: str
    quantity: int
    total: str
    created_at: datetime

    @field_validator("unit_price", "total", mode="before")
    @classmethod
    def format_money(cls, value: object) -> str:
        return format(Decimal(str(value)), ".2f")

    @field_validator("created_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria.")
        return value


class OrderPage(BaseModel):
    items: list[OrderOut]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class OrdersReadiness(BaseModel):
    status: Literal["ready", "not_ready"]
    service: Literal["orders"]
    checks: dict[Literal["database", "catalog"], Literal["up", "down"]]
