"""Compatibilidad: el encadenamiento entre capas es vía DynamoDB (estado en pipeline_runs + routers por fase).

No se usa EventBridge PutEvents para avanzar el pipeline. El estado RAW lo escribe este repo en Dynamo
(`lib/pipeline_dynamo.py`); el siguiente paso lo reacciona `lake_pipeline_stream_router` en fase 2.
"""

from __future__ import annotations

from typing import Any


def put_pipeline_layer_succeeded(
    *,
    layer: str,
    project: str,
    environment: str,
    business_date: str,
    batch_id: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """
    Reservado por compatibilidad; siempre False.

    El avance del pipeline no depende de eventos en el bus; usá DynamoDB + stream / routers por fase.
    """
    _ = (layer, project, environment, business_date, batch_id, extra)
    return False
