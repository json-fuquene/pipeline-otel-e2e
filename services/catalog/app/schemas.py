from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PRICE_PATTERN = r"^\d{1,10}(?:\.\d{1,2})?$"


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    price: Annotated[str, StringConstraints(pattern=PRICE_PATTERN)]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 200:
            raise ValueError("El nombre debe contener entre 1 y 200 caracteres.")
        return normalized

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("El precio no es válido.") from error
        if amount <= 0:
            raise ValueError("El precio debe ser mayor que cero.")
        return format(amount, ".2f")


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price: str
    created_at: datetime

    @field_validator("price", mode="before")
    @classmethod
    def format_price(cls, value: object) -> str:
        return format(Decimal(str(value)), ".2f")

    @field_validator("created_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria.")
        return value


class ProductPage(BaseModel):
    items: list[ProductOut]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class CatalogReadiness(BaseModel):
    status: Literal["ready", "not_ready"]
    service: Literal["catalog"]
    checks: dict[Literal["database"], Literal["up", "down"]]
