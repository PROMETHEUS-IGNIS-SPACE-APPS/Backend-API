"""Server-side AI explanation of figures computed by the platform (Google Gemini).

The API key lives only in this backend (``GEMINI_API_KEY`` in the environment or
in ``Backend-API/.env``); the frontend never sees it. The model only interprets the
numbers it receives and must not invent or change any of them.
"""

import asyncio
import hashlib
import json
import os
from collections import OrderedDict
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas.ai import AiExplanation
from app.utils.env import load_env_file

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_PAYLOAD_CHARS = 60_000
CACHE_SIZE = 64
TIMEOUT_SECONDS = 45.0

_cache: "OrderedDict[str, AiExplanation]" = OrderedDict()


class AiServiceError(Exception):
    """Error with the HTTP status the route should answer."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def api_key() -> str:
    load_env_file()
    key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    return "" if key in {"", "MY_GEMINI_API_KEY"} else key


def has_api_key() -> bool:
    return bool(api_key())


def model_name() -> str:
    load_env_file()
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


_RULES = (
    "Eres el asistente explicativo científico de PROMETHEUS IGNIS, una plataforma que "
    "muestra detecciones térmicas satelitales (MODIS y VIIRS) en Antioquia y Colombia.",
    "REGLAS ESTRICTAS:",
    "1. Interpreta EXCLUSIVAMENTE las cifras, fechas, estados y métricas que se te "
    "entregan en JSON (pronóstico Markov 3x3 exploratorio, validación retrospectiva, "
    "ranking de celdas, matrices mensuales del calendario con frecuencia por subregión "
    "y FRP promedio en MW).",
    "2. PROHIBIDO inventar métricas, probabilidades, coordenadas o porcentajes que no "
    "estén en los datos, y PROHIBIDO modificar las probabilidades recibidas.",
    "3. Distingue siempre: detección térmica satelital no es incendio confirmado; FRP "
    "(MW) no es área quemada; ausencia de puntos no es ausencia de fuego; la "
    "probabilidad Markov es de actividad térmica satelital, no de ignición ni de "
    "propagación.",
    "4. MODIS (~1 km) y VIIRS (~375 m) son sensores distintos: no sumes ni compares "
    "sus conteos como si fueran equivalentes.",
    "5. Si los datos son insuficientes o la validación es débil (por ejemplo Brier "
    "Skill Score negativo), dilo claramente.",
    "6. No hay factor climático validado en esta plataforma: no lo menciones como si existiera.",
)


def _system_instruction(language: str) -> str:
    target = "inglés claro" if language == "en" else "español claro y preciso"
    closing = f"7. Responde en {target} siguiendo el esquema JSON solicitado."
    return "\n".join((*_RULES, closing))


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "resumenEjecutivo": {
            "type": "STRING",
            "description": "Resumen breve y riguroso de lo que muestran las cifras.",
        },
        "hallazgosClave": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "3 a 4 hallazgos citando cifras reales recibidas.",
        },
        "interpretacionSensores": {
            "type": "STRING",
            "description": "MODIS vs VIIRS, FRP o cobertura observacional según los datos.",
        },
        "interpretacionMarkov": {
            "type": "STRING",
            "description": (
                "Lectura del estado Markov y su validación, o advertencia si no hay "
                "datos suficientes."
            ),
        },
        "limitacionesYCautela": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Cautelas epistémicas y limitaciones.",
        },
        "recomendacionesOperativas": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Sugerencias de monitoreo o verificación en terreno según los datos.",
        },
    },
    "required": [
        "resumenEjecutivo",
        "hallazgosClave",
        "interpretacionSensores",
        "interpretacionMarkov",
        "limitacionesYCautela",
        "recomendacionesOperativas",
    ],
}


def _cache_key(mode: str, payload: dict[str, Any], language: str, model: str) -> str:
    raw = json.dumps(
        {"m": mode, "p": payload, "l": language, "model": model}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def explain(
    mode: str,
    payload: dict[str, Any],
    language: str = "es",
    client: httpx.AsyncClient | None = None,
) -> tuple[AiExplanation, str, bool]:
    """Return (explanation, model, cached). Raises AiServiceError with an HTTP status."""
    key = api_key()
    if not key:
        raise AiServiceError(
            503,
            "La interpretación con IA no está configurada: falta GEMINI_API_KEY en el Backend-API. "
            "Los cálculos de Markov y los mapas siguen funcionando normalmente.",
        )
    payload_text = json.dumps(payload, ensure_ascii=False, indent=1)
    if len(payload_text) > MAX_PAYLOAD_CHARS:
        raise AiServiceError(413, "Los datos enviados para interpretar son demasiado grandes.")

    model = model_name()
    cache_id = _cache_key(mode, payload, language, model)
    if cache_id in _cache:
        _cache.move_to_end(cache_id)
        return _cache[cache_id], model, True

    prompt = (
        f"Modo solicitado: {mode}\n"
        f"Datos deterministas precalculados por la plataforma:\n{payload_text}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": _system_instruction(language)}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    try:
        response: httpx.Response | None = None
        for attempt in range(3):
            try:
                response = await http.post(
                    GEMINI_URL.format(model=model),
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body,
                )
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise AiServiceError(
                        502, f"No se pudo contactar el servicio de IA: {exc.__class__.__name__}."
                    ) from exc
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            if response.status_code in (500, 502, 503, 504) and attempt < 2:
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            break
    finally:
        if owns_client:
            await http.aclose()

    assert response is not None
    if response.status_code == 429:
        raise AiServiceError(
            429,
            "Cuota del servicio de IA alcanzada temporalmente. Intenta de nuevo en unos minutos.",
        )
    if response.status_code in (400, 401, 403):
        raise AiServiceError(
            502,
            "El servicio de IA rechazó la solicitud: revisa GEMINI_API_KEY y GEMINI_MODEL "
            "en el Backend-API.",
        )
    if response.status_code >= 400:
        raise AiServiceError(
            502, f"El servicio de IA no está disponible (HTTP {response.status_code})."
        )

    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        explanation = AiExplanation.model_validate(json.loads(text))
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise AiServiceError(
            502, "La respuesta del servicio de IA no tiene el formato esperado."
        ) from exc

    _cache[cache_id] = explanation
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return explanation, model, False
