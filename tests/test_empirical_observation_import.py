import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
    aggregate_observations,
    load_empirical_observation_files,
    raw_empirical_probability_dataset_to_dict,
    write_aggregated_empirical_dataset,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import EmpiricalProbabilityRepository
from packages.shared.donniecraftshell_contracts.probability import ProbabilityCompleteness, ProbabilityContext
from tests.test_empirical_probability_pipeline import parsed_quiver_6, synthetic_outcome_set


ROOT = Path(__file__).resolve().parents[1]


def observation(
    raw_record_id: str,
    outcome_id: str | None = "synthetic-outcome-a",
    *,
    action_id: str = "dc:test:craft-action:synthetic-annulment",
    league: str = "Synthetic Test League",
    game_version: str | None = "synthetic-test-version",
    synthetic: bool = True,
    unclassified: bool = False,
) -> dict:
    return {
        "raw_record_id": raw_record_id,
        "action_id": action_id,
        "source_outcome_set_id": "synthetic-quiver-analysis:dc:test:craft-action:synthetic-annulment",
        "item_class": "Quivers",
        "league": league,
        "game": "Path of Exile 2",
        "game_version": game_version,
        "crafting_dataset_version": "synthetic-crafting-dataset",
        "modifier_dataset_version": "synthetic-modifier-dataset",
        "observed_at": "2026-08-13T00:00:00+00:00",
        "source_id": "synthetic-observation-batch",
        "source_type": "INTERNAL",
        "source_uri": "local://tests/synthetic-observations",
        "synthetic": synthetic,
        "outcome_id": outcome_id,
        "unclassified": unclassified,
        "verification_status": "NEEDS_VERIFICATION",
    }


