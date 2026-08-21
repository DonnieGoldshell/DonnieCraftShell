# DonnieCraftShell First Playable

This is the first local, user-runnable DonnieCraftShell workflow for Windows.
It starts the FastAPI backend and Next.js frontend together, then verifies the
vertical rare-Quiver slice through the real local API.

The First Playable uses only committed offline/local data. It does not scrape
Trade, poll poe.show, fabricate valuation evidence, fabricate probabilities, or
execute gameplay actions. `NO_RECOMMENDATION`, partial analysis, missing
requirements, and `UNKNOWN` probability are valid expected results.

## Prerequisites

Install these before running from a fresh clone:

- Python 3.11 or newer on `PATH`
- Node.js LTS with `npm` on `PATH`
- Windows PowerShell 5+ or PowerShell 7+

## One-Time Setup

From the repository root:

```powershell
python -m pip install -r services/api/requirements.txt
cd apps\web
npm install
npm run generate:openapi
cd ..\..
```

The app writes local operator workspace files under `.dcs/`. That directory is
git-ignored and is safe for local persistence.

## Start The App

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_first_playable.ps1
```

The launcher starts:

- API: `http://localhost:8000`
- Web: `http://localhost:3000`

It also runs the smoke check automatically. If the browser does not open, visit:

```text
http://localhost:3000
```

Press `Ctrl+C` in the launcher terminal to stop both local processes.

Logs are written to:

```text
.dcs/logs/first-playable-api.out.log
.dcs/logs/first-playable-api.err.log
.dcs/logs/first-playable-web.out.log
.dcs/logs/first-playable-web.err.log
```

## Smoke Check Only

If the API and web app are already running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_first_playable.ps1
```

The smoke check verifies:

- `GET /api/v1/health`
- the frontend root page
- `POST /api/v1/items/parse`
- `POST /api/v1/advisor/analyze`

## Sample Quiver

Use:

```text
samples/first_playable_quiver_sample.txt
```

Paste the entire file into the web workbench and run analysis.

This sample is fixture/example data only. It is not live market evidence and
does not include real valuation or probability evidence. The expected first
playable outcome is a structured partial analysis with `NO_RECOMMENDATION`.

## Configuration

The defaults match the committed offline MVP datasets:

- league: `Runes of Aldur`
- game data: `poe2db-unknown-version-2026-08-12-task8c-fullx1`
- crafting data: `crafting-actions-poe2-quiver-2026-08-12-research`
- affix capacity: `affix-capacity-poe2-2026-08-12-research`

Useful environment overrides:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"
$env:DCS_CORS_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
$env:DCS_OBSERVATION_WORKSPACE_PATH = ".dcs\observation_workspace.json"
$env:DCS_MANUAL_VALUATION_WORKSPACE_PATH = ".dcs\manual_valuation_workspace.json"
$env:DCS_EMPIRICAL_REGISTRY_PATH = ".dcs\empirical_probability_registry.json"
```

## Troubleshooting

If the launcher reports missing backend dependencies, run:

```powershell
python -m pip install -r services/api/requirements.txt
```

If it reports missing frontend dependencies, run:

```powershell
cd apps\web
npm install
cd ..\..
```

If a port is already in use, pick alternate ports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_first_playable.ps1 -ApiPort 8010 -WebPort 3010
```

Then open the URL printed by the launcher.
