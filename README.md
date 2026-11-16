# PROMETHEUS IGNIS · Backend-API

<p align="center">
  <strong>FastAPI service for harmonizing and serving MODIS/VIIRS thermal hotspot observations</strong><br>
  <sub>NASA Space Apps Challenge 2026 · ITM Astronomy Seedbed</sub>
</p>

<p align="center">
  <a href="https://github.com/PROMETHEUS-IGNIS/Backend-API"><img src="https://img.shields.io/badge/status-active-success?style=flat-square" alt="Status: active"></a>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/FastAPI-0.161-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/API-contract-v0.2.0-6B2A12?style=flat-square" alt="API contract v0.2.0">
</p>

<p align="center">
  <a href="#spanish">🇪🇸 Español</a> ·
  <a href="#english">🇬🇧 English</a>
</p>

<a id="spanish"></a>

## 1. Purpose

Backend-API is the server-side integration layer for PROMETHEUS IGNIS. It exposes stable HTTP contracts for:

- real IDEAM SMByC daily CSV observations;
- public NASA FIRMS near-real-time feeds;
- multi-source fusion and deduplication;
- Open-Meteo weather context;
- optional server-side Gemini explanations;
- legacy synthetic v0.1 demo observations;
- health, readiness, provenance, cache, and source diagnostics.

The API is built with FastAPI and keeps external credentials on the server. The frontend never receives provider keys.

## 2. Data sources

| Source | Role | Important limitation |
|---|---|---|
| **IDEAM · SMByC** | Historical/daily Colombian hotspot CSV files. | Inclusive query range, maximum 90 days. |
| **NASA FIRMS** | Public NRT feeds for MODIS C6.1 and VIIRS NOAA-20/21. | Public feed covers the recent 7-day window. |
| **Open-Meteo** | Complementary weather context. | Context only; not a fire-confirmation model. |
| **Gemini** | Optional explanation of figures already calculated by the platform. | Requires a server-side API key and provider quota. |

## 3. API surface

### Production ingestion (`/api`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service status, capabilities, key availability flags, and counters. |
| `GET` | `/api/healthz` | Lightweight readiness probe. |
| `GET` | `/api/ideam/directory` | Available IDEAM files and recent dates. |
| `GET` | `/api/ideam/observations` | IDEAM observations by date range and area. |
| `GET` | `/api/firms/observations` | NASA FIRMS public NRT observations. |
| `GET` | `/api/fusion/observations` | IDEAM + FIRMS deduplicated fusion. |
| `GET` | `/api/fusion/historical-all` | Historical sampled window from 2024 to the current date. |
| `GET` | `/api/weather` | Open-Meteo current and recent daily context. |
| `POST` | `/api/ai/explain` | Optional structured Gemini interpretation. |
| `GET/POST/PATCH/DELETE` | `/api/citizen-reports...` | Local/server report contract where enabled. |

### Legacy demo contract (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Versioned legacy health check. |
| `GET` | `/api/v1/observations` | Synthetic demo observations. |

`/api/v1` data is explicitly labeled `data_provenance: "synthetic_demo"` and is not NASA data.

The complete payload contract is maintained in [`docs/api-contracts.md`](docs/api-contracts.md). Interactive documentation is available through Swagger UI and ReDoc.

## 4. Request examples

```bash
# Health
curl http://127.0.0.1:8000/api/health

# Recent IDEAM observations in Antioquia
curl "http://127.0.0.1:8000/api/ideam/observations?from=2026-11-09&to=2026-11-15&region=antioquia_ideam"

# Public FIRMS feed
curl "http://127.0.0.1:8000/api/firms/observations?region=antioquia_ideam"

# Weather context
curl "http://127.0.0.1:8000/api/weather?lat=6.4&lon=-75.6&name=Antioquia"
```

Date ranges are inclusive. Supported regions include `antioquia`, `antioquia_ideam`, `colombia`, and `colombia_wide`. A `bbox` may override the region using `west,south,east,north` or the IDEAM extent notation.

## 5. Requirements

- Python **3.13 or newer**.
- pip and a virtual environment.
- Network access to IDEAM, NASA FIRMS, and Open-Meteo for live ingestion.
- Optional Gemini API key for `/api/ai/explain`.
- Docker Engine/Desktop and Compose v2 for container deployment.

## 6. Local installation

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Linux/macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Documentation:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## 7. Environment variables

```env
# Optional server-side Google AI Studio credential.
GEMINI_API_KEY=

# Optional; defaults to gemini-2.5-flash.
GEMINI_MODEL=gemini-2.5-flash

# Comma-separated browser origins.
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8080

# Optional SQLite path for citizen reports.
CITIZEN_REPORTS_DATABASE=data/citizen_reports.db
```

