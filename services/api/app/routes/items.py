"""Item routes."""

from __future__ import annotations

from fastapi import APIRouter

from packages.shared.donniecraftshell_contracts.domain import GameContext
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item

from services.api.app.mappers.item import parse_result_to_dto
from services.api.app.schemas.item import ParseItemRequestDto, ParseItemResponseDto


router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.post("/parse", response_model=ParseItemResponseDto)
def parse_item(request: ParseItemRequestDto) -> ParseItemResponseDto:
    result = parse_clipboard_item(
        request.raw_clipboard_text,
        GameContext(
            game=request.game,
            league=request.league,
            game_version=request.game_version,
            locale=request.locale,
        ),
    )
    return parse_result_to_dto(result)
