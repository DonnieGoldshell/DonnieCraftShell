"""First Playable local smoke checks using only Python's standard library."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "samples" / "first_playable_quiver_sample.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check the local DonnieCraftShell First Playable.")
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--web-base-url", default="http://localhost:3000")
    parser.add_argument("--sample-path", default=str(DEFAULT_SAMPLE))
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    sample_path = Path(args.sample_path)
    if not sample_path.exists():
        raise SystemExit(f"Sample clipboard payload not found: {sample_path}")

    clipboard_text = sample_path.read_text(encoding="utf-8")
    api_base = args.api_base_url.rstrip("/")
    web_base = args.web_base_url.rstrip("/")

    print("Smoke check: API health", flush=True)
    health = wait_json(f"{api_base}/api/v1/health", args.timeout_seconds, "API health")
    if health.get("status") != "ok":
        raise SystemExit("API health did not return status ok.")

    print("Smoke check: frontend reachable", flush=True)
    wait_http_ok(web_base, args.timeout_seconds, "Frontend")

    print("Smoke check: item parse", flush=True)
    parse_response = post_json(
        f"{api_base}/api/v1/items/parse",
        {
            "raw_clipboard_text": clipboard_text,
            "game": "Path of Exile 2",
            "league": "Runes of Aldur",
        },
    )
    if parse_response.get("error") is not None:
        error = parse_response["error"]
        raise SystemExit(f"Expected parse response without error, got {error.get('message')}.")
    item = parse_response.get("item") or {}
    if item.get("item_class") != "Quivers":
        raise SystemExit(f"Expected parsed item class Quivers, got {item.get('item_class')}.")

    print("Smoke check: advisor analyze", flush=True)
    advisor_response = post_json(
        f"{api_base}/api/v1/advisor/analyze",
        {
            "clipboard_text": clipboard_text,
            "league": "Runes of Aldur",
            "game_data_dataset_version": "poe2db-unknown-version-2026-08-12-task8c-fullx1",
            "crafting_dataset_version": "crafting-actions-poe2-quiver-2026-08-12-research",
            "affix_capacity_dataset_version": "affix-capacity-poe2-2026-08-12-research",
            "outcome_valuation_evidence": [],
        },
    )
    if not advisor_response.get("analysis_id"):
        raise SystemExit("Advisor response did not include analysis_id.")
    advisor_item = advisor_response.get("item") or {}
    if advisor_item.get("base_type") != "Primed Quiver":
        raise SystemExit(f"Expected Primed Quiver advisor result, got {advisor_item.get('base_type')}.")
    decision = advisor_response.get("decision") or {}
    if decision.get("decision_type") != "NO_RECOMMENDATION":
        raise SystemExit("Expected Advisor decision NO_RECOMMENDATION for fixture-only smoke data.")

    print()
    print("First Playable smoke check passed.")
    return 0


def wait_json(url: str, timeout_seconds: int, name: str) -> dict[str, Any]:
    payload = wait_http_ok(url, timeout_seconds, name)
    return json.loads(payload.decode("utf-8"))


def wait_http_ok(url: str, timeout_seconds: int, name: str) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    return response.read()
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise SystemExit(f"{name} did not respond at {url} within {timeout_seconds} seconds. Last error: {last_error}")


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
