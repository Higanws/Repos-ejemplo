"""
redshift_sfn_stream_router — Router de fase 3 (analítica / Redshift)

Propósito
---------
    Es la Lambda **solo router**: no ejecuta SQL ni COPY. Escucha el **DynamoDB Stream**
    de `pipeline_runs` (la misma tabla y stream que consume `lake_pipeline_stream_router`
    en el repo de data lake) y, cuando una capa pasa a **SUCCEEDED**, llama a
    **Step Functions** (`states:StartExecution`) para encadenar la siguiente fase.

Capas Dynamo que dispara acción
-------------------------------
    * ``lake_standardized_to_silver`` → arranca la state machine **COPY**
      (Parquet en S3 silver → tablas silver en Redshift vía Lambda ``redshift_sql``).
    * ``redshift_silver`` → arranca la state machine **gold** (SQL de agregados / gold).

Qué NO hace
-----------
    * No escribe estado en Dynamo (eso lo hace la Lambda ``pipeline_runs_dynamo``, invocada por ``redshift_sql``).
    * No corre Glue (eso es ``lake_pipeline_stream_router`` en fase 2).

Entorno (Terraform inyecta)
---------------------------
    ``PIPELINE_COPY_STATE_MACHINE_ARN``, ``PIPELINE_GOLD_STATE_MACHINE_ARN``,
    ``PROJECT``, ``ENVIRONMENT``, ``PIPELINE_RUNS_TABLE`` (referencia; la lectura real es el stream).
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sfn = boto3.client("stepfunctions")
_deser = TypeDeserializer()

# Capas cuyo paso a SUCCEEDED dispara una Step Function en este repo.
LAYERS_TRIGGER_SFN = frozenset({"lake_standardized_to_silver", "redshift_silver"})


def _deserialize_image(image: dict | None) -> dict[str, Any]:
    if not image:
        return {}
    return {k: _deser.deserialize(v) for k, v in image.items()}


def _layer_status(layers: dict[str, Any], layer: str) -> str:
    doc = layers.get(layer)
    if isinstance(doc, dict):
        return (doc.get("status") or "").upper()
    return ""


def _just_succeeded(old_layers: dict[str, Any], new_layers: dict[str, Any], layer: str) -> bool:
    return _layer_status(old_layers, layer) != "SUCCEEDED" and _layer_status(
        new_layers, layer
    ) == "SUCCEEDED"


def _extract_business_date_batch(item: dict[str, Any]) -> tuple[str, str]:
    bd = (item.get("business_date") or "").strip()
    sk = (item.get("sk") or "").strip()
    bid = sk[4:] if sk.startswith("RUN#") else ""
    if not bd:
        pk = item.get("pk") or ""
        if "BDATE#" in str(pk):
            bd = str(pk).split("BDATE#", 1)[-1]
    return bd, bid


def _sanitize_execution_name(prefix: str, bd: str, bid: str) -> str:
    raw = f"{prefix}-{bd}-{bid}-{uuid.uuid4().hex[:8]}"
    s = re.sub(r"[^0-9A-Za-z-_]", "-", raw)
    return s[:80]


def _start_step_functions_execution(
    *,
    state_machine_arn: str,
    execution_name_prefix: str,
    bd: str,
    bid: str,
    project: str,
    env: str,
) -> dict[str, Any]:
    arn = (state_machine_arn or "").strip()
    if not arn:
        raise RuntimeError("ARN de Step Functions no configurado (COPY o gold)")
    payload = {
        "load_date": bd,
        "session_date": bd,
        "batch_id": bid,
        "project": project,
        "environment": env,
    }
    name = _sanitize_execution_name(execution_name_prefix, bd, bid)
    resp = sfn.start_execution(
        stateMachineArn=arn,
        name=name,
        input=json.dumps(payload),
    )
    return {
        "action": "StartExecution",
        "state_machine_arn": arn,
        "execution_arn": resp.get("executionArn"),
        "execution_name": name,
    }


def handler(event: dict, context: Any) -> dict[str, Any]:
    """Procesa registros del stream; una ejecución puede incluir varios records (batch)."""
    results: list[dict[str, Any]] = []
    for record in event.get("Records") or []:
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue
        ddb = record.get("dynamodb") or {}
        new_image = _deserialize_image(ddb.get("NewImage"))
        old_image = _deserialize_image(ddb.get("OldImage"))
        if not new_image:
            continue
        new_layers = new_image.get("layers") or {}
        old_layers = old_image.get("layers") or {}
        if not isinstance(new_layers, dict):
            continue
        bd, bid = _extract_business_date_batch(new_image)
        if not bd or not bid:
            logger.warning(
                "redshift_sfn_stream_router skip_missing_bd_bid pk=%s sk=%s",
                new_image.get("pk"),
                new_image.get("sk"),
            )
            continue
        project = os.environ.get("PROJECT", "reporting")
        env = os.environ.get("ENVIRONMENT", "dev")
        for layer in LAYERS_TRIGGER_SFN:
            if not _just_succeeded(old_layers, new_layers, layer):
                continue
            if layer == "lake_standardized_to_silver":
                out = _start_step_functions_execution(
                    state_machine_arn=os.environ.get("PIPELINE_COPY_STATE_MACHINE_ARN", ""),
                    execution_name_prefix="cp",
                    bd=bd,
                    bid=bid,
                    project=project,
                    env=env,
                )
                logger.info("redshift_sfn_stream_router copy_sfn %s", out)
                results.append(out)
            elif layer == "redshift_silver":
                out = _start_step_functions_execution(
                    state_machine_arn=os.environ.get("PIPELINE_GOLD_STATE_MACHINE_ARN", ""),
                    execution_name_prefix="gd",
                    bd=bd,
                    bid=bid,
                    project=project,
                    env=env,
                )
                logger.info("redshift_sfn_stream_router gold_sfn %s", out)
                results.append(out)
    return {"processed": len(results), "results": results}
