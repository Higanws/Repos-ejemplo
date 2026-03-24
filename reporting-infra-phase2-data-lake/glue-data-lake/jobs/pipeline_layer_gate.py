"""
Gate DynamoDB para jobs Glue: exige que la capa inmediata anterior esté SUCCEEDED
antes de ejecutar la capa actual (misma corrida pk/sk).

Uso: empaquetar con --extra-py-files. Argumentos opcionales en el JobRun:
  --PIPELINE_RUNS_TABLE  (obligatorio para activar gate)
  --PIPELINE_PROJECT
  --PIPELINE_ENVIRONMENT
  --PIPELINE_BUSINESS_DATE
  --PIPELINE_BATCH_ID
  --PIPELINE_SKIP_LAYER_CHECK  (true = emergencia; no validar)

Desactivar gate: no pasar PIPELINE_RUNS_TABLE o dejar vacío.
"""

from __future__ import annotations

import os
from typing import Any

import boto3

# Alineado con pipeline_layers.py en lambdas (fase 2)
LAYER_RAW = "raw"
LAYER_LAKE_VALIDATED_TO_STANDARDIZED = "lake_validated_to_standardized"
LAYER_LAKE_STANDARDIZED_TO_SILVER = "lake_standardized_to_silver"

# Solo gates inmediatos usados en fase 2.
PREVIOUS_BY_LAYER: dict[str, str] = {
    LAYER_LAKE_VALIDATED_TO_STANDARDIZED: LAYER_RAW,
    LAYER_LAKE_STANDARDIZED_TO_SILVER: LAYER_LAKE_VALIDATED_TO_STANDARDIZED,
}


def previous_layer(layer: str) -> str | None:
    return PREVIOUS_BY_LAYER.get(layer)


def require_previous_layer_succeeded_for_glue(
    *,
    current_layer: str,
    argv: list[str],
) -> None:
    """
    current_layer: capa que este job va a ejecutar (y luego registrar al terminar).
    """
    table = _argv_opt(argv, "PIPELINE_RUNS_TABLE").strip()
    if not table:
        return
    skip = _argv_opt(argv, "PIPELINE_SKIP_LAYER_CHECK").lower()
    if skip in ("1", "true", "yes"):
        return

    prev = previous_layer(current_layer)
    if not prev:
        return

    project = _argv_opt(argv, "PIPELINE_PROJECT") or os.environ.get("PIPELINE_PROJECT", "reporting")
    env = _argv_opt(argv, "PIPELINE_ENVIRONMENT") or os.environ.get("PIPELINE_ENVIRONMENT", "dev")
    bd = _argv_opt(argv, "PIPELINE_BUSINESS_DATE")
    bid = _argv_opt(argv, "PIPELINE_BATCH_ID")
    if not bd or not bid:
        raise RuntimeError(
            f"Gate Dynamo: faltan --PIPELINE_BUSINESS_DATE / --PIPELINE_BATCH_ID "
            f"(requeridos para validar capa anterior {prev!r} antes de {current_layer!r})."
        )

    pk = f"PIPE#{project}#{env}#BDATE#{bd}"
    sk = f"RUN#{bid}"
    ddb = boto3.resource("dynamodb").Table(table)
    resp = ddb.get_item(Key={"pk": pk, "sk": sk})
    item: dict[str, Any] = resp.get("Item") or {}
    layers = item.get("layers") or {}
    pdoc = layers.get(prev) or {}
    st = (pdoc.get("status") or "").upper()
    if st != "SUCCEEDED":
        raise RuntimeError(
            f"Capa anterior {prev!r} no está SUCCEEDED para pk={pk} sk={sk}: "
            f"status={st!r}. No se ejecuta {current_layer!r}."
        )


def _argv_opt(argv: list[str], name: str) -> str:
    prefix = f"--{name}"
    for i, a in enumerate(argv):
        if a == prefix and i + 1 < len(argv):
            return argv[i + 1]
    return ""
