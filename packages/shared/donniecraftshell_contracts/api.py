"""API request/response contracts and common error model.

These are DTO contracts only. They do not implement endpoint behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .domain import (
    AdvisorRecommendation,
    BankrollContext,
    ClipboardFormat,
    CraftAction,
    CraftSession,
    EconomyQuote,
    GameContext,
    ParsedItem,
    SimulationResult,
    Valuation,
)
from .game_data import ItemEnrichment


class ApiErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_ITEM = "UNSUPPORTED_ITEM"
    PARSE_FAILURE = "PARSE_FAILURE"
    INSUFFICIENT_VERIFIED_DATA = "INSUFFICIENT_VERIFIED_DATA"
    EXTERNAL_DATA_UNAVAILABLE = "EXTERNAL_DATA_UNAVAILABLE"
    SIMULATION_UNAVAILABLE = "SIMULATION_UNAVAILABLE"
    VALUATION_UNAVAILABLE = "VALUATION_UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass(frozen=True)
class ApiError:
    code: ApiErrorCode
    message: str
    recoverable: bool = True
    reliable_no_result: bool = False
    details: Mapping[str, str] | None = None


@dataclass(frozen=True)
class ApiResponse:
    data: object | None = None
    error: ApiError | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseItemRequest:
    raw_clipboard_text: str
    game_context: GameContext


@dataclass(frozen=True)
class ParseItemResponse:
    item: ParsedItem | None
    detected_format: ClipboardFormat = ClipboardFormat.UNKNOWN
    warnings: tuple[str, ...] = ()
    unparsed_sections: tuple[str, ...] = ()
    error: ApiError | None = None


@dataclass(frozen=True)
class AnalyzeItemRequest:
    item: ParsedItem
    bankroll_context: BankrollContext | None = None


@dataclass(frozen=True)
class AnalyzeItemResponse:
    item: ParsedItem
    current_valuation: Valuation | None = None
    candidate_actions: tuple[CraftAction, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EconomyCurrentRequest:
    game_context: GameContext
    asset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EconomyCurrentResponse:
    quotes: tuple[EconomyQuote, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValuationRequest:
    item: ParsedItem
    game_context: GameContext


@dataclass(frozen=True)
class ValuationResponse:
    valuation: Valuation | None
    error: ApiError | None = None


@dataclass(frozen=True)
class EnrichItemRequest:
    item: ParsedItem
    snapshot_id: str | None = None


@dataclass(frozen=True)
class EnrichItemResponse:
    enrichment: ItemEnrichment | None
    error: ApiError | None = None


@dataclass(frozen=True)
class SimulateCraftRequest:
    source_item: ParsedItem
    action: CraftAction
    game_context: GameContext


@dataclass(frozen=True)
class SimulateCraftResponse:
    simulation: SimulationResult | None
    error: ApiError | None = None


@dataclass(frozen=True)
class AdvisorRequest:
    item: ParsedItem
    game_context: GameContext
    bankroll_context: BankrollContext | None = None


@dataclass(frozen=True)
class AdvisorResponse:
    recommendation: AdvisorRecommendation
    errors: tuple[ApiError, ...] = ()


@dataclass(frozen=True)
class CreateSessionRequest:
    game_context: GameContext
    initial_item: ParsedItem


@dataclass(frozen=True)
class CreateSessionResponse:
    session: CraftSession


@dataclass(frozen=True)
class AddSessionStepRequest:
    session_id: str
    action: CraftAction
    resulting_item: ParsedItem | None = None


@dataclass(frozen=True)
class AddSessionStepResponse:
    session: CraftSession | None
    error: ApiError | None = None


@dataclass(frozen=True)
class EndpointContract:
    method: str
    path: str
    request_type: str
    response_type: str
    status: ApiErrorCode = ApiErrorCode.NOT_IMPLEMENTED


ENDPOINT_CONTRACTS: tuple[EndpointContract, ...] = (
    EndpointContract("POST", "/api/v1/items/parse", "ParseItemRequest", "ParseItemResponse"),
    EndpointContract("POST", "/api/v1/items/enrich", "EnrichItemRequest", "EnrichItemResponse"),
    EndpointContract("POST", "/api/v1/items/analyze", "AnalyzeItemRequest", "AnalyzeItemResponse"),
    EndpointContract("GET", "/api/v1/economy/current", "EconomyCurrentRequest", "EconomyCurrentResponse"),
    EndpointContract("POST", "/api/v1/valuation", "ValuationRequest", "ValuationResponse"),
    EndpointContract("POST", "/api/v1/crafts/simulate", "SimulateCraftRequest", "SimulateCraftResponse"),
    EndpointContract("POST", "/api/v1/advisor", "AdvisorRequest", "AdvisorResponse"),
    EndpointContract("POST", "/api/v1/sessions", "CreateSessionRequest", "CreateSessionResponse"),
    EndpointContract("POST", "/api/v1/sessions/{id}/steps", "AddSessionStepRequest", "AddSessionStepResponse"),
)
