"""Minimal API scaffold for DonnieCraftShell.

Only item parsing has real behavior in Task 4. Other product functionality is
intentionally not implemented.
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ModuleNotFoundError as exc:  # pragma: no cover - documents missing deps
    raise RuntimeError(
        "FastAPI/Pydantic are required to run the HTTP API. "
        "Install backend dependencies before starting services.api.app.main."
    ) from exc

from packages.shared.donniecraftshell_contracts.domain import GameContext
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


class ParseItemRequestDto(BaseModel):
    raw_clipboard_text: str
    game: str = "Path of Exile 2"
    league: str | None = None
    game_version: str | None = None
    locale: str | None = None


app = FastAPI(title="DonnieCraftShell API", version="0.1.0")


@app.post("/api/v1/items/parse")
def parse_item(request: ParseItemRequestDto) -> dict[str, Any]:
    result = parse_clipboard_item(
        request.raw_clipboard_text,
        GameContext(
            game=request.game,
            league=request.league,
            game_version=request.game_version,
            locale=request.locale,
        ),
    )
    return {
        "item": _to_jsonable(result.item),
        "detected_format": result.detected_format.value,
        "warnings": result.warnings,
        "unparsed_sections": result.unparsed_sections,
        "error": _to_jsonable(result.error),
    }


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: _to_jsonable(getattr(value, key))
            for key in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return str(value) if value.__class__.__module__ == "decimal" else value
