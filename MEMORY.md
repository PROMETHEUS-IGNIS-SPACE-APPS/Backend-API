# MEMORY.md — NASA Fire Harmonization API
Memoria del proyecto entre sesiones. Máximo ~50 líneas: resume o elimina lo que ya no
aporte.
## Estado actual
- F1, F2 y F3-núcleo completadas: `/api/v1/health` + `/api/v1/observations`
  (sintéticos etiquetados) y **ingesta real** réplica fiel del proyecto
  Ejemplo (PROMETHEUS IGNIS): `/api/health`, `/api/ideam/directory`,
  `/api/ideam/observations`, `/api/firms/observations`,
  `/api/fusion/observations`, `/api/fusion/historical-all`.
- Verificado en vivo (2026-11-14): IDEAM 639 obs/5 archivos, FIRMS 3731
  obs/3 feeds, fusión 1342, histórico 9000 condensados/114 cortes.
- 49 pruebas pasando (sin red); Ruff check+format limpios.
- Contratos documentados en `docs/api-contracts.md` (v0.2.0 ingesta).
- Entorno: Python 3.13.17, venv `.venv`; sin dependencias nuevas
  (httpx ya estaba).
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
- Columnas reales IDEAM: `Fecha (UTC-5);Lat;Lon;Fuente;...` — el
  matching exacto del Ejemplo es correcto; `Confianza` usa palabras
  ("Nominal"). Validar siempre contra archivos reales, no ejemplos.
- El offset COT→UTC es +5h (local 06:58 → UTC 11:58); señas al revés
  pasaron los tests solo por/fixtures mal hechos.
- Ruff E501/B023: usar helpers `_text_at/_decimal_at(row, idx)` en
  lugar de condicionales inline; `ruff format` solo a archivos tocados.
- `historical-all` requiere el índice IDEAM COMPLETO para anclas
  semimensuales (no el top-30 del endpoint directory).
- Windows: la consola cp1252 no imprime "→/í"; usar ascii-replace al
  depurar payloads.
## Próximos pasos
- F4/F5 (harmonization/calendar/analytics): bloqueados por definición
  científica; no simular aprobaciones.
- F6: integración con Frontend-UI-UX (CORS ya listo vía env
  `ALLOWED_ORIGINS`; origen de prod por acordar).
- Opcionales: FIRMS Area API con MAP_KEY (por env, nunca versionado),
  `/api/connectors/verify`, clima y reportes ciudadanos (fuera del
  núcleo acordado).
