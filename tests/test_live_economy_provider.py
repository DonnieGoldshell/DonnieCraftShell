import json
import unittest
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.economy import (
    DIVINE_ASSET_ID,
    ESSENCE_OF_HYSTERIA_ASSET_ID,
    EXALTED_ASSET_ID,
    OMEN_OF_GREATER_ANNULMENT_ASSET_ID,
    ORB_OF_ANNULMENT_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
    EconomyCategory,
    FreshnessState,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.live_economy import (
    HttpResponse,
    LiveEconomyProviderChain,
    LiveEconomyProviderConfig,
    PoeNinjaLiveEconomyProvider,
    PoeShowLiveEconomyProvider,
)


LEAGUE = "Runes of Aldur"
OTHER_LEAGUE = "Other League"
AS_OF = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp-tests" / "live-economy"


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, headers, timeout_seconds):
        self.requests.append((url, dict(headers), timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class LiveEconomyProviderTests(unittest.TestCase):
    def _cache_dir(self) -> str:
        path = TMP_ROOT / f"{os.getpid()}-{self._testMethodName}"
        path.mkdir(parents=True, exist_ok=True)
        for child in path.glob("*"):
            if child.is_file():
                child.unlink()
        return str(path)

    def test_live_provider_fetches_exact_league_and_normalizes_currency_quotes(self):
        transport = FakeTransport((_response(currency_payload()),))

        result = _provider(self._cache_dir(), transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        quote = result.repository.get_current_quote(LEAGUE, PERFECT_EXALTED_ASSET_ID, AS_OF)
        divine_rate = result.repository.get_exchange_rate(LEAGUE, DIVINE_ASSET_ID, EXALTED_ASSET_ID, AS_OF)

        self.assertEqual(result.fetched_count, 1)
        self.assertIn("league=Runes+of+Aldur", transport.requests[0][0])
        self.assertEqual(quote.normalized_value.amount, Decimal("850.00"))
        self.assertEqual(divine_rate.rate, Decimal("340"))
        self.assertEqual(quote.source, "poe.show")
        self.assertEqual(quote.provenance[0].source_uri, transport.requests[0][0])
        self.assertIsNone(result.repository.get_current_quote(OTHER_LEAGUE, PERFECT_EXALTED_ASSET_ID, AS_OF))

    def test_live_provider_fetches_currency_ritual_and_essence_categories(self):
        transport = FakeTransport((
            _response(currency_payload()),
            _response(ritual_payload()),
            _response(essence_payload()),
        ))

        provider = PoeShowLiveEconomyProvider(
            Path(self._cache_dir()),
            LiveEconomyProviderConfig(
                enabled=True,
                base_url="https://poe.show/poe2/api/economy",
                user_agent="DonnieCraftShell test",
                timeout_seconds=Decimal("2"),
                categories=("Currency", "Ritual", "Essences"),
            ),
            transport,
        )
        result = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        self.assertEqual(result.fetched_count, 3)
        self.assertIn("type=Currency", transport.requests[0][0])
        self.assertIn("type=Ritual", transport.requests[1][0])
        self.assertIn("type=Essences", transport.requests[2][0])
        self.assertEqual(
            result.repository.get_current_quote(LEAGUE, OMEN_OF_GREATER_ANNULMENT_ASSET_ID, AS_OF).normalized_value.amount,
            Decimal("680"),
        )
        self.assertEqual(
            result.repository.get_current_quote(LEAGUE, ESSENCE_OF_HYSTERIA_ASSET_ID, AS_OF).normalized_value.amount,
            Decimal("1020"),
        )

    def test_provider_does_not_fabricate_unknown_asset_quotes(self):
        payload = currency_payload()
        payload["lines"].append({"id": "future-unknown-currency", "primaryValue": "1", "volumePrimaryValue": "2"})
        transport = FakeTransport((_response(payload),))

        result = _provider(self._cache_dir(), transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        self.assertIn("Unmapped poe.show asset skipped: future-unknown-currency", result.warnings)
        self.assertIsNone(result.repository.get_current_quote(LEAGUE, "future-unknown-currency", AS_OF))

    def test_live_provider_resolves_annulment_from_core_item_details_id(self):
        transport = FakeTransport((_response(currency_payload_with_metadata_annulment()),))

        result = _provider(self._cache_dir(), transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF)

        self.assertEqual(result.fetched_count, 1)
        self.assertIsNotNone(quote)
        self.assertEqual(quote.normalized_value.amount, Decimal("170.00"))
        self.assertEqual(quote.source_native_value, Decimal("0.5"))
        self.assertEqual(quote.volume, Decimal("11"))
        self.assertEqual(quote.source, "poe.show")
        self.assertEqual(quote.provenance[0].source_uri, transport.requests[0][0])
        self.assertEqual(quote.freshness, FreshnessState.FRESH)
        self.assertIsNone(result.repository.get_current_quote(OTHER_LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF))
        self.assertNotIn("Unmapped poe.show asset skipped: provider-specific-annulment-id", result.warnings)

    def test_cache_within_refresh_interval_reuses_cached_snapshot_without_transport_request(self):
        transport = FakeTransport((_response(currency_payload(), etag="currency-v1"),))

        cache_dir = self._cache_dir()
        provider = _provider(cache_dir, transport)
        first = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        second = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(minutes=30))

        quote = second.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF + timedelta(minutes=30))

        self.assertEqual(first.fetched_count, 1)
        self.assertEqual(first.cache_hit_count, 0)
        self.assertEqual(second.fetched_count, 0)
        self.assertEqual(second.cache_hit_count, 1)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(len(list(Path(cache_dir).glob("poe-show-*.json"))), 1)
        self.assertEqual(quote.normalized_value.amount, Decimal("2040"))

    def test_etag_cache_reuses_cached_snapshot_after_refresh_interval(self):
        transport = FakeTransport((
            _response(currency_payload(), etag="currency-v1"),
            HttpResponse(status_code=304, headers={}),
        ))

        provider = _provider(self._cache_dir(), transport)
        first = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        second = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(hours=2))

        quote = second.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF + timedelta(hours=2))

        self.assertEqual(first.fetched_count, 1)
        self.assertEqual(second.cache_hit_count, 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(transport.requests[1][1]["If-None-Match"], "currency-v1")
        self.assertEqual(quote.normalized_value.amount, Decimal("2040"))

    def test_provider_error_uses_valid_cache_with_freshness_warning(self):
        transport = FakeTransport((
            _response(currency_payload(), etag="currency-v1"),
            TimeoutError("timed out"),
        ))

        provider = _provider(self._cache_dir(), transport)
        provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        cached = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(hours=7))

        quote = cached.repository.get_current_quote(LEAGUE, DIVINE_ASSET_ID, AS_OF + timedelta(hours=7))

        self.assertEqual(cached.cache_hit_count, 1)
        self.assertEqual(quote.freshness, FreshnessState.STALE)
        self.assertTrue(any("Using cached live economy snapshot" in warning for warning in cached.warnings))
        self.assertTrue(any("timed out" in warning for warning in cached.warnings))

    def test_provider_error_without_cache_fails_closed(self):
        transport = FakeTransport((TimeoutError("timed out"),))

        result = _provider(self._cache_dir(), transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        self.assertEqual(result.snapshots, ())
        self.assertIsNone(result.repository.get_current_quote(LEAGUE, DIVINE_ASSET_ID, AS_OF))
        self.assertTrue(any("timed out" in warning for warning in result.warnings))

    def test_provider_chain_uses_poe_show_success_without_poe_ninja_fetch(self):
        cache_dir = self._cache_dir()
        show_transport = FakeTransport((_response(currency_payload()),))
        ninja_transport = FakeTransport((_response(currency_payload()),))
        chain = LiveEconomyProviderChain((
            _provider(cache_dir, show_transport),
            _ninja_provider(cache_dir, ninja_transport),
        ))

        result = chain.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF)
        self.assertEqual(result.selected_provider_id, "poe.show")
        self.assertEqual(result.provider_order, ("poe.show", "poe.ninja"))
        self.assertEqual(result.attempted_provider_ids, ("poe.show",))
        self.assertEqual(len(show_transport.requests), 1)
        self.assertEqual(len(ninja_transport.requests), 0)
        self.assertEqual(quote.source, "poe.show")

    def test_provider_chain_uses_clean_poe_show_cache_without_poe_ninja_fetch(self):
        cache_dir = self._cache_dir()
        show_transport = FakeTransport((_response(currency_payload()),))
        ninja_transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload()),
        ))
        show_provider = _provider(cache_dir, show_transport)
        show_provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        chain = LiveEconomyProviderChain((
            show_provider,
            _ninja_provider(cache_dir, ninja_transport),
        ))

        result = chain.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(minutes=10))

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF + timedelta(minutes=10))
        self.assertEqual(result.selected_provider_id, "poe.show")
        self.assertEqual(result.cache_hit_count, 1)
        self.assertEqual(len(show_transport.requests), 1)
        self.assertEqual(len(ninja_transport.requests), 0)
        self.assertEqual(quote.source, "poe.show")

    def test_provider_chain_falls_back_to_poe_ninja_on_poe_show_5xx(self):
        cache_dir = self._cache_dir()
        show_transport = FakeTransport((HttpResponse(status_code=522, headers={}, body=""),))
        ninja_transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload_with_metadata_annulment()),
        ))
        chain = LiveEconomyProviderChain((
            _provider(cache_dir, show_transport),
            _ninja_provider(cache_dir, ninja_transport),
        ))

        result = chain.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF)
        self.assertEqual(result.selected_provider_id, "poe.ninja")
        self.assertEqual(result.attempted_provider_ids, ("poe.show", "poe.ninja"))
        self.assertIsNotNone(quote)
        self.assertEqual(quote.source, "poe.ninja")
        self.assertEqual(quote.normalized_value.amount, Decimal("170.00"))
        self.assertTrue(quote.snapshot_id.startswith("economy-snapshot:live-poe-ninja:"))
        self.assertTrue(any("poe.show" in warning and "HTTP 522" in warning for warning in result.warnings))
        self.assertIn("/leagues", ninja_transport.requests[0][0])
        self.assertIn("league=runes-of-aldur", ninja_transport.requests[1][0])

    def test_provider_chain_prefers_fresh_poe_ninja_over_poe_show_error_cache(self):
        cache_dir = self._cache_dir()
        seed_show_transport = FakeTransport((_response(currency_payload()),))
        failing_show_transport = FakeTransport((TimeoutError("show down"),))
        ninja_transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload_with_metadata_annulment()),
        ))
        _provider(cache_dir, seed_show_transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        chain = LiveEconomyProviderChain((
            _provider(cache_dir, failing_show_transport),
            _ninja_provider(cache_dir, ninja_transport),
        ))

        result = chain.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(hours=2))

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF + timedelta(hours=2))
        self.assertEqual(result.selected_provider_id, "poe.ninja")
        self.assertEqual(quote.source, "poe.ninja")
        self.assertTrue(any("poe.show" in warning and "show down" in warning for warning in result.warnings))

    def test_poe_ninja_currency_payload_resolves_orb_of_annulment_stable_identity(self):
        transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload_with_metadata_annulment()),
        ))

        result = _ninja_provider(self._cache_dir(), transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        quote = result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF)
        self.assertIsNotNone(quote)
        self.assertEqual(result.selected_provider_id, "poe.ninja")
        self.assertEqual(quote.source, "poe.ninja")
        self.assertEqual(quote.asset_id, ORB_OF_ANNULMENT_ASSET_ID)
        self.assertEqual(quote.provenance[0].source_id, "poe.ninja")

    def test_provider_chain_fails_closed_when_both_providers_fail(self):
        chain = LiveEconomyProviderChain((
            _provider(self._cache_dir(), FakeTransport((HttpResponse(status_code=522, headers={}, body=""),))),
            _ninja_provider(self._cache_dir(), FakeTransport((TimeoutError("ninja leagues down"), TimeoutError("ninja down")))),
        ))

        result = chain.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        self.assertEqual(result.snapshots, ())
        self.assertIsNone(result.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF))
        self.assertEqual(result.attempted_provider_ids, ("poe.show", "poe.ninja"))
        self.assertTrue(any("poe.show" in warning for warning in result.warnings))
        self.assertTrue(any("poe.ninja" in warning for warning in result.warnings))

    def test_provider_specific_caches_do_not_cross_contaminate(self):
        cache_dir = self._cache_dir()
        ninja_transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload()),
        ))

        result = _ninja_provider(cache_dir, ninja_transport).economy_repository(EconomyRepository(()), LEAGUE, AS_OF)

        self.assertEqual(result.selected_provider_id, "poe.ninja")
        self.assertEqual(len(list(Path(cache_dir).glob("poe-ninja-*.json"))), 2)
        self.assertEqual(len(list(Path(cache_dir).glob("poe-show-*.json"))), 0)

    def test_poe_ninja_cache_reuse_avoids_repeated_http_within_refresh_interval(self):
        cache_dir = self._cache_dir()
        transport = FakeTransport((
            _response(poe_ninja_leagues_payload()),
            _response(currency_payload(), etag="ninja-currency-v1"),
        ))
        provider = _ninja_provider(cache_dir, transport)

        first = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF)
        second = provider.economy_repository(EconomyRepository(()), LEAGUE, AS_OF + timedelta(minutes=10))

        quote = second.repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF + timedelta(minutes=10))
        self.assertEqual(first.fetched_count, 1)
        self.assertEqual(second.fetched_count, 0)
        self.assertEqual(second.cache_hit_count, 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(quote.source, "poe.ninja")


def _provider(tmp: str, transport: FakeTransport) -> PoeShowLiveEconomyProvider:
    return PoeShowLiveEconomyProvider(
        Path(tmp),
        LiveEconomyProviderConfig(
            enabled=True,
            base_url="https://poe.show/poe2/api/economy",
            user_agent="DonnieCraftShell test",
            timeout_seconds=Decimal("2"),
            refresh_interval=timedelta(hours=1),
            categories=(EconomyCategory.CURRENCY.value,),
        ),
        transport,
    )


def _ninja_provider(tmp: str, transport: FakeTransport) -> PoeNinjaLiveEconomyProvider:
    return PoeNinjaLiveEconomyProvider(
        Path(tmp),
        LiveEconomyProviderConfig(
            enabled=True,
            base_url="https://poe.ninja/poe2/api/economy",
            user_agent="DonnieCraftShell test",
            timeout_seconds=Decimal("2"),
            refresh_interval=timedelta(hours=1),
            categories=(EconomyCategory.CURRENCY.value,),
        ),
        transport,
    )


def _response(payload: dict, etag: str | None = None) -> HttpResponse:
    headers = {"etag": etag} if etag else {}
    return HttpResponse(status_code=200, headers=headers, body=json.dumps(payload))


def currency_payload() -> dict:
    return {
        "core": {
            "primary": "divine",
            "secondary": "exalted",
            "rates": {"exalted": "340"},
        },
        "lines": [
            {"id": "divine", "primaryValue": "1", "volumePrimaryValue": "1000"},
            {"id": "perfect-exalted-orb", "primaryValue": "2.5", "volumePrimaryValue": "20"},
            {"id": "orb-of-annulment", "primaryValue": "6", "volumePrimaryValue": "33"},
        ],
    }


def poe_ninja_leagues_payload() -> list[dict]:
    return [{"id": "runes-of-aldur", "text": LEAGUE}]


def currency_payload_with_metadata_annulment() -> dict:
    payload = currency_payload()
    payload["core"]["items"] = [
        {"id": "divine", "name": "Divine Orb", "category": "Currency", "detailsId": "divine-orb"},
        {"id": "exalted", "name": "Exalted Orb", "category": "Currency", "detailsId": "exalted-orb"},
        {
            "id": "provider-specific-annulment-id",
            "name": "Orb of Annulment",
            "category": "Currency",
            "detailsId": "orb-of-annulment",
        },
    ]
    payload["lines"] = [
        {"id": "divine", "primaryValue": "1", "volumePrimaryValue": "1000"},
        {"id": "provider-specific-annulment-id", "primaryValue": "0.5", "volumePrimaryValue": "11"},
    ]
    return payload


def ritual_payload() -> dict:
    return {
        "core": {
            "primary": "divine",
            "secondary": "exalted",
            "rates": {"exalted": "340"},
        },
        "lines": [
            {"id": "omen-of-greater-annulment", "primaryValue": "2", "volumePrimaryValue": "10"},
        ],
    }


def essence_payload() -> dict:
    return {
        "core": {
            "primary": "divine",
            "secondary": "exalted",
            "rates": {"exalted": "340"},
        },
        "lines": [
            {"id": "essence-of-hysteria", "primaryValue": "3", "volumePrimaryValue": "5"},
        ],
    }


if __name__ == "__main__":
    unittest.main()