class EmpiricalObservationImportTests(unittest.TestCase):
    def test_valid_observation_batch_aggregates_to_raw_probability_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "observations.json"
            path.write_text(
                json.dumps(
                    [
                        observation("record-1", "synthetic-outcome-a"),
                        observation("record-2", "synthetic-outcome-b"),
                        observation("record-3", "synthetic-outcome-b"),
                    ]
                ),
                encoding="utf-8",
            )

            result = aggregate_observations(
                load_empirical_observation_files((path,)),
                retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
                dataset_id_prefix="synthetic-import",
            )

        self.assertEqual(result.accepted_record_count, 3)
        self.assertEqual(result.duplicate_record_count, 0)
        self.assertEqual(len(result.datasets), 1)
        dataset = result.datasets[0]
        counts = {item.outcome_id: item.observed_count for item in dataset.observations}
        self.assertEqual(counts["synthetic-outcome-a"], 1)
        self.assertEqual(counts["synthetic-outcome-b"], 2)
        self.assertEqual(dataset.unclassified_count, 0)
        self.assertEqual(dataset.observations[1].raw_record_ids, ("record-2", "record-3"))

    def test_duplicate_raw_record_ids_do_not_increase_counts(self):
        batch = load_empirical_observation_files((self._json_file([observation("record-1"), observation("record-1")]),))

        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc))

        self.assertEqual(result.accepted_record_count, 1)
        self.assertEqual(result.duplicate_record_count, 1)
        self.assertEqual(result.datasets[0].observations[0].observed_count, 1)

    def test_unclassified_observations_remain_in_denominator(self):
        batch = load_empirical_observation_files(
            (
                self._json_file(
                    [
                        observation("record-1", "synthetic-outcome-a"),
                        observation("record-2", None, unclassified=True),
                    ]
                ),
            )
        )

        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc))

        self.assertEqual(result.unclassified_record_count, 1)
        self.assertEqual(result.datasets[0].unclassified_count, 1)

    def test_context_incompatible_records_are_partitioned(self):
        batch = load_empirical_observation_files(
            (
                self._json_file(
                    [
                        observation("record-1", "synthetic-outcome-a", league="League A"),
                        observation("record-2", "synthetic-outcome-a", league="League B"),
                    ]
                ),
            )
        )

        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc))

        self.assertEqual(len(result.datasets), 2)
        self.assertEqual({dataset.league for dataset in result.datasets}, {"League A", "League B"})

    def test_malformed_records_surface_validation_errors_without_corrupting_accepted_records(self):
        batch = load_empirical_observation_files(
            (
                self._json_file(
                    [
                        observation("record-1", "synthetic-outcome-a"),
                        {"raw_record_id": "bad-record", "outcome_id": "synthetic-outcome-a"},
                    ]
                ),
            )
        )
        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc))

        self.assertEqual(len(batch.rejected_records), 1)
        self.assertEqual(result.accepted_record_count, 1)
        self.assertEqual(result.rejected_records[0].raw_record_id, "bad-record")

    def test_synthetic_and_non_synthetic_records_are_not_mixed_silently(self):
        batch = load_empirical_observation_files(
            (
                self._json_file(
                    [
                        observation("record-1", "synthetic-outcome-a", synthetic=True),
                        observation("record-2", "synthetic-outcome-a", synthetic=False),
                    ]
                ),
            )
        )

        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc))

        self.assertEqual(len(result.datasets), 2)
        self.assertTrue(any("Synthetic and non-synthetic" in warning for warning in result.warnings))

    def test_csv_import_is_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "observations.csv"
            rows = [observation("record-1"), observation("record-2", "synthetic-outcome-b")]
            header = list(rows[0])
            path.write_text(
                ",".join(header) + "\n" + "\n".join(",".join(str(row.get(key) or "") for key in header) for row in rows),
                encoding="utf-8",
            )

            result = aggregate_observations(load_empirical_observation_files((path,)))

        self.assertEqual(result.accepted_record_count, 2)
        self.assertEqual(len(result.datasets[0].observations), 2)

    def test_aggregated_dataset_loads_into_repository_and_provider(self):
        batch = load_empirical_observation_files(
            (
                self._json_file(
                    [
                        *(observation(f"a-{index}", "synthetic-outcome-a") for index in range(30)),
                        *(observation(f"b-{index}", "synthetic-outcome-b") for index in range(30)),
                    ]
                ),
            )
        )
        result = aggregate_observations(batch, retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc), dataset_id_prefix="synthetic-import")
        with tempfile.TemporaryDirectory() as temp:
            output = write_aggregated_empirical_dataset(result.datasets[0], Path(temp) / "dataset.json")
            repository = EmpiricalProbabilityRepository.from_json_files((output,), allow_synthetic=True)

        model = repository.to_provider(allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(
                evidence_dataset_version=result.datasets[0].dataset_id,
                crafting_dataset_version="synthetic-crafting-dataset",
                modifier_dataset_version="synthetic-modifier-dataset",
                league="Synthetic Test League",
                game_version="synthetic-test-version",
            ),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.COMPLETE)
        self.assertEqual(model.total_known_probability_mass, Decimal("1.0"))

    def test_no_real_quiver_probability_changes_because_import_feature_exists(self):
        repository = EmpiricalProbabilityRepository(())

        model = repository.to_provider().get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))

    def test_cli_writes_dataset_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path = Path(temp) / "observations.json"
            output_path = Path(temp) / "dataset.json"
            input_path.write_text(json.dumps([observation("record-1")]), encoding="utf-8")
            command = [
                sys.executable,
                str(ROOT / "scripts" / "import_empirical_observations.py"),
                str(input_path),
                "--output",
                str(output_path),
                "--retrieved-at",
                "2026-08-13T00:00:00+00:00",
            ]

            first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("accepted=1", first.stdout)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("Refusing to overwrite", second.stderr)

    def test_serialized_dataset_shape_is_task15a_raw_format(self):
        result = aggregate_observations(
            load_empirical_observation_files((self._json_file([observation("record-1")]),)),
            retrieved_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
        )

        payload = raw_empirical_probability_dataset_to_dict(result.datasets[0])

        self.assertIn("observations", payload)
        self.assertIn("unclassified_count", payload)
        self.assertEqual(payload["observations"][0]["raw_record_ids"], ["record-1"])

    def _json_file(self, records: list[dict]) -> Path:
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with temp:
            json.dump(records, temp)
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return Path(temp.name)


if __name__ == "__main__":
    unittest.main()