For a public deployment:

```env
ALLOWED_ORIGINS=https://your-domain.example
```

Never commit `.env`. Rotate a credential immediately if it appears in a screenshot, log, issue, or chat.

## 8. Docker

The backend image uses Python 3.13 slim, installs `requirements.txt`, copies the application, and listens on port 8000.

From the parent directory containing the shared `docker-compose.yml`:

```bash
docker compose build --no-cache backend
docker compose up -d backend
docker compose logs -f backend
```

The Compose setup mounts a named volume at `/data` for the citizen-report SQLite database and uses the backend health endpoint as a readiness condition for the frontend.

## 9. Scientific and domain rules

- MODIS and VIIRS are different products and must not be silently combined as equivalent measurements.
- `confidence_raw` preserves the provider’s original value.
- `confidence_level` and `confidence_score` are provisional presentation heuristics, not an approved scientific harmonization.
- `frp_mw: null` means unavailable; it must not be converted to zero.
- Cross-sensor spatial/temporal matches are marked with `concordance` instead of silently double-counted.
- A zero or missing record set does not prove absence of fire.
- Weather is contextual and experimental; it does not confirm ignition.
- The API exposes provenance, source URLs, cache state, and degraded-mode warnings explicitly.

## 10. Reliability behavior

- IDEAM and fusion responses are cached in memory for approximately 15 minutes.
- Historical responses use a longer cache window and are sampled to a bounded result size.
- If an upstream source fails, an authentic snapshot may be returned with `degradedMode: true` and a warning.
- Without a valid snapshot, the API returns an explicit `400`, `422`, `502`, `503`, or `429` according to the failure.
- Gemini responses are cached in memory for repeated identical requests.

## 11. Development commands

```bash
python -m pytest -v
ruff check .
ruff format --check .
python -m compileall -q app
```

Tests mock upstream providers and do not require external credentials.

## 12. Structure

```text
app/
├── main.py                 # FastAPI app, CORS, routers, OpenAPI metadata
├── api/routes/             # HTTP endpoints
├── schemas/                # Pydantic contracts
├── services/               # Weather, AI, and application services
├── repositories/           # IDEAM, FIRMS, HTTP, cache, and persistence
└── utils/                  # Environment, parsing, geography, deduplication
tests/                      # pytest + TestClient
docs/api-contracts.md       # Shared API contract
Dockerfile                 # Production container
```

## 13. Troubleshooting

### The frontend receives CORS errors

Set `ALLOWED_ORIGINS` to the exact public origin, including scheme and port when applicable:

```env
ALLOWED_ORIGINS=https://your-domain.example
```

Then recreate the backend container:

```bash
docker compose up -d --force-recreate backend
```

### The frontend calls `backend:8000`

That hostname is only valid inside Docker. The browser must call the public frontend origin, while Nginx proxies `/api/` internally.

### Gemini returns `502`

The backend reached the provider but the provider rejected the request, the model is unavailable, the key is invalid/restricted, or the upstream service failed. Check `GEMINI_MODEL`, key permissions, quota, and backend logs without printing the key.

## 14. Attribution

Project by the ITM Astronomy Seedbed for NASA Space Apps Challenge 2026. Data attribution remains attached to every ingestion response and must be preserved by downstream consumers.

---

<a id="english"></a>

# PROMETHEUS IGNIS · Backend-API

<p align="center">
  <strong>FastAPI service for harmonizing and serving MODIS/VIIRS thermal hotspot observations</strong><br>
  <sub>NASA Space Apps Challenge 2026 · ITM Astronomy Seedbed</sub>
</p>

## 1. Purpose

Backend-API is the server-side integration layer for PROMETHEUS IGNIS. It provides stable contracts for real IDEAM observations, public NASA FIRMS feeds, multi-source fusion, Open-Meteo context, optional Gemini explanations, health checks, provenance, caching, and the legacy synthetic demo contract.

Provider credentials remain on the server and are never sent to the frontend.

## 2. Data sources

| Source | Role | Limitation |
|---|---|---|
| **IDEAM · SMByC** | Historical and daily Colombian hotspot CSV files. | Inclusive range, maximum 90 days. |
| **NASA FIRMS** | Public NRT MODIS C6.1 and VIIRS NOAA-20/21 feeds. | Recent 7-day public window. |
| **Open-Meteo** | Complementary weather context. | Context only, not fire confirmation. |
| **Gemini** | Optional explanation of platform figures. | Server key and provider quota required. |

