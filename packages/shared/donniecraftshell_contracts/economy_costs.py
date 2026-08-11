"""Craft-material cost calculation using normalized economy quotes.

This is not crafting simulation; it only prices a known list of ingredients.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .domain import EconomicValue
from .economy import EconomyQuote, FreshnessState, least_fresh, normalized_exalted_value
from .economy_repository import EconomyRepository


@dataclass(frozen=True)
class CraftMaterialRequirement:
    asset_id: str
    quantity: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.quantity, float):
            raise TypeError("craft material quantity must not use binary floating point")
        quantity = Decimal(self.quantity)
        if quantity <= Decimal("0"):
            raise ValueError("craft material quantity must be positive")
        object.__setattr__(self, "quantity", quantity)


@dataclass(frozen=True)
class CraftMaterialCostLine:
    asset_id: str
    quantity: Decimal
    quote: EconomyQuote | None
    unit_price: EconomicValue | None
    subtotal: EconomicValue | None
    freshness: FreshnessState = FreshnessState.UNAVAILABLE
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CraftMaterialCost:
    lines: tuple[CraftMaterialCostLine, ...]
    total: EconomicValue | None
    complete: bool
    freshness: FreshnessState
    warnings: tuple[str, ...] = ()
    oldest_source_timestamp: datetime | None = None
    newest_source_timestamp: datetime | None = None


def calculate_craft_material_cost(
    repository: EconomyRepository,
    league: str,
    requirements: tuple[CraftMaterialRequirement, ...],
    as_of: datetime,
) -> CraftMaterialCost:
    lines: list[CraftMaterialCostLine] = []
    warnings: list[str] = []
    timestamps: list[datetime] = []
    total = Decimal("0")
    complete = True

    for requirement in requirements:
        quote = repository.get_current_quote(league, requirement.asset_id, as_of)
        if quote is None or quote.normalized_value is None:
            complete = False
            warning = f"Missing economy quote for {requirement.asset_id}"
            warnings.append(warning)
            lines.append(
                CraftMaterialCostLine(
                    asset_id=requirement.asset_id,
                    quantity=requirement.quantity,
                    quote=quote,
                    unit_price=None,
                    subtotal=None,
                    warnings=(warning,),
                )
            )
            continue
        subtotal = quote.normalized_value.amount * requirement.quantity
        total += subtotal
        if quote.retrieved_at is not None:
            timestamps.append(quote.retrieved_at)
        lines.append(
            CraftMaterialCostLine(
                asset_id=requirement.asset_id,
                quantity=requirement.quantity,
                quote=quote,
                unit_price=quote.normalized_value,
                subtotal=normalized_exalted_value(subtotal),
                freshness=quote.freshness,
            )
        )

    freshness = least_fresh(tuple(line.freshness for line in lines))
    return CraftMaterialCost(
        lines=tuple(lines),
        total=normalized_exalted_value(total) if complete else None,
        complete=complete,
        freshness=freshness,
        warnings=tuple(warnings),
        oldest_source_timestamp=min(timestamps) if timestamps else None,
        newest_source_timestamp=max(timestamps) if timestamps else None,
    )
