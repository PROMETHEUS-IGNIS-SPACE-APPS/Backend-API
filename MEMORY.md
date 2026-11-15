# MEMORY.md — NASA Fire Harmonization API
Memoria del proyecto entre sesiones. Máximo ~50 líneas: resume o elimina lo que ya no
aporte.
## Estado actual
- F1, F2 y F3-núcleo completadas: `/api/v1/health` + `/api/v1/observations`
  (sintéticos etiquetados) y **ingesta real** réplica fiel del proyecto
  Ejemplo (PROMETHEUS IGNIS, versión final 2026-11-14): `/api/health`,
  `/healthz`, `/api/ideam/directory`, `/api/ideam/observations`,
  `/api/firms/observations`, `/api/fusion/observations`.
- **historical-all ELIMINADO** (decisión del usuario 2026-11-14): el
  Ejemplo final ya no lo expone ni su frontend lo consume.
- Alineación con Ejemplo final: `/api/health` usa `hasFirmsKey` +
  `hasGeminiKey` + `citizenReportsCount`; snapshots IDEAM/FIRMS se
  guardan al éxito (antes nunca se escribían → degradado imposible);
  IDs FIRMS con `feed.id` (`FIRMS_MODIS_C6_1_7d_...`); fusión TTL hit
  marca `cached: true`; `failedFiles/failedFeeds` con detalle `(HTTP x)`;
  `/healthz` (readiness, `prometheus-ignis`, `uptimeSec`).
- Modo degradado cubierto por pruebas (14 casos) + fix
  `serialization_alias` → `alias` (bug de validación de snapshots).
- Verificado en vivo (2026-11-14): IDEAM 19 obs/1 día, FIRMS 3993
  obs/3 feeds (IDs nuevos), fusión 4051, 2ª llamada `cached: true`,
  snapshots `last_ideam/last_firms/last_fusion.json` creados.
- 64 pruebas pasando (sin red); Ruff check+format limpios.
- Contratos documentados en `docs/api-contracts.md` (v0.2.0 ingesta).
- Entorno: Python 3.13.17, venv `.venv`; sin dependencias nuevas
  (httpx ya estaba).
- Frontend integrado (2026-11-14): modo `historical` eliminado del
  cliente; mapa replicado del Ejemplo (capas en `map.on('load')`,
  re-agregadas tras `setStyle` con `map.once('style.load')`, guard
  `mapLoaded`); estilo base por defecto = dark. 42/42 tests + build OK.
- Bug MapLibre+Vite resuelto: el worker se resuelve relativo a
  `import.meta.url` y Vite pre-empaqueta la lib → URL inexistente
  ("Worker failed to load", mapa sin puntos). Fix del Ejemplo: importar
  `maplibre-gl/dist/maplibre-gl-worker.mjs?url` y fijar
  `setWorkerUrl(...)` antes de crear el mapa.
## Decisiones (qué cambió y por qué)
- Rutas réplica fiel del Ejemplo (sin `/v1`) decidido por el usuario;
  los endpoints `/api/v1` se conservan intactos (contrato v0.1).
- `confidence_level`/`confidence_score` en ingesta real son heurística
  de UI replicada del Ejemplo, marcada como provisional; la
  normalización científica (F4) sigue bloqueada. No confundirlas.
- Deduplicación + concordancia MODIS/VIIRS (~1.6 km, ±90 min)
  replicadas del `adapters.ts` del Ejemplo.
- Modo degradado: snapshots auténticos en `data/cache/` (gitignored),
  siempre con `degradedMode:true` + `warning` explícito; nunca silencio.
- TLS sin verificación SOLO para el host IDEAM (certificado incompleto
  documentado en el Ejemplo); FIRMS usa verificación normal.
- Horas COT fijas UTC-5 (sin `zoneinfo`, evita depender de `tzdata`).
- Ventana por defecto dinámica (últimos 45 días hasta hoy COT) en vez
  de las fechas duras 2026 del Ejemplo.
- Caché TTL 15 min + deduplicación de peticiones en vuelo (dict de
  asyncio.Task); respuestas Pydantic con aliases camelCase
  (`observedAtUtc`, `degradedMode`, `from`, `filesLoaded`...).
## Aprendizajes y errores a evitar
- Pydantic v2: `serialization_alias` NO sirve para validar (los
  snapshots con claves camelCase no cargaban y el modo degradado habría
  fallado en silencio). Usar `alias=` + `populate_by_name=True` cuando
  el JSON entra y sale con claves camelCase.
- Al replicar una referencia, releerla completa antes de decidir: el
  Ejemplo se actualizó a mitad de sesión y `historical-all` dejó de
  existir; los snapshots IDEAM/FIRMS existían en el Ejemplo pero no los
  replicamos (bug silencioso detectado solo al comparar).
- Columnas reales IDEAM: `Fecha (UTC-5);Lat;Lon;Fuente;...` — el
  matching exacto del Ejemplo es correcto; `Confianza` usa palabras
  ("Nominal"). Validar siempre contra archivos reales, no ejemplos.
- El offset COT→UTC es +5h (local 06:58 → UTC 11:58); señas al revés
  pasaron los tests solo por/fixtures mal hechos.
- Ruff E501/B023: usar helpers `_text_at/_decimal_at(row, idx)` en
  lugar de condicionales inline; `ruff format` solo a archivos tocados.
- Windows: la consola cp1252 no imprime "→/í"; usar ascii-replace al
  depurar payloads.
## Próximos pasos
- F4/F5 (harmonization/calendar/analytics): bloqueados por definición
  científica; no simular aprobaciones.
- F6: integración con Frontend-UI-UX (CORS ya listo vía env
  `ALLOWED_ORIGINS`; origen de prod por acordar).
- Opcionales del Ejemplo final NO implementados (decisión del usuario:
  "ninguna por ahora"): FIRMS Area API con MAP_KEY (por env, nunca
  versionado), `/api/weather`, citizen-reports CRUD (password '1025' del
  Ejemplo — discutir seguridad, AGENTS prohíbe credenciales fijas),
  `/api/gemini/explain`, `/api/connectors/verify`, pre-warm al arrancar.