## 3. API surface

### Production API (`/api`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Status, capabilities, key flags, and counters. |
| `GET` | `/api/healthz` | Lightweight readiness probe. |
| `GET` | `/api/ideam/directory` | Available IDEAM files and dates. |
| `GET` | `/api/ideam/observations` | IDEAM observations by range and area. |
| `GET` | `/api/firms/observations` | NASA FIRMS public NRT observations. |
| `GET` | `/api/fusion/observations` | Deduplicated IDEAM + FIRMS fusion. |
| `GET` | `/api/fusion/historical-all` | Sampled history from 2024 to today. |
| `GET` | `/api/weather` | Open-Meteo current and recent daily context. |
| `POST` | `/api/ai/explain` | Optional structured Gemini interpretation. |
| `GET/POST/PATCH/DELETE` | `/api/citizen-reports...` | Citizen report contract where enabled. |

### Legacy demo API (`/api/v1`)

`/api/v1/health` and `/api/v1/observations` expose synthetic data labeled `data_provenance: "synthetic_demo"`. They are not NASA observations.

Full payloads are documented in [`docs/api-contracts.md`](docs/api-contracts.md). Generated documentation is available at `/docs`, `/redoc`, and `/openapi.json`.

## 4. Quick requests

```bash
curl http://127.0.0.1:8000/api/health
curl "http://127.0.0.1:8000/api/ideam/observations?from=2026-11-09&to=2026-11-15&region=antioquia_ideam"
curl "http://127.0.0.1:8000/api/firms/observations?region=antioquia_ideam"
curl "http://127.0.0.1:8000/api/weather?lat=6.4&lon=-75.6&name=Antioquia"
```

Ranges are inclusive. Supported regions include `antioquia`, `antioquia_ideam`, `colombia`, and `colombia_wide`. A `bbox` can override a region.

## 5. Requirements and local setup

- Python **3.13 or newer**.
- pip and a virtual environment.
- Network access to IDEAM, NASA FIRMS, and Open-Meteo for live ingestion.
- Optional Gemini key for `/api/ai/explain`.
- Docker Engine/Desktop and Compose v2 for containers.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 6. Environment variables

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8080
CITIZEN_REPORTS_DATABASE=data/citizen_reports.db
```

For production, set `ALLOWED_ORIGINS` to the exact public origin, for example `https://your-domain.example`. Never commit `.env`; rotate credentials if they appear in screenshots or logs.

## 7. Docker

The image uses Python 3.13 slim and listens on port 8000:

```bash
docker compose build --no-cache backend
docker compose up -d backend
docker compose logs -f backend
```

Compose mounts a named volume at `/data` for the citizen-report SQLite database.

## 8. Scientific and reliability rules

- MODIS and VIIRS are different products and must not be silently treated as equivalent.
- `confidence_raw` preserves the provider value.
- `confidence_level` and `confidence_score` are provisional presentation heuristics.
- `frp_mw: null` means unavailable, not zero.
- Cross-sensor matches use `concordance` instead of silent double counting.
- Missing or zero records do not prove fire absence.
- Weather is contextual and experimental; it does not confirm ignition.
- Provenance, source URLs, cache state, and degraded-mode warnings remain explicit.
- Upstream results are cached; authentic snapshots may be returned with `degradedMode: true`.

## 9. Development and structure

```bash
python -m pytest -v
ruff check .
ruff format --check .
python -m compileall -q app
```

```text
app/
├── main.py                 # FastAPI app, CORS, routers, OpenAPI
├── api/routes/             # HTTP endpoints
├── schemas/                # Pydantic contracts
├── services/               # Weather, AI, and application services
├── repositories/           # IDEAM, FIRMS, HTTP, cache, persistence
└── utils/                  # Environment, parsing, geography, deduplication
tests/                      # pytest + TestClient
docs/api-contracts.md       # Shared API contract
Dockerfile                 # Production container
```

Tests mock upstream providers and do not require external credentials.

## 10. Troubleshooting

### CORS errors

Set `ALLOWED_ORIGINS` to the exact public origin and recreate the backend:

```bash
docker compose up -d --force-recreate backend
```

### The browser calls `backend:8000`

That hostname only works inside Docker. The browser must call the public frontend origin while Nginx proxies `/api/` internally.

### Gemini returns `502`

Check model availability, key restrictions, quota, provider status, and backend logs without printing the key.

## 11. Attribution

ITM Astronomy Seedbed project for NASA Space Apps Challenge 2026. Data attribution remains attached to every ingestion response and must be preserved downstream.
