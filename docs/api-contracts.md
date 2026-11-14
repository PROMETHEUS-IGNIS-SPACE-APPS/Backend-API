# API Contracts — NASA Fire Harmonization API

Contratos compartidos entre Backend/API, Frontend/Map/UX, Data/Geospatial,
Data/ML/Statistics y Science Lead. Este documento debe mantenerse
sincronizado con el comportamiento real de la API; si cambian los
endpoints o los esquemas, se actualiza este archivo y sus pruebas.

## Versión 0.2.0 (ingesta de datos reales — réplica del contrato "Ejemplo")

Los endpoints de esta sección replican **exactamente** las rutas y
payloads del servidor de referencia (`server.ts` del proyecto Ejemplo /
PROMETHEUS IGNIS) para que ambos frontends puedan consumir esta API sin
cambios. Los datos provienen **en vivo** de fuentes oficiales públicas:

- **IDEAM - SMByC:** CSV diarios de puntos de calor de Colombia
  (`https://puntosdecalor.ideam.gov.co/archivos-csv/`), delimitador `;`,
  decimales con coma, horas en UTC-5 (Colombia, sin horario de verano).
- **NASA FIRMS Earthdata (NRT público):** feeds CSV 7d de Sudamérica
  (MODIS C6.1, VIIRS NOAA-20, VIIRS NOAA-21), sin MAP_KEY.

### Convenciones de la ingesta real

- Fechas de consulta (`from`/`to`): `YYYY-MM-DD`, inclusivas, máximo
  90 días por consulta en IDEAM.
- Regiones: `antioquia`, `antioquia_ideam`, `colombia`,
  `colombia_wide`, sobrescribibles con `bbox`
  (`west,south,east,north` o extent IDEAM `(N_W_S_E)`).
- Todo registro lleva procedencia: `source`, `source_origin`
  (`IDEAM` | `NASA_FIRMS`), `reference_url` e `is_synthetic: false`.
- `confidence_raw` conserva el valor original del producto
  (MODIS: 0–100; VIIRS: `l`/`n`/`h`; IDEAM: palabra de la columna
  `Confianza`).
- `confidence_level`/`confidence_score` son una **heurística de
  presentación provisional** replicada del proyecto de referencia;
  NO constituyen la normalización científica aprobada (F4 sigue
  bloqueada para esa decisión).
- La concordancia MODIS/VIIRS (~1.6 km, ±90 min) se marca con
  `concordance: coincident_high | coincident_moderate` para evitar
  sobreconteo silencioso.
- Caché en memoria de 15 minutos; respuestas degradadas provienen de
  snapshots auténticos guardados en `data/cache/` y siempre anuncian
  `degradedMode: true` con `warning` explícito.

### GET /api/health

```json
{
  "ok": true,
  "service": "NASA Fire Harmonization API - Public Data Ingest",
  "timestampUtc": "2026-11-14T19:25:25.550672+00:00",
  "hasFirmsMapKey": false,
  "firmsPublicNrtAvailable": true,
  "ideamMaxDaysPerQuery": 90
}
```

### GET /api/ideam/directory

```json
{
  "ok": true,
  "portalUrl": "https://puntosdecalor.ideam.gov.co/archivos-csv/",
  "totalFiles": 1048,
  "latestDates": ["2026-11-14", "2026-11-13"]
}
```

### GET /api/ideam/observations?from=&to=&region=&bbox=

Respuesta `200` (`FusionResponse`), verificada en vivo el 2026-11-14:

