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

OpenAPI is available at `/openapi.json` and `/docs`.

The API uses local/offline configured datasets. It does not perform runtime PoE2DB, poe.show, or Trade requests.
