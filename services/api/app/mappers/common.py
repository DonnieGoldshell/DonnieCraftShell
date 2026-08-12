"""Shared API mapping helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from packages.shared.donniecraftshell_contracts.domain import EconomicValue

from services.api.app.schemas.common import ApiErrorDto, EconomicValueDto, enum_value


def economic_value_to_dto(value: EconomicValue | None) -> EconomicValueDto | None:
    if value is None:
        return None
    return EconomicValueDto(amount=str(value.amount), unit=value.unit)


def api_error_to_dto(error) -> ApiErrorDto | None:
    if error is None:
        return None
    return ApiErrorDto(
        code=enum_value(error.code),
        message=error.message,
        recoverable=error.recoverable,
        reliable_no_result=error.reliable_no_result,
        details=dict(error.details) if error.details else None,
    )


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: to_jsonable(getattr(value, key))
            for key in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
