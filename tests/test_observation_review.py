import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
    aggregate_observations,
    load_empirical_observation_files,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import EmpiricalProbabilityRepository
from packages.shared.donniecraftshell_contracts.observation_review import (
    OBSERVATION_REVIEW_VERSION,
    ObservationReviewDecision,
    ObservationReviewStatus,
    review_observation_batches,
)
from packages.shared.donniecraftshell_contracts.probability import ProbabilityCompleteness, ProbabilityContext
from tests.test_empirical_probability_pipeline import parsed_quiver_6, synthetic_outcome_set


REVIEWED_AT = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def observation(
    raw_record_id: str = "manual-craft-observation-1",
    *,
    outcome_id: str | None = "outcome-1",
    unclassified: bool = False,
    classification_method: str = "AUTOMATIC",
    synthetic: bool = False,
    league: str = "Runes of Aldur",
) -> dict:
    return {
        "raw_record_id": raw_record_id,
        "action_id": "dc:poe2:craft-action:orb-of-annulment",
        "source_outcome_set_id": "backend-outcome-set:annulment:test",
        "item_class": "Quivers",
        "league": league,
        "game": "Path of Exile 2",
        "game_version": "synthetic-test-version",
        "crafting_dataset_version": "crafting-actions-test",
        "modifier_dataset_version": "modifier-dataset-test",
        "observed_at": "2026-08-13T10:00:00+00:00",
        "source_id": "test-recorder",
        "source_type": "MANUAL_RESEARCH",
        "source_uri": "local://tests/observation-review",
        "synthetic": synthetic,
        "outcome_id": outcome_id,
        "unclassified": unclassified,
        "verification_status": "NEEDS_VERIFICATION",
        "notes": "synthetic observation review test",
        "classification_method": classification_method,
        "classification_reason": "test classification",
        "classification_warnings": [],
        "before_item_fingerprint": "before-fingerprint",
        "after_item_fingerprint": "after-fingerprint",
        "recorder_version": "dc-observation-recorder-v1",
        "warnings": [],
    }


