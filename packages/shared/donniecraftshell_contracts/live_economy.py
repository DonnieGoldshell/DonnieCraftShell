"""League-aware live economy ingestion with bounded cache semantics."""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from .economy import EconomyCategory, EconomySnapshot
from .economy_repository import EconomyRepository
from .poe_show_economy import normalize_poe_show_economy_payload


LIVE_ECONOMY_CACHE_VERSION = "dc-live-economy-cache-v1"
DEFAULT_POE_SHOW_BASE_URL = "https://poe.show/poe2/api/economy"
DEFAULT_POE_NINJA_BASE_URL = "https://poe.ninja/poe2/api/economy"
DEFAULT_LIVE_ECONOMY_USER_AGENT = "DonnieCraftShell/0.1 (+https://github.com/DonnieGoldshell/DonnieCraftShell)"
DEFAULT_LIVE_ECONOMY_CATEGORIES = (
    EconomyCategory.CURRENCY.value,
    EconomyCategory.RITUAL.value,
    EconomyCategory.ESSENCES.value,
)
DEFAULT_LIVE_ECONOMY_REFRESH_INTERVAL = timedelta(hours=1)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: str | None = None


class EconomyHttpTransport(Protocol):
    def get(self, url: str, headers: dict[str, str], timeout_seconds: Decimal) -> HttpResponse:
        ...


