"""Schemas of the AI explanation endpoint (``POST /api/ai/explain``)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AiExplainRequest(BaseModel):
    """Deterministic figures already computed by the frontend, to be explained."""

    mode: Literal["predictability", "calendar"] = Field(
        description="Which module asks for the explanation."
    )
    payload: dict[str, Any] = Field(
        description=(
            "Figures computed by the platform (Markov forecast, validation, "
            "ranking, monthly calendar matrices...). The model may only "
            "interpret these numbers, never add new ones."
        )
    )
    language: Literal["es", "en"] = "es"


class AiExplanation(BaseModel):
    """Structured reading returned by the model (same schema as the reference app)."""

    model_config = ConfigDict(populate_by_name=True)

    resumen_ejecutivo: str = Field(alias="resumenEjecutivo")
    hallazgos_clave: list[str] = Field(alias="hallazgosClave")
    interpretacion_sensores: str = Field(alias="interpretacionSensores")
    interpretacion_markov: str = Field(alias="interpretacionMarkov")
    limitaciones_y_cautela: list[str] = Field(alias="limitacionesYCautela")
    recomendaciones_operativas: list[str] = Field(alias="recomendacionesOperativas")


class AiExplainResponse(BaseModel):
    """Successful AI explanation."""

    model_config = ConfigDict(populate_by_name=True)

    ok: Literal[True] = True
    model: str
    cached: bool
    structured: AiExplanation
    disclaimer: str = Field(
        default=(
            "Lectura generada por IA a partir de las cifras de la plataforma. "
            "No reemplaza el criterio técnico ni la verificación en terreno."
        )
    )
