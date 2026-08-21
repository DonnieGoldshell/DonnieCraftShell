import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.app.main import app


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "first_playable_quiver_sample.txt"
START_SCRIPT = ROOT / "scripts" / "start_first_playable.ps1"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke_first_playable.ps1"
SMOKE_PYTHON = ROOT / "scripts" / "smoke_first_playable.py"


class FirstPlayableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.clipboard_text = SAMPLE.read_text(encoding="utf-8")

    def test_sample_quiver_payload_parses_through_public_api(self):
        response = self.client.post(
            "/api/v1/items/parse",
            json={
                "raw_clipboard_text": self.clipboard_text,
                "game": "Path of Exile 2",
                "league": "Runes of Aldur",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["error"])
        self.assertEqual(body["item"]["item_class"], "Quivers")
        self.assertEqual(body["item"]["base_type"], "Primed Quiver")

    def test_sample_quiver_payload_analyzes_as_honest_partial_first_playable(self):
        response = self.client.post(
            "/api/v1/advisor/analyze",
            json={
                "clipboard_text": self.clipboard_text,
                "league": "Runes of Aldur",
                "game_data_dataset_version": "poe2db-unknown-version-2026-08-12-task8c-fullx1",
                "crafting_dataset_version": "crafting-actions-poe2-quiver-2026-08-12-research",
                "affix_capacity_dataset_version": "affix-capacity-poe2-2026-08-12-research",
                "outcome_valuation_evidence": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["item"]["base_type"], "Primed Quiver")
        self.assertEqual(body["decision"]["decision_type"], "NO_RECOMMENDATION")
        probability_requirements = [
            item for item in body["missing_requirements"]
            if item["type"] == "PROBABILITY_EVIDENCE_REQUIRED"
        ]
        self.assertTrue(probability_requirements)

    def test_first_playable_scripts_cover_required_public_checks(self):
        start_script = START_SCRIPT.read_text(encoding="utf-8")
        smoke_script = SMOKE_SCRIPT.read_text(encoding="utf-8")
        smoke_python = SMOKE_PYTHON.read_text(encoding="utf-8")

        self.assertIn("uvicorn", start_script)
        self.assertIn("npm", start_script)
        self.assertIn("smoke_first_playable.py", smoke_script)
        self.assertIn("/api/v1/health", smoke_python)
        self.assertIn("/api/v1/items/parse", smoke_python)
        self.assertIn("/api/v1/advisor/analyze", smoke_python)
        self.assertIn("first_playable_quiver_sample.txt", smoke_python)


if __name__ == "__main__":
    unittest.main()
