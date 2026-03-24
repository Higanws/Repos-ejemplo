"""
Orden de datasets en el lake (referencia / validación en CI).
Fuente operativa en runtime: config/glue_pipeline.json (subido a S3 por Terraform).

RAW no son tablas Glue: la ingesta escribe archivos bajo `validated/<dataset>/` o `rejected/<dataset>/`.
"""

from __future__ import annotations

GLUE_LAYER_DATASET_ORDER: tuple[str, ...] = (
    "trade_event",
    "price_history",
)

# Retrocompatibilidad (nombre antiguo cuando se hablaba de "tablas").
GLUE_LAYER_TABLE_ORDER = GLUE_LAYER_DATASET_ORDER


def _paths_for(ids: tuple[str, ...]) -> dict[str, str]:
    return {tid: f"{tid}/" for tid in ids}


def _paths_validated_raw(ids: tuple[str, ...]) -> dict[str, str]:
    return {tid: f"validated/{tid}/" for tid in ids}


# Clave "raw": prefijos bajo el bucket de landing (archivos), no tablas Glue catalog.
GLUE_DATASET_S3_PATHS: dict[str, dict[str, str]] = {
    "raw": _paths_validated_raw(GLUE_LAYER_DATASET_ORDER),
    "standardized": _paths_for(GLUE_LAYER_DATASET_ORDER),
    "silver": _paths_for(GLUE_LAYER_DATASET_ORDER),
}

GLUE_TABLE_S3_PATHS = GLUE_DATASET_S3_PATHS