class UrlLibEconomyHttpTransport:
    def get(self, url: str, headers: dict[str, str], timeout_seconds: Decimal) -> HttpResponse:
        request = urllib.request.Request(url, headers=headers, method="GET")
        timeout = float(timeout_seconds)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured backend-only provider.
                body = response.read().decode("utf-8")
                return HttpResponse(
                    status_code=response.status,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return HttpResponse(status_code=304, headers={key.lower(): value for key, value in exc.headers.items()})
            raise


@dataclass(frozen=True)
class LiveEconomyProviderConfig:
    enabled: bool = False
    base_url: str = DEFAULT_POE_SHOW_BASE_URL
    user_agent: str = DEFAULT_LIVE_ECONOMY_USER_AGENT
    timeout_seconds: Decimal = Decimal("5")
    refresh_interval: timedelta = DEFAULT_LIVE_ECONOMY_REFRESH_INTERVAL
    categories: tuple[str, ...] = DEFAULT_LIVE_ECONOMY_CATEGORIES

    def __post_init__(self) -> None:
        if self.timeout_seconds <= Decimal("0"):
            raise ValueError("live economy timeout must be positive")
        if self.refresh_interval <= timedelta(0):
            raise ValueError("live economy refresh interval must be positive")
        if not self.user_agent.strip():
            raise ValueError("live economy User-Agent is required")
        if not self.categories:
            raise ValueError("live economy categories are required")


@dataclass(frozen=True)
class LiveEconomyIngestionResult:
    repository: EconomyRepository
    snapshots: tuple[EconomySnapshot, ...]
    warnings: tuple[str, ...] = ()
    fetched_count: int = 0
    cache_hit_count: int = 0
    provider_id: str | None = None
    selected_provider_id: str | None = None
    provider_order: tuple[str, ...] = ()
    attempted_provider_ids: tuple[str, ...] = ()
    cache_dir: Path | None = None


class PoeShowLiveEconomyProvider:
    """Fetch poe.show overview categories and normalize them through the shared adapter."""

    provider_id = "poe.show"
    cache_prefix = "poe-show"
    live_snapshot_slug = "poe-show"

    def __init__(
        self,
        cache_dir: Path,
        config: LiveEconomyProviderConfig | None = None,
        transport: EconomyHttpTransport | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.config = config or LiveEconomyProviderConfig()
        self.transport = transport or UrlLibEconomyHttpTransport()

    def economy_repository(
        self,
        base_repository: EconomyRepository,
        league: str,
        as_of: datetime,
    ) -> LiveEconomyIngestionResult:
        if not self.config.enabled:
            return LiveEconomyIngestionResult(
                repository=base_repository,
                snapshots=(),
                provider_id=self.provider_id,
                selected_provider_id=None,
                provider_order=(self.provider_id,),
                attempted_provider_ids=(),
                cache_dir=self.cache_dir,
            )
        if not league.strip():
            raise ValueError("league is required for live economy ingestion")

        source_league, league_warnings = self._league_for_request(league, as_of)
        snapshots: list[EconomySnapshot] = []
        warnings: list[str] = list(league_warnings)
        fetched_count = 0
        cache_hit_count = 0
        for category in self.config.categories:
            result = self._snapshot_for_category(league, source_league, category, as_of)
            warnings.extend(result.warnings)
            if result.snapshot is not None:
                snapshots.append(result.snapshot)
            fetched_count += result.fetched_count
            cache_hit_count += result.cache_hit_count
        repository = EconomyRepository((*base_repository.snapshots(), *snapshots))
        return LiveEconomyIngestionResult(
            repository=repository,
            snapshots=tuple(snapshots),
            warnings=tuple(warnings),
            fetched_count=fetched_count,
            cache_hit_count=cache_hit_count,
            provider_id=self.provider_id,
            selected_provider_id=self.provider_id if snapshots else None,
            provider_order=(self.provider_id,),
            attempted_provider_ids=(self.provider_id,),
            cache_dir=self.cache_dir,
        )

    def _league_for_request(self, league: str, as_of: datetime) -> tuple[str, tuple[str, ...]]:
        return league, ()

    def _snapshot_for_category(self, league: str, source_league: str, category: str, as_of: datetime) -> "_CategorySnapshotResult":
        url = _overview_url(self.config.base_url, source_league, category)
        cache_path = self._cache_path(league, source_league, category)
        cached = _read_cache(cache_path)
        if cached and _cache_age(cached, as_of) <= self.config.refresh_interval:
            return _normalize_cached(cached, as_of, cache_hit=True)
        headers = {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
        }
        if cached and cached.get("etag"):
            headers["If-None-Match"] = str(cached["etag"])
        try:
            response = self.transport.get(url, headers, self.config.timeout_seconds)
            if response.status_code == 304:
                if cached is None:
                    return _CategorySnapshotResult(
                        None,
                        (f"{self.provider_id} returned 304 for {category}, but no local cache was available.",),
                    )
                return _normalize_cached(cached, as_of, cache_hit=True)
            if response.status_code != 200:
                return self._fallback_or_warning(
                    cached,
                    as_of,
                    f"{self.provider_id} {category} fetch returned HTTP {response.status_code}.",
                )
            raw_response = json.loads(response.body or "{}", parse_float=Decimal, parse_int=Decimal)
            envelope = _cache_envelope(
                provider_id=self.provider_id,
                live_snapshot_slug=self.live_snapshot_slug,
                source_uri=url,
                league=league,
                source_league=source_league,
                category=category,
                response=raw_response,
                retrieved_at=as_of,
                etag=_header(response.headers, "etag"),
            )
            _write_cache(cache_path, envelope)
            normalized = normalize_poe_show_economy_payload(envelope, as_of)
            return _CategorySnapshotResult(normalized, tuple(normalized.warnings), fetched_count=1)
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            return self._fallback_or_warning(cached, as_of, f"{self.provider_id} {category} fetch failed: {exc}")

    def _fallback_or_warning(
        self,
        cached: dict[str, Any] | None,
        as_of: datetime,
        warning: str,
    ) -> "_CategorySnapshotResult":
        if cached is None:
            return _CategorySnapshotResult(None, (warning,))
        normalized = normalize_poe_show_economy_payload(cached, as_of)
        return _CategorySnapshotResult(
            normalized,
            (warning, f"Using cached live economy snapshot {normalized.snapshot_id} with freshness {normalized.freshness.value}.", *normalized.warnings),
            cache_hit_count=1,
        )

    def _cache_path(self, league: str, source_league: str, category: str) -> Path:
        digest = hashlib.sha256(
            f"{self.provider_id}|{league}|{source_league}|{category}|{self.config.base_url}".encode("utf-8")
        ).hexdigest()[:24]
        return self.cache_dir / f"{self.cache_prefix}-{digest}.json"


class PoeNinjaLiveEconomyProvider(PoeShowLiveEconomyProvider):
    """Fetch poe.ninja overview categories with a poe.ninja-isolated cache namespace."""

    provider_id = "poe.ninja"
    cache_prefix = "poe-ninja"
    live_snapshot_slug = "poe-ninja"

    def _league_for_request(self, league: str, as_of: datetime) -> tuple[str, tuple[str, ...]]:
        cache_path = self._league_cache_path(league)
        cached = _read_cache(cache_path)
        if cached and _cache_age(cached, as_of) <= self.config.refresh_interval:
            source_league = cached.get("source_league")
            if isinstance(source_league, str) and source_league.strip():
                return source_league, ()
        url = f"{self.config.base_url.rstrip('/')}/leagues"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
        }
        try:
            response = self.transport.get(url, headers, self.config.timeout_seconds)
            if response.status_code != 200:
                return league, (f"{self.provider_id} league discovery returned HTTP {response.status_code}; using requested league.",)
            payload = json.loads(response.body or "[]", parse_float=Decimal, parse_int=Decimal)
            resolved = _resolve_poe_ninja_league_id(payload, league)
            if resolved is None:
                return league, (f"{self.provider_id} league discovery did not contain exact league {league}; using requested league.",)
            _write_cache(
                cache_path,
                {
                    "cache_version": LIVE_ECONOMY_CACHE_VERSION,
                    "source": self.provider_id,
                    "source_uri": url,
                    "league": league,
                    "source_league": resolved,
                    "retrieved_at": as_of.astimezone(timezone.utc).isoformat(),
                    "category": "Leagues",
                    "response": payload,
                },
            )
            return resolved, ()
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            return league, (f"{self.provider_id} league discovery failed: {exc}; using requested league.",)

    def _league_cache_path(self, league: str) -> Path:
        digest = hashlib.sha256(f"{self.provider_id}|leagues|{league}|{self.config.base_url}".encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{self.cache_prefix}-leagues-{digest}.json"


class LiveEconomyProviderChain:
    """Ordered live economy provider chain with fail-closed fallback provenance."""

    def __init__(self, providers: tuple[PoeShowLiveEconomyProvider, ...]) -> None:
        if not providers:
            raise ValueError("at least one live economy provider is required")
        self.providers = providers
        self.config = providers[0].config
        self.cache_dir = providers[0].cache_dir
        self.provider_order = tuple(provider.provider_id for provider in providers)

    def economy_repository(
        self,
        base_repository: EconomyRepository,
        league: str,
        as_of: datetime,
    ) -> LiveEconomyIngestionResult:
        if not any(provider.config.enabled for provider in self.providers):
            return LiveEconomyIngestionResult(
                repository=base_repository,
                snapshots=(),
                provider_order=self.provider_order,
                attempted_provider_ids=(),
                cache_dir=self.cache_dir,
            )

        attempted: list[str] = []
        warnings: list[str] = []
        cached_fallback: LiveEconomyIngestionResult | None = None
        for provider in self.providers:
            if not provider.config.enabled:
                continue
            attempted.append(provider.provider_id)
            result = provider.economy_repository(base_repository, league, as_of)
            provider_warnings = [f"{provider.provider_id}: {warning}" for warning in result.warnings]
            warnings.extend(provider_warnings)
            provider_result = _with_chain_metadata(
                result,
                warnings=tuple(warnings),
                provider_order=self.provider_order,
                attempted_provider_ids=tuple(attempted),
            )
            if result.fetched_count and result.snapshots:
                return provider_result
            if result.snapshots and cached_fallback is None:
                cached_fallback = provider_result
                if not _result_used_provider_error_cache(result):
                    return provider_result
                continue
            if result.snapshots:
                return provider_result
        if cached_fallback is not None:
            return cached_fallback
        return LiveEconomyIngestionResult(
            repository=base_repository,
            snapshots=(),
            warnings=tuple(warnings) or ("Live economy providers returned no usable snapshots.",),
            provider_order=self.provider_order,
            attempted_provider_ids=tuple(attempted),
            cache_dir=self.cache_dir,
        )


@dataclass(frozen=True)
class _CategorySnapshotResult:
    snapshot: EconomySnapshot | None
    warnings: tuple[str, ...] = ()
    fetched_count: int = 0
    cache_hit_count: int = 0


def _overview_url(base_url: str, league: str, category: str) -> str:
    query = urllib.parse.urlencode({"league": league, "type": category})
    return f"{base_url.rstrip('/')}/exchange/current/overview?{query}"


def _cache_envelope(
    provider_id: str,
    live_snapshot_slug: str,
    source_uri: str,
    league: str,
    source_league: str,
    category: str,
    response: dict[str, Any],
    retrieved_at: datetime,
    etag: str | None,
) -> dict[str, Any]:
    checksum = hashlib.sha256(json.dumps(response, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    snapshot_seed = hashlib.sha256(f"{league}|{category}|{retrieved_at.isoformat()}|{checksum}".encode("utf-8")).hexdigest()[:24]
    return {
        "cache_version": LIVE_ECONOMY_CACHE_VERSION,
        "source": provider_id,
        "source_uri": source_uri,
        "league": league,
        "source_league": source_league,
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
        "category": category,
        "snapshot_id": f"economy-snapshot:live-{live_snapshot_slug}:{snapshot_seed}",
        "etag": etag,
        "raw_checksum": checksum,
        "response": response,
    }


def _with_chain_metadata(
    result: LiveEconomyIngestionResult,
    warnings: tuple[str, ...],
    provider_order: tuple[str, ...],
    attempted_provider_ids: tuple[str, ...],
) -> LiveEconomyIngestionResult:
    return LiveEconomyIngestionResult(
        repository=result.repository,
        snapshots=result.snapshots,
        warnings=warnings,
        fetched_count=result.fetched_count,
        cache_hit_count=result.cache_hit_count,
        provider_id=result.provider_id,
        selected_provider_id=result.selected_provider_id,
        provider_order=provider_order,
        attempted_provider_ids=attempted_provider_ids,
        cache_dir=result.cache_dir,
    )


def _result_used_provider_error_cache(result: LiveEconomyIngestionResult) -> bool:
    warnings = " ".join(result.warnings).lower()
    return bool(result.cache_hit_count and ("fetch failed" in warnings or "returned http" in warnings))


def _resolve_poe_ninja_league_id(payload: Any, requested_league: str) -> str | None:
    requested = requested_league.strip().lower()
    candidates = payload
    if isinstance(payload, dict):
        candidates = payload.get("leagues") or payload.get("data") or payload.get("result") or []
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        possible_labels = (
            candidate.get("id"),
            candidate.get("name"),
            candidate.get("text"),
            candidate.get("displayName"),
            candidate.get("display_name"),
        )
        if any(isinstance(label, str) and label.strip().lower() == requested for label in possible_labels):
            source_id = candidate.get("id")
            return str(source_id) if source_id is not None else requested_league
    return None


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    except Exception:
        return None
    if data.get("cache_version") != LIVE_ECONOMY_CACHE_VERSION:
        return None
    return data


def _write_cache(path: Path, envelope: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(envelope, indent=2, sort_keys=True, default=str)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _normalize_cached(cached: dict[str, Any], as_of: datetime, cache_hit: bool = False) -> _CategorySnapshotResult:
    normalized = normalize_poe_show_economy_payload(cached, as_of)
    warnings = (f"Using cached live economy snapshot {normalized.snapshot_id} with freshness {normalized.freshness.value}.", *normalized.warnings)
    return _CategorySnapshotResult(normalized, warnings, cache_hit_count=1 if cache_hit else 0)


def _cache_age(cached: dict[str, Any], as_of: datetime) -> timedelta:
    retrieved_at = _cache_retrieved_at(cached)
    reference = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=timezone.utc)
    age = reference.astimezone(timezone.utc) - retrieved_at
    return max(age, timedelta(0))


def _cache_retrieved_at(cached: dict[str, Any]) -> datetime:
    value = cached.get("retrieved_at")
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _header(headers: dict[str, str], name: str) -> str | None:
    return headers.get(name.lower()) or headers.get(name)
