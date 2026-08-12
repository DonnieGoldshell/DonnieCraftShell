"""Common Pydantic transport schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True, json_encoders={Decimal: str})


class ApiErrorDto(ApiModel):
    code: str
    message: str
    recoverable: bool = True
    reliable_no_result: bool = False
    details: dict[str, str] | None = None


class GameContextDto(ApiModel):
    game: str = "Path of Exile 2"
    league: str | None = None
    game_version: str | None = None
    locale: str | None = None


class EconomicValueDto(ApiModel):
    amount: str = Field(description="Decimal amount encoded as a string to avoid binary float corruption.")
    unit: str = "EXALTED_ECONOMIC_UNIT"

    @field_validator("amount")
    @classmethod
    def amount_is_decimal_string(cls, value: str) -> str:
        Decimal(value)
        return value


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
    environment: str


def decimal_to_str(value: Decimal | int | str | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value))


def enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value
