"""In-memory economy repository for normalized snapshots."""

from __future__ import annotations

from datetime import datetime

from .economy import EconomyCategory, EconomyQuote, EconomySnapshot, ExchangeRate, FreshnessState


class EconomyRepository:
    def __init__(self, snapshots: tuple[EconomySnapshot, ...]):
        self._snapshots = {snapshot.snapshot_id: snapshot for snapshot in snapshots}

    def get_snapshot(self, snapshot_id: str) -> EconomySnapshot:
        try:
            return self._snapshots[snapshot_id]
        except KeyError as exc:
            raise KeyError(f"unknown economy snapshot: {snapshot_id}") from exc

    def get_current_quote(
        self,
        league: str,
        asset_id: str,
        as_of: datetime,
        source: str | None = None,
    ) -> EconomyQuote | None:
        candidates = [
            quote
            for snapshot in self._snapshots.values()
            if snapshot.league == league and (source is None or snapshot.provider == source)
            for quote in snapshot.quotes
            if quote.asset_id == asset_id
            and quote.retrieved_at is not None
            and quote.retrieved_at <= as_of
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda quote: quote.retrieved_at or as_of)

    def get_exchange_rate(
        self,
        league: str,
        base_asset_id: str,
        quote_asset_id: str,
        as_of: datetime,
        source: str | None = None,
    ) -> ExchangeRate | None:
        candidates = [
            rate
            for snapshot in self._snapshots.values()
            if snapshot.league == league and (source is None or snapshot.provider == source)
            for rate in snapshot.exchange_rates
            if rate.base_asset_id == base_asset_id
            and rate.quote_asset_id == quote_asset_id
            and rate.retrieved_at is not None
            and rate.retrieved_at <= as_of
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda rate: rate.retrieved_at or as_of)

    def get_current_quotes(
        self,
        league: str,
        asset_ids: tuple[str, ...],
        as_of: datetime,
        source: str | None = None,
    ) -> dict[str, EconomyQuote | None]:
        return {
            asset_id: self.get_current_quote(league, asset_id, as_of, source)
            for asset_id in asset_ids
        }

    def get_category_quotes(
        self,
        league: str,
        category: EconomyCategory | str,
        as_of: datetime,
        source: str | None = None,
    ) -> tuple[EconomyQuote, ...]:
        candidates = [
            quote
            for snapshot in self._snapshots.values()
            if snapshot.league == league and (source is None or snapshot.provider == source)
            for quote in snapshot.quotes
            if quote.category == category
            and quote.retrieved_at is not None
            and quote.retrieved_at <= as_of
        ]
        latest_by_asset: dict[str, EconomyQuote] = {}
        for quote in candidates:
            current = latest_by_asset.get(quote.asset_id)
            if current is None or (quote.retrieved_at or as_of) > (current.retrieved_at or as_of):
                latest_by_asset[quote.asset_id] = quote
        return tuple(latest_by_asset.values())

    def get_history(self, league: str, asset_id: str) -> tuple[EconomyQuote, ...]:
        return tuple(
            sorted(
                (
                    quote
                    for snapshot in self._snapshots.values()
                    if snapshot.league == league
                    for quote in snapshot.quotes
                    if quote.asset_id == asset_id
                ),
                key=lambda quote: quote.retrieved_at,
            )
        )

    def provider_snapshot_unavailable(self, source: str, league: str) -> bool:
        return not any(snapshot.provider == source and snapshot.league == league for snapshot in self._snapshots.values())

    @staticmethod
    def unavailable_quote_state() -> FreshnessState:
        return FreshnessState.UNAVAILABLE
