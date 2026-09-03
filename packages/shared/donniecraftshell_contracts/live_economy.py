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


class PoeShowLiveEconomyProvider:
    """Fetch poe.show overview categories and normalize them through the shared adapter."""

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
            return LiveEconomyIngestionResult(repository=base_repository, snapshots=())
        if not league.strip():
            raise ValueError("league is required for live economy ingestion")

        snapshots: list[EconomySnapshot] = []
        warnings: list[str] = []
        fetched_count = 0
        cache_hit_count = 0
        for category in self.config.categories:
            result = self._snapshot_for_category(league, category, as_of)
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
        )

    def _snapshot_for_category(self, league: str, category: str, as_of: datetime) -> "_CategorySnapshotResult":
        url = _overview_url(self.config.base_url, league, category)
        cache_path = self._cache_path(league, category)
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
                        (f"poe.show returned 304 for {category}, but no local cache was available.",),
                    )
                return _normalize_cached(cached, as_of, cache_hit=True)
            if response.status_code != 200:
                return self._fallback_or_warning(
                    cached,
                    as_of,
                    f"poe.show {category} fetch returned HTTP {response.status_code}.",
                )
            raw_response = json.loads(response.body or "{}", parse_float=Decimal, parse_int=Decimal)
            envelope = _cache_envelope(
                source_uri=url,
                league=league,
                category=category,
                response=raw_response,
                retrieved_at=as_of,
                etag=_header(response.headers, "etag"),
            )
            _write_cache(cache_path, envelope)
            normalized = normalize_poe_show_economy_payload(envelope, as_of)
            return _CategorySnapshotResult(normalized, tuple(normalized.warnings), fetched_count=1)
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            return self._fallback_or_warning(cached, as_of, f"poe.show {category} fetch failed: {exc}")

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

    def _cache_path(self, league: str, category: str) -> Path:
        digest = hashlib.sha256(f"{league}|{category}|{self.config.base_url}".encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"poe-show-{digest}.json"


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
    source_uri: str,
    league: str,
    category: str,
    response: dict[str, Any],
    retrieved_at: datetime,
    etag: str | None,
) -> dict[str, Any]:
    checksum = hashlib.sha256(json.dumps(response, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    snapshot_seed = hashlib.sha256(f"{league}|{category}|{retrieved_at.isoformat()}|{checksum}".encode("utf-8")).hexdigest()[:24]
    return {
        "cache_version": LIVE_ECONOMY_CACHE_VERSION,
        "source": "poe.show",
        "source_uri": source_uri,
        "league": league,
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
        "category": category,
        "snapshot_id": f"economy-snapshot:live-poe-show:{snapshot_seed}",
        "etag": etag,
        "raw_checksum": checksum,
        "response": response,
    }


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
