"""Item parser API schemas."""

from __future__ import annotations

from typing import Any

from .common import ApiErrorDto, ApiModel


class ParseItemRequestDto(ApiModel):
    raw_clipboard_text: str
    game: str = "Path of Exile 2"
    league: str | None = None
    game_version: str | None = None
    locale: str | None = None


class ParseItemResponseDto(ApiModel):
    item: dict[str, Any] | None = None
    detected_format: str
    warnings: list[str] = []
    unparsed_sections: list[str] = []
    error: ApiErrorDto | None = None