class ObservationReviewTests(unittest.TestCase):
    def test_valid_recorded_observation_loads_as_pending(self):
        result = review_observation_batches(({"observations": [observation()]},), reviewed_at=REVIEWED_AT)

        self.assertEqual(result.records[0].decision.status, ObservationReviewStatus.PENDING)
        self.assertEqual(result.accepted_export["observations"], [])

    def test_accepted_export_preserves_original_record_shape(self):
        record = observation()
        result = review_observation_batches(
            ({"observations": [record]},),
            (ObservationReviewDecision(record["raw_record_id"], ObservationReviewStatus.ACCEPTED, note="reviewed"),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertEqual(result.accepted_export["observations"], [record])
        self.assertEqual(result.accepted_export["review_version"], OBSERVATION_REVIEW_VERSION)

    def test_rejected_and_pending_records_are_absent_from_accepted_export(self):
        rejected = observation("manual-craft-observation-rejected")
        pending = observation("manual-craft-observation-pending")
        result = review_observation_batches(
            ({"observations": [rejected, pending]},),
            (ObservationReviewDecision(rejected["raw_record_id"], ObservationReviewStatus.REJECTED, note="bad context"),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertEqual(result.accepted_export["observations"], [])
        self.assertEqual(result.manifest.rejected_count, 1)
        self.assertEqual(result.manifest.pending_count, 1)

    def test_unclassified_can_be_accepted_without_coercion(self):
        record = observation(
            "manual-craft-observation-unclassified",
            outcome_id=None,
            unclassified=True,
            classification_method="UNCLASSIFIED",
        )
        result = review_observation_batches(
            ({"observations": [record]},),
            (ObservationReviewDecision(record["raw_record_id"], ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        exported = result.accepted_export["observations"][0]
        self.assertTrue(exported["unclassified"])
        self.assertIsNone(exported["outcome_id"])
        self.assertEqual(exported["classification_method"], "UNCLASSIFIED")

    def test_manual_classification_remains_manual(self):
        record = observation("manual-craft-observation-manual", classification_method="MANUAL")
        result = review_observation_batches(
            ({"observations": [record]},),
            (ObservationReviewDecision(record["raw_record_id"], ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertEqual(result.accepted_export["observations"][0]["classification_method"], "MANUAL")
        self.assertTrue(any("Manual classification remains manual" in warning for warning in result.records[0].warnings))

    def test_duplicate_raw_ids_are_manifested_and_not_exported_twice(self):
        first = observation("manual-craft-observation-duplicate")
        duplicate = observation("manual-craft-observation-duplicate")
        result = review_observation_batches(
            ({"observations": [first]}, {"observations": [duplicate]}),
            (ObservationReviewDecision(first["raw_record_id"], ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertEqual(len(result.accepted_export["observations"]), 1)
        self.assertEqual(result.manifest.duplicate_count, 1)
        self.assertTrue(any("Duplicate raw_record_id" in warning for warning in result.warnings))

    def test_invalid_accepted_record_is_not_exported_and_validation_is_manifested(self):
        malformed = {"raw_record_id": "manual-craft-observation-malformed"}
        result = review_observation_batches(
            ({"observations": [malformed]},),
            (ObservationReviewDecision(malformed["raw_record_id"], ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertEqual(result.accepted_export["observations"], [])
        self.assertFalse(result.records[0].valid_for_import)
        self.assertTrue(any("Task 15C import validation failed" in warning for warning in result.records[0].warnings))
        self.assertTrue(any("was not exported" in warning for warning in result.warnings))
        manifest_record = result.manifest.to_dict()["records"][0]
        self.assertEqual(manifest_record["status"], "ACCEPTED")
        self.assertFalse(manifest_record["valid_for_import"])
        self.assertFalse(manifest_record["exported"])

    def test_absent_review_decision_is_surfaced_as_warning(self):
        result = review_observation_batches(
            ({"observations": [observation()]},),
            (ObservationReviewDecision("manual-craft-observation-absent", ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        self.assertTrue(any("manual-craft-observation-absent" in warning for warning in result.warnings))
        self.assertEqual(result.accepted_export["observations"], [])

    def test_synthetic_and_non_synthetic_mix_is_warned_not_silent(self):
        synthetic = observation("manual-craft-observation-synthetic", synthetic=True)
        real = observation("manual-craft-observation-real", synthetic=False)
        result = review_observation_batches(
            ({"observations": [synthetic, real]},),
            (
                ObservationReviewDecision(synthetic["raw_record_id"], ObservationReviewStatus.ACCEPTED),
                ObservationReviewDecision(real["raw_record_id"], ObservationReviewStatus.ACCEPTED),
            ),
            reviewed_at=REVIEWED_AT,
        )

        self.assertTrue(any("mixes synthetic and non-synthetic" in warning for warning in result.warnings))

    def test_manifest_preserves_decision_note_timestamp_and_provenance_references(self):
        record = observation()
        result = review_observation_batches(
            ({"observations": [record]},),
            (ObservationReviewDecision(record["raw_record_id"], ObservationReviewStatus.REJECTED, note="duplicate screenshot"),),
            reviewed_at=REVIEWED_AT,
        )

        manifest_record = result.manifest.to_dict()["records"][0]
        self.assertEqual(manifest_record["raw_record_id"], record["raw_record_id"])
        self.assertEqual(manifest_record["status"], "REJECTED")
        self.assertEqual(manifest_record["note"], "duplicate screenshot")
        self.assertEqual(manifest_record["reviewed_at"], REVIEWED_AT.isoformat())
        self.assertEqual(manifest_record["source_id"], record["source_id"])
        self.assertEqual(manifest_record["before_item_fingerprint"], record["before_item_fingerprint"])
        self.assertFalse(manifest_record["exported"])

    def test_accepted_export_round_trips_through_empirical_importer(self):
        record = observation()
        result = review_observation_batches(
            ({"observations": [record]},),
            (ObservationReviewDecision(record["raw_record_id"], ObservationReviewStatus.ACCEPTED),),
            reviewed_at=REVIEWED_AT,
        )

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "accepted.json"
            path.write_text(json.dumps(result.accepted_export), encoding="utf-8")
            imported = load_empirical_observation_files((path,))
            aggregation = aggregate_observations(imported, retrieved_at=REVIEWED_AT)

        self.assertEqual(aggregation.accepted_record_count, 1)
        self.assertEqual(aggregation.datasets[0].observations[0].raw_record_ids, (record["raw_record_id"],))

    def test_review_does_not_change_probability_readiness(self):
        model = EmpiricalProbabilityRepository(()).to_provider().get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))


if __name__ == "__main__":
    unittest.main()
