import unittest
from decimal import Decimal

from packages.shared.donniecraftshell_contracts.domain import (
    AdvisorRecommendation,
    BankrollContext,
    Confidence,
    CraftAction,
    CraftOutcome,
    EconomicValue,
    GameContext,
    ParsedItem,
    Rarity,
    RecommendationStatus,
    RiskProfile,
    SimulationResult,
    Valuation,
)


class DomainContractTests(unittest.TestCase):
    def test_confidence_score_must_be_between_zero_and_one(self):
        Confidence(score=Decimal("0"))
        Confidence(score=Decimal("1"))

        with self.assertRaises(ValueError):
            Confidence(score=Decimal("1.01"))

    def test_valuation_range_must_contain_estimate(self):
        Valuation(
            plausible_low=EconomicValue(Decimal("1")),
            estimated_value=EconomicValue(Decimal("2")),
            plausible_high=EconomicValue(Decimal("3")),
        )

        with self.assertRaises(ValueError):
            Valuation(
                plausible_low=EconomicValue(Decimal("3")),
                estimated_value=EconomicValue(Decimal("2")),
                plausible_high=EconomicValue(Decimal("4")),
            )

    def test_unknown_probability_remains_unknown(self):
        outcome = CraftOutcome(probability=None)

        self.assertIsNone(outcome.probability)

    def test_sell_now_is_normal_candidate_action(self):
        action = CraftAction.sell_now()

        self.assertEqual(action.action_id, "core.action.sell_now")
        self.assertTrue(action.simulation_supported)

    def test_recommendation_can_be_no_recommendation(self):
        recommendation = AdvisorRecommendation(
            status=RecommendationStatus.NO_RECOMMENDATION,
            current_item_valuation=None,
            candidate_actions=(CraftAction.sell_now(),),
            selected_action=None,
            warnings=("insufficient verified data",),
        )

        self.assertEqual(recommendation.status, RecommendationStatus.NO_RECOMMENDATION)

    def test_no_recommendation_cannot_select_action(self):
        with self.assertRaises(ValueError):
            AdvisorRecommendation(
                status=RecommendationStatus.NO_RECOMMENDATION,
                current_item_valuation=None,
                candidate_actions=(CraftAction.sell_now(),),
                selected_action=CraftAction.sell_now(),
            )

    def test_bankroll_risk_does_not_mutate_raw_expected_value(self):
        source_item = ParsedItem(
            analysis_id="analysis-test",
            raw_clipboard_text="unverified clipboard text",
            game_context=GameContext(game="Path of Exile 2"),
            rarity=Rarity.RARE,
            item_class="generic-item-class",
        )
        raw_expected = EconomicValue(Decimal("10.5"))
        simulation = SimulationResult(
            source_item=source_item,
            craft_action=CraftAction.sell_now(),
            expected_net_value=raw_expected,
        )
        bankroll = BankrollContext(
            risk_profile=RiskProfile.CONSERVATIVE,
            bankroll=EconomicValue(Decimal("20")),
            exposure_percentage=Decimal("0.80"),
        )

        self.assertEqual(simulation.expected_net_value, raw_expected)
        self.assertEqual(bankroll.exposure_percentage, Decimal("0.80"))

    def test_currency_values_reject_binary_floats(self):
        with self.assertRaises(TypeError):
            EconomicValue(1.1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
