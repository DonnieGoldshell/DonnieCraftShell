import copy
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionDefinition,
    CraftActionEngine,
    CraftActionKind,
    CraftActionPrecondition,
    CraftApplicabilityStatus,
    CraftingDatasetSnapshot,
    PreconditionKind,
    RequiredMaterial,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import (
    Confidence,
    DataProvenance,
    SourceType,
    VerificationStatus,
)
from packages.shared.donniecraftshell_contracts.economy import (
    ESSENCE_OF_HYSTERIA_ASSET_ID,
    EXALTED_ASSET_ID,
    OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID,
    OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID,
    ORB_OF_ANNULMENT_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


ROOT = Path(__file__).resolve().parents[1]
CRAFTING_DATASET = (
    ROOT
    / "data"
    / "normalized"
    / "crafting"
    / "crafting-actions-poe2-quiver-2026-08-12-research"
    / "actions.json"
)
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def parsed_fixture(name: str):
    result = parse_clipboard_item(fixture(name))
    assert result.item is not None
    return result.item


def action_by_id(dataset: CraftingDatasetSnapshot, action_id: str) -> CraftActionDefinition:
    return next(action for action in dataset.actions if action.action_id == action_id)


def provenance() -> DataProvenance:
    return DataProvenance(
        source_id="synthetic-task-7a-test",
        source_type=SourceType.INTERNAL,
        retrieved_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        verification_status=VerificationStatus.VERIFIED,
        confidence=Confidence(score=Decimal("1")),
    )


class CraftActionContractTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.engine = CraftActionEngine(self.dataset)

    def test_dataset_version_is_explicitly_selected(self):
        self.assertEqual(
            self.dataset.dataset_id,
            "crafting-actions-poe2-quiver-2026-08-12-research",
        )
        self.assertGreaterEqual(len(self.dataset.actions), 1)

    def test_required_materials_use_economy_asset_ids_not_action_ids(self):
        annul = action_by_id(self.dataset, "dc:poe2:craft-action:orb-of-annulment")
        essence = action_by_id(self.dataset, "dc:poe2:craft-action:essence-of-hysteria")

        self.assertEqual(annul.required_materials[0].asset_id, ORB_OF_ANNULMENT_ASSET_ID)
        self.assertEqual(essence.required_materials[0].asset_id, ESSENCE_OF_HYSTERIA_ASSET_ID)
        self.assertNotEqual(annul.action_id, annul.required_materials[0].asset_id)

    def test_decimal_required_material_quantity_is_enforced(self):
        material = RequiredMaterial(asset_id=EXALTED_ASSET_ID, quantity="1")

        self.assertEqual(material.quantity, Decimal("1"))
        with self.assertRaises(TypeError):
            RequiredMaterial(asset_id=EXALTED_ASSET_ID, quantity=1.0)

    def test_verified_action_definition_requires_provenance(self):
        with self.assertRaises(ValueError):
            CraftActionDefinition(
                action_id="dc:test:action:verified-without-source",
                display_name="Synthetic Verified Action",
                kind=CraftActionKind.CURRENCY,
                required_materials=(RequiredMaterial(asset_id=EXALTED_ASSET_ID, quantity="1"),),
                preconditions=(),
                mechanic_summary="Synthetic test action.",
                verification_status=VerificationStatus.VERIFIED,
            )

    def test_verified_precondition_requires_provenance(self):
        with self.assertRaises(ValueError):
            CraftActionPrecondition(
                kind=PreconditionKind.NOT_CORRUPTED,
                verification_status=VerificationStatus.VERIFIED,
            )

    def test_annulment_is_applicable_to_non_corrupted_rare_with_modifiers(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        annul = action_by_id(self.dataset, "dc:poe2:craft-action:orb-of-annulment")

        result = self.engine.evaluate_action(annul, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.APPLICABLE)
        self.assertEqual(result.failed_preconditions, ())
        self.assertEqual(result.unknown_preconditions, ())

    def test_corrupted_restriction_prevents_action_when_verified(self):
        item = parsed_fixture("quiver_5_rare_corrupted_advanced.txt")
        annul = action_by_id(self.dataset, "dc:poe2:craft-action:orb-of-annulment")

        result = self.engine.evaluate_action(annul, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertIn("item is corrupted", result.failed_preconditions)

    def test_exalted_open_slot_requirement_remains_unknown_without_verified_capacity(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        exalt = action_by_id(self.dataset, "dc:poe2:craft-action:exalted-orb")

        result = self.engine.evaluate_action(exalt, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.UNKNOWN)
        self.assertTrue(
            any("open" in reason.lower() or "capacity" in reason.lower() for reason in result.unknown_preconditions)
        )

    def test_magic_item_is_not_applicable_for_exalted_orb(self):
        item = parsed_fixture("quiver_4_magic_advanced.txt")
        exalt = action_by_id(self.dataset, "dc:poe2:craft-action:exalted-orb")

        result = self.engine.evaluate_action(exalt, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertTrue(any("MAGIC" in reason for reason in result.failed_preconditions))

    def test_unknown_remains_distinct_from_not_applicable(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        perfect_exalt = action_by_id(self.dataset, "dc:poe2:craft-action:perfect-exalted-orb")

        result = self.engine.evaluate_action(perfect_exalt, item)

        self.assertEqual(result.status, CraftApplicabilityStatus.UNKNOWN)
        self.assertNotEqual(result.status, CraftApplicabilityStatus.NOT_APPLICABLE)

    def test_essence_hysteria_material_is_mapped_and_applicability_is_separate_from_simulation(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        essence = action_by_id(self.dataset, "dc:poe2:craft-action:essence-of-hysteria")

        self.assertFalse(essence.simulation_supported)
        self.assertEqual(essence.required_materials[0].asset_id, ESSENCE_OF_HYSTERIA_ASSET_ID)
        self.assertEqual(
            self.engine.evaluate_action(essence, item).status,
            CraftApplicabilityStatus.APPLICABLE,
        )

    def test_exaltation_omen_actions_use_composed_required_materials(self):
        sinistral = action_by_id(
            self.dataset,
            "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation",
        )
        dextral = action_by_id(
            self.dataset,
            "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation",
        )

        self.assertEqual(
            tuple(material.asset_id for material in sinistral.required_materials),
            (EXALTED_ASSET_ID, OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID),
        )
        self.assertEqual(
            tuple(material.asset_id for material in dextral.required_materials),
            (EXALTED_ASSET_ID, OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID),
        )

    def test_candidate_actions_return_statuses_without_recommendation_logic(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")

        results = self.engine.get_candidate_actions(item)
        statuses = {result.status for result in results}

        self.assertIn(CraftApplicabilityStatus.APPLICABLE, statuses)
        self.assertIn(CraftApplicabilityStatus.UNKNOWN, statuses)

    def test_parsed_item_remains_immutable_after_applicability_evaluation(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        before = copy.deepcopy(item)
        action = action_by_id(self.dataset, "dc:poe2:craft-action:orb-of-annulment")

        self.engine.evaluate_action(action, item)

        self.assertEqual(item, before)

    def test_synthetic_verified_open_slot_precondition_can_be_applicable(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        affix_state = item.affix_state
        assert affix_state is not None
        item_with_verified_open_slot = item.__class__(
            **{
                **item.__dict__,
                "affix_state": affix_state.__class__(
                    **{
                        **affix_state.__dict__,
                        "open_prefix_count": 1,
                        "open_suffix_count": 0,
                    }
                ),
            }
        )
        synthetic = CraftActionDefinition(
            action_id="dc:test:action:synthetic-open-slot",
            display_name="Synthetic Open Slot Action",
            kind=CraftActionKind.CURRENCY,
            required_materials=(RequiredMaterial(asset_id=PERFECT_EXALTED_ASSET_ID, quantity="1"),),
            preconditions=(
                CraftActionPrecondition(
                    kind=PreconditionKind.HAS_OPEN_AFFIX_SLOT,
                    verification_status=VerificationStatus.VERIFIED,
                    provenance=(provenance(),),
                ),
            ),
            mechanic_summary="Synthetic test action.",
            provenance=(provenance(),),
        )

        result = self.engine.evaluate_action(synthetic, item_with_verified_open_slot)

        self.assertEqual(result.status, CraftApplicabilityStatus.APPLICABLE)


if __name__ == "__main__":
    unittest.main()
