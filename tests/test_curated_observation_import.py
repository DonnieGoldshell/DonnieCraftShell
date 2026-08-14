import unittest
from datetime import datetime, timezone

from packages.shared.donniecraftshell_contracts.curated_observation_import import (
    CURATED_OBSERVATION_IMPORT_VERSION,
    build_empirical_datasets_from_curated_export,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import EmpiricalProbabilityRepository
from packages.shared.donniecraftshell_contracts.probability import ProbabilityCompleteness, ProbabilityContext
from tests.test_empirical_probability_pipeline import parsed_quiver_6, synthetic_outcome_set


BUILT_AT = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)


def accepted_export(*records: dict) -> dict:
    return {
        "review_version": "dc-observation-review-v1",
        "exported_at": "2026-08-14T07:50:00+00:00",
        "observations": list(records),
        "warnings": ["review warning carried forward"],
    }


def record(
    raw_record_id: str,
    *,
    outcome_id: str | None = "outcome-a",
    unclassified: bool = False,
    league: str = "Runes of Aldur",
    synthetic: bool = False,
) -> dict:
    return {
        "raw_record_id": raw_record_id,
        "action_id": "dc:poe2:craft-action:orb-of-annulment",
        "source_outcome_set_id": "backend-outcome-set:annulment:curated-build",
        "item_class": "Quivers",
        "league": league,
        "game": "Path of Exile 2",
        "game_version": "synthetic-test-version",
        "crafting_dataset_version": "crafting-actions-test",
        "modifier_dataset_version": "modifier-dataset-test",
        "observed_at": "2026-08-14T07:45:00+00:00",
        "source_id": "curated-build-test",
        "source_type": "MANUAL_RESEARCH",
        "source_uri": "local://tests/curated-observation-build",
        "synthetic": synthetic,
        "outcome_id": outcome_id,
        "unclassified": unclassified,
        "verification_status": "NEEDS_VERIFICATION",
        "notes": "synthetic test-only curated import",
    }


class CuratedObservationImportTests(unittest.TestCase):
    def test_valid_accepted_observations_build_task15a_compatible_dataset(self):
        result = build_empirical_datasets_from_curated_export(
            accepted_export(record("raw-1", outcome_id="outcome-a"), record("raw-2", outcome_id="outcome-b")),
            built_at=BUILT_AT,
            dataset_id_prefix="curated-test",
        )

        self.assertEqual(result.build_version, CURATED_OBSERVATION_IMPORT_VERSION)
        self.assertEqual(result.source_record_count, 2)
        self.assertEqual(result.imported_record_count, 2)
        self.assertEqual(result.accepted_record_count, 2)
        self.assertEqual(result.invalid_record_count, 0)
        self.assertEqual(result.dataset_count, 1)
        self.assertEqual(result.datasets[0].observations[0].observed_count, 1)
        self.assertTrue(result.dataset_ids[0].startswith("curated-test-"))

    def test_malformed_accepted_records_are_rejected_conservatively(self):
        result = build_empirical_datasets_from_curated_export(
            accepted_export({"raw_record_id": "malformed-record"}),
            built_at=BUILT_AT,
        )

        self.assertEqual(result.source_record_count, 1)
        self.assertEqual(result.imported_record_count, 0)
        self.assertEqual(result.accepted_record_count, 0)
        self.assertEqual(result.invalid_record_count, 1)
        self.assertEqual(result.dataset_count, 0)
        self.assertEqual(result.rejected_records[0].raw_record_id, "malformed-record")
        self.assertTrue(any("Malformed accepted-export records" in warning for warning in result.warnings))

    def test_duplicate_raw_ids_are_not_double_counted(self):
        duplicate = record("duplicate-raw", outcome_id="outcome-a")
        result = build_empirical_datasets_from_curated_export(
            accepted_export(duplicate, duplicate),
            built_at=BUILT_AT,
        )

        self.assertEqual(result.imported_record_count, 2)
        self.assertEqual(result.accepted_record_count, 1)
        self.assertEqual(result.duplicate_record_count, 1)
        self.assertEqual(result.datasets[0].observations[0].raw_record_ids, ("duplicate-raw",))

    def test_unclassified_observations_remain_in_denominator_semantics(self):
        result = build_empirical_datasets_from_curated_export(
            accepted_export(
                record("classified-raw", outcome_id="outcome-a"),
                record("unclassified-raw", outcome_id=None, unclassified=True),
            ),
            built_at=BUILT_AT,
        )

        self.assertEqual(result.accepted_record_count, 2)
        self.assertEqual(result.unclassified_record_count, 1)
        self.assertEqual(result.datasets[0].unclassified_count, 1)
        self.assertEqual(result.datasets[0].observations[0].observed_count, 1)

    def test_mixed_contexts_partition_into_separate_datasets(self):
        result = build_empirical_datasets_from_curated_export(
            accepted_export(
                record("league-a", league="Runes of Aldur"),
                record("league-b", league="Different League"),
            ),
            built_at=BUILT_AT,
        )

        self.assertEqual(result.accepted_record_count, 2)
        self.assertEqual(result.dataset_count, 2)
        self.assertEqual(sorted(dataset.league for dataset in result.datasets), ["Different League", "Runes of Aldur"])

    def test_dataset_ids_are_deterministic_and_content_sensitive(self):
        first = build_empirical_datasets_from_curated_export(
            accepted_export(record("raw-1", outcome_id="outcome-a")),
            built_at=BUILT_AT,
        )
        same = build_empirical_datasets_from_curated_export(
            accepted_export(record("raw-1", outcome_id="outcome-a")),
            built_at=BUILT_AT,
        )
        different = build_empirical_datasets_from_curated_export(
            accepted_export(record("raw-2", outcome_id="outcome-a")),
            built_at=BUILT_AT,
        )

        self.assertEqual(first.dataset_ids, same.dataset_ids)
        self.assertNotEqual(first.dataset_ids, different.dataset_ids)

    def test_dataset_build_alone_does_not_activate_probability_for_unrelated_advisor_requests(self):
        result = build_empirical_datasets_from_curated_export(
            accepted_export(record("raw-1", outcome_id="outcome-a")),
            built_at=BUILT_AT,
        )

        model = EmpiricalProbabilityRepository(()).to_provider().get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version=result.dataset_ids[0]),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))


if __name__ == "__main__":
    unittest.main()
