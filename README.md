# NASA Fire Harmonization API

Backend de la **NASA Space Apps Challenge 2026** para el reto
**Harmonization of MODIS and VIIRS Hot Spots**.

API HTTP construida con FastAPI que expone observaciones de puntos
calientes satelitales (MODIS/VIIRS) para su exploración desde el
frontend: consultas filtradas, contrato de observaciones estables y
documentación OpenAPI interactiva.

> ⚠️ **Estado de los datos:** los endpoints `/api/v1` sirven datos
> **sintéticos y demostrativos** (`data_provenance: "synthetic_demo"`).
> NO son observaciones reales de NASA. Los endpoints `/api` de ingesta
> (fase F3) sirven **datos reales** del portal IDEAM y de los feeds
> públicos NASA FIRMS, siempre con su procedencia original y
> `is_synthetic: false`.

## Requisitos

- **Python 3.13** o superior (entorno de desarrollo actual: 3.13.17,
  con el launcher `py` disponible).
- Windows con PowerShell (comandos probados en este entorno).

## Instalación

Desde la raíz del repositorio (la carpeta que contiene `app/` y
`requirements.txt`):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ejecución en desarrollo

```powershell
python -m uvicorn app.main:app --reload
```

Documentación interactiva (con el servidor en ejecución):

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Esquema OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

## Endpoints (v0.1.0)

### Sintéticos (contrato v0.1, sin cambios)

| Método | Ruta                     | Descripción                                   |
| ------- | ------------------------ | ---------------------------------------------- |
| `GET` | `/api/v1/health`       | Comprobación de estado (`{"status": "ok"}`) |
| `GET` | `/api/v1/observations` | Observaciones normalizadas, filtro opcional    |

**Parámetros de `GET /api/v1/observations`:**

| Parámetro | Tipo   | Rango                  | Por defecto  |
| ---------- | ------ | ---------------------- | ------------ |
| `sensor` | string | `MODIS` \| `VIIRS` | (sin filtro) |
| `limit`  | int    | 1–1000                | 100          |

Ejemplo:

```powershell
curl "http://127.0.0.1:8000/api/v1/observations?sensor=VIIRS&limit=2"
```

```json
{
  "data": [
    {
      "observation_id": "SYN-VIR-0001",
      "sensor": "VIIRS",
      "latitude": 5.9021,
      "longitude": -68.611,
      "acquired_at": "2026-10-05T13:45:00Z",
      "frp_mw": 30.2,
      "confidence_raw": "h",
      "source": "synthetic_demo"
    }
  ],
  "count": 2,
  "total_matching": 4,
  "data_provenance": "synthetic_demo"
}
```

Parámetros inválidos (sensor desconocido, `limit` fuera de rango)
devuelven **422**. Consultas válidas sin resultados devuelven 200 con
`data: []`.

### Ingesta de datos reales (fase F3, réplica del contrato del proyecto Ejemplo)

| Método | Ruta                           | Fuente real           | Descripción                                              |
| ------- | ------------------------------ | --------------------- | --------------------------------------------------------- |
| `GET` | `/api/health`                | —                    | Estado + capacidades de ingesta                           |
| `GET` | `/api/ideam/directory`       | Portal IDEAM          | Fechas de los CSV diarios disponibles                     |
| `GET` | `/api/ideam/observations`    | IDEAM (CSV diarios)   | Observaciones reales por rango de fechas (máx. 90 días) |
| `GET` | `/api/firms/observations`    | NASA FIRMS NRT 7d     | Observaciones reales (MODIS C6.1 + VIIRS NOAA-20/21)      |
| `GET` | `/api/fusion/observations`   | IDEAM + FIRMS         | Fusión multi-agencia con deduplicación                  |
| `GET` | `/api/fusion/historical-all` | IDEAM archivo + FIRMS | Histórico 2024-01-01 → hoy (muestreado, tope 9000)      |

**Parámetros comunes de las rutas de ingesta:**

| Parámetro        | Tipo           | Descripción                                                                                     |
| ----------------- | -------------- | ------------------------------------------------------------------------------------------------ |
| `from` / `to` | `YYYY-MM-DD` | Rango inclusive; por defecto los últimos 45 días                                               |
| `region`        | alias          | `antioquia` \| `antioquia_ideam` \| `colombia` \| `colombia_wide`                        |
| `bbox`          | string         | `west,south,east,north` o formato extent IDEAM `(N_W_S_E)`; tiene prioridad sobre `region` |

Los datos reales se descargan en vivo desde los portales oficiales y se
cachéan 15 minutos. Si una fuente falla, la respuesta puede degradarse a
un snapshot auténtico previo (`degradedMode: true` + `warning`) o
devolver **502** con `{"ok": false, "error": "..."}`; fechas inválidas
devuelven **400**.

📄 La referencia oficial de contratos compartida con el frontend y el
equipo científico es **`docs/api-contracts.md`**.

## Reglas de dominio (resumen)

- MODIS y VIIRS **no son fuentes intercambiables**: no se suman sus
  conteos ni se asume equivalencia de campos, resolución o confianza.
- `confidence_raw` conserva el valor/categoría **original** del
  producto sin reinterpretar. En la ingesta real existe además un
  `confidence_level`/`confidence_score` **provisional** replicado del
  proyecto de referencia para la UI; NO es la normalización científica
  aprobada (F4), que sigue pendiente de Science Lead y
  Data/ML/Statistics.
- Una ausencia de registros no implica cero actividad; cero
  detecciones y datos faltantes se distinguen en los contratos según lo
  permita la fuente.
- La detección cruzada MODIS/VIIRS del mismo foco (~1.6 km, ±90 min) se
  **marca** con `concordance` en lugar de contarse dos veces sin
  señalización.

## Pruebas

```powershell
python -m pytest -v
python -m pytest tests/test_observations.py -v
```

Las pruebas no requieren servicios externos ni credenciales.

## Lint y formato

```powershell
ruff check .
ruff format --check .
```

## Estructura del proyecto

```text
backend/
├── app/
│   ├── main.py                   # Aplicación FastAPI, routers y CORS
│   ├── api/routes/               # health, observations, status, ideam, firms, fusion
│   ├── schemas/                  # Contratos Pydantic (health, observation, hotspot, ingest)
│   ├── services/                 # Lógica de aplicación (observation, ingest)
│   ├── repositories/             # Ingesta IDEAM/FIRMS + sintético + http_fetch
│   └── utils/                    # geo (bbox/fechas), parsing (CSV), deduplication
├── tests/                        # pytest + TestClient (sin red)
├── docs/
│   └── api-contracts.md          # Contratos compartidos con el equipo
├── requirements.txt
├── pyproject.toml                # Configuración de Ruff y pytest
├── PROJECT_CONTEXT.md            # Contexto de producto y dominio
├── AGENTS.md                     # Convenciones del agente/código
└── ROADMAP.md                    # Fases e historias de usuario
```

Las respuestas degradadas se respaldan en `data/cache/` (excluido del
repositorio).

## Hoja de ruta

El plan de fases y los criterios de aceptación están en `ROADMAP.md`.
Estado vivo, decisiones y aprendizajes del proyecto en `MEMORY.md`.
Fases pendientes inmediatas: integración con el módulo científico (F4),
calendario/analítica (F5) e integración con el frontend (F6).

## Licencia y atribución

Proyecto del equipo Semillero de Astronomía para la NASA Space Apps
Challenge 2026. Los datos sintéticos incluidos son exclusivamente de
demostración.
