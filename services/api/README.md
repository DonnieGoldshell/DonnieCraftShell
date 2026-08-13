# API Service

Python + FastAPI backend for DonnieCraftShell.

Responsibilities:

- Parse pasted item text.
- Normalize rare Quiver data.
- Call item-class analysis modules.
- Retrieve economy snapshots.
- Return partial Advisor analysis and decisions where evidence supports them.

Implemented endpoints:

- `GET /health`
- `GET /api/v1/health`
- `POST /api/v1/items/parse`
- `POST /api/v1/advisor/analyze`

Run locally:

```bash
python -m pip install -r services/api/requirements.txt
python -m uvicorn services.api.app.main:app --reload
```

The local CORS allow-list defaults to the Next.js development origins:

```text
http://localhost:3000
http://127.0.0.1:3000
```

Override with `DCS_CORS_ALLOWED_ORIGINS` as a comma-separated list for other environments.

OpenAPI is available at `/openapi.json` and `/docs`.

The API uses local/offline configured datasets. It does not perform runtime PoE2DB, poe.show, or Trade requests.
