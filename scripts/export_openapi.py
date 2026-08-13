"""Export the FastAPI OpenAPI schema for frontend type generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from services.api.app.main import app


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/export_openapi.py <output-path>", file=sys.stderr)
        return 2
    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
