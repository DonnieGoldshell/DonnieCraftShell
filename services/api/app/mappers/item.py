"""Item parser API mappers."""

from __future__ import annotations

from packages.shared.donniecraftshell_contracts.parser import ParseResult

from services.api.app.mappers.common import api_error_to_dto, to_jsonable
from services.api.app.schemas.item import ParseItemResponseDto


def parse_result_to_dto(result: ParseResult) -> ParseItemResponseDto:
    return ParseItemResponseDto(
        item=to_jsonable(result.item),
        detected_format=result.detected_format.value,
        warnings=list(result.warnings),
        unparsed_sections=list(result.unparsed_sections),
        error=api_error_to_dto(result.error),
    )