```json
{
  "ok": true,
  "cached": false,
  "degradedMode": false,
  "warning": null,
  "metadata": {
    "source": "IDEAM - SMByC Colombia",
    "fetchedAtUtc": "2026-11-14T19:23:00+00:00",
    "from": "2026-11-09",
    "to": "2026-11-13",
    "region": "antioquia_ideam",
    "bbox": {"west": -78.73352, "south": 5.04717, "east": -72.27356, "north": 9.24309},
    "filesLoaded": ["Puntos_de_calor_Colombia_2026-11-09.csv"],
    "rawCount": 639,
    "deduplicatedCount": 639,
    "attribution": "IDEAM - SMByC. Puntos de calor en Colombia (...). Fuente original: NASA LANCE FIRMS."
  },
  "observations": [
    {
      "id": "IDEAM_VIIRS_202611131349_6.3764_-74.3615",
      "observation_id": "IDEAM_VIIRS_202611131349_6.3764_-74.3615",
      "latitude": 6.3764,
      "longitude": -74.3615,
      "acquired_at": "2026-11-13T18:49:00+00:00",
      "observedAtUtc": "2026-11-13T18:49:00+00:00",
      "observedAtLocalCot": "2026-11-13 13:49",
      "acq_date": "2026-11-13",
      "acq_time": "1349",
      "sensor": "VIIRS",
      "satellite": "NOAA-20",
      "instrument": "VIIRS",
      "confidence_raw": "Nominal",
      "confidence_level": "nominal",
      "confidence_score": 60,
      "frp_mw": 5.2,
      "brightness_k": 309.25,
      "secondary_brightness_k": 289.35,
      "scan_km": 0.55,
      "track_km": 0.51,
      "daynight": "N",
      "concordance": "single_sensor",
      "department": "Antioquia",
      "municipality": "Puerto Berrío",
      "source": "IDEAM (VIIRS-NOAA-20)",
      "source_origin": "IDEAM",
      "verification_status": null,
      "quality_flags": [],
      "ingested_at": "2026-11-14T19:23:00+00:00",
      "reference_url": "https://puntosdecalor.ideam.gov.co/archivos-csv/Puntos_de_calor_Colombia_2026-11-13.csv",
      "is_synthetic": false
    }
  ]
}
```

### GET /api/firms/observations?region=&bbox=

Respuesta `200` (`FirmsResponse`): añade `publicNrtMode: true`,
`hasMapKey`, `source`, `feedsLoaded`, `count` y las mismas observaciones.

Verificado en vivo (2026-11-14, Colombia): 3731 registros, 3 feeds,
concordancia marcada en 45 pares.

### GET /api/fusion/observations?from=&to=&region=&bbox=

Igual a `FusionResponse` con `metadata.ideamRawCount`,
`metadata.firmsRawCount` y fusión deduplicada de ambas fuentes.

### GET /api/fusion/historical-all?region=&bbox=

Igual a `FusionResponse`; ventana `2024-01-01` → hoy (fecha COT):
45 días densos + cortes archivísticos semimensuales + FIRMS en vivo,
condensado a los 9000 registros más recientes. Verificado en vivo
(2026-11-14): 9000 registros, 114 archivos fuente, 99 días distintos.

### Errores de la ingesta

- `400`: fecha o rango inválido (`{"ok": false, "error": "..."}`).
- `502`: fuente remota no disponible sin snapshot de respaldo.
- `422`: parámetros con tipo incorrecto (FastAPI).

### Decisiones pendientes (bloqueos registrados, sin cambios)

- `confidence_score` definitivo: requiere método aprobado por
  Science/Data (F4). El valor actual es una heurística de UI y debe
  tratarse como tal.
- Calendario, armonización y analítica siguen bloqueadas hasta la
  definición científica aprobada.

---

## Versión 0.1.0 (MVP — datos sintéticos)

### Convenciones generales

- Base URL local: `http://127.0.0.1:8000`
- Prefijo de versiones: `/api/v1`
- Todas las fechas y horas se expresan en **UTC** (ISO 8601) y se
  clasifican como **adquisición** (`acquired_at`). La semántica exacta
  debe verificarse contra los productos reales.
- Coordenadas en grados decimales: latitud [-90, 90], longitud [-180, 180].
- **Procedencia de los datos:** todos los datos actuales son
  **sintéticos y demostrativos**; no son observaciones reales de NASA.
  El campo `data_provenance` y el texto `source` lo identifican
  explícitamente. Al incorporar datos reales (ROADMAP.md, F3), estos
  campos cambiarán y se anunciará el cambio aquí.

### GET /api/v1/health

Comprobación de estado del servicio.

**Respuesta 200:**

```json
{
  "status": "ok",
  "api_version": "0.1.0"
}
```

### GET /api/v1/observations

Consulta de observaciones de puntos calientes normalizadas.

**Parámetros de consulta:**

| Parámetro | Tipo | Requerido | Rango / valores | Descripción |
|---|---|---|---|---|
| `sensor` | string | No | `MODIS` \| `VIIRS` | Filtro por sensor de origen |
| `limit` | int | No | 1–1000, por defecto 100 | Máximo de registros a devolver (truncamiento simple; sin paginación en v0.1) |

**Respuesta 200:**

```json
{
  "data": [
    {
      "observation_id": "SYN-MOD-0001",
      "sensor": "MODIS",
      "latitude": 5.8412,
      "longitude": -68.5031,
      "acquired_at": "2026-10-05T13:30:00Z",
      "frp_mw": 42.1,
      "confidence_raw": 80,
      "source": "synthetic_demo"
    }
  ],
  "count": 1,
  "total_matching": 1,
  "data_provenance": "synthetic_demo"
}
```

**Descripción de `Observation`:**

| Campo | Tipo | Semántica | Condición |
|---|---|---|---|
| `observation_id` | string | Identificador del registro en el sistema | Requerido |
| `sensor` | string | Sensor de origen: `MODIS` o `VIIRS`. No son fuentes intercambiables ni sus conteos se suman | Requerido |
| `latitude` | float | Grados decimales | Requerido, [-90, 90] |
| `longitude` | float | Grados decimales | Requerido, [-180, 180] |
| `acquired_at` | string (ISO 8601, UTC) | Instante de adquisición con zona horaria explícita | Requerido |
| `frp_mw` | float \| null | Potencia radiativa del fuego en MW; `null` cuando el producto de origen no la proporciona | Opcional |
| `confidence_raw` | int \| string | Valor o categoría de confianza **original** del producto sin reinterpretar. Convención provisional: para MODIS un entero 0–100; para VIIRS una letra `l`/`n`/`h`. La correspondencia definitiva debe verificarse contra archivos reales | Requerido |
| `source` | string | Producto o procedencia del registro (`synthetic_demo` hasta confirmar productos reales) | Requerido |

**Descripción del envoltorio `ObservationCollection`:**

| Campo | Tipo | Semántica |
|---|---|---|
| `data` | array de `Observation` | Registros tras aplicar `limit` |
| `count` | int | Registros devueltos (= `len(data)`) |
| `total_matching` | int | Total de coincidencias **antes** de aplicar `limit`; útil para detectar truncamiento |
| `data_provenance` | string | `synthetic_demo` mientras los datos sean de demostración |

**Errores:**

- Parámetros inválidos (sensor desconocido, `limit` fuera de 1–1000,
  tipos incorrectos): **422** con el formato de error de FastAPI.
- No se encontraron registros: **200** con `data: []`.

### Decisiones pendientes (bloqueos registrados)

- **Esquema definitivo:** el contrato anterior se debe contrastar con
  los archivos reales de MCD14ML/VNP14 (o los productos que confirme el
  equipo) para validar nombres de columnas, unidades y semántica de
  `confidence_raw` y `acquired_at`.
- **`confidence_score`:** NO se incluye hasta que Science Lead y
  Data/ML/Statistics definan y aprueben un método y una escala de
  normalización (ROADMAP.md, HU-002).
- **Filtros temporales y espaciales** (rango de fechas, bounding box):
  pendientes de HU-007 y de coordinar el formato con el frontend.
- **Calendario (`/calendar`), armonización (`/harmonization`) y
  analítica (`/analytics`):** bloqueadas hasta que exista una
  definición científica aprobada del método y las métricas.
