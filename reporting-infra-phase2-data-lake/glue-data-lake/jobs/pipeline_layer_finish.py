"""
Cierre de capa en un job Glue (solo este repo):

  1) Escribe **siempre** la capa como SUCCEEDED en DynamoDB (si hay tabla + fechas de corrida).
  2) El siguiente paso lo disparan los **routers por fase** leyendo el stream de `pipeline_runs` (no PutEvents).

Ejecutar después de job.commit() (validar → ETL → commit → Dynamo → fin).

Argumentos (mismo estilo que pipeline_layer_gate):
  --PIPELINE_RUNS_TABLE
  --PIPELINE_PROJECT / --PIPELINE_ENVIRONMENT / --PIPELINE_BUSINESS_DATE / --PIPELINE_BATCH_ID
  --ENABLE_PIPELINE_EMIT  (legado; encadenamiento real vía DynamoDB Stream)
  --PIPELINE_EVENT_BUS_NAME  (opcional)
  --PIPELINE_EVENTBRIDGE_DISABLED  (no emitir aunque ENABLE_PIPELINE_EMIT)
  --PIPELINE_SKIP_LAYER_FINISH  (emergencia: no Dynamo ni evento)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from pipeline_layer_gate import _argv_opt

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_events = None


def _events_client():
    global _events
    if _events is None:
        _events = boto3.client("events")
    return _events


def _glue_latest_run_id(job_name: str) -> str:
    glue = boto3.client("glue")
    resp = glue.get_job_runs(JobName=job_name, MaxResults=1)
    runs = resp.get("JobRuns") or []
    if not runs:
        return "unknown"
    return str(runs[0].get("Id") or "unknown")


def _emit_pipeline_layer_succeeded(
    *,
    argv: list[str],
    layer: str,
    project: str,
    environment: str,
    business_date: str,
    batch_id: str,
    event_bus_name: str,
) -> None:
    if (_argv_opt(argv, "PIPELINE_EVENTBRIDGE_DISABLED") or os.environ.get("PIPELINE_EVENTBRIDGE_DISABLED") or "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    detail: dict[str, Any] = {
        "layer": layer,
        "project": project,
        "environment": environment,
        "business_date": business_date,
        "batch_id": batch_id,
    }
    entry: dict[str, Any] = {
        "Source": "reporting.pipeline",
        "DetailType": "ReportingPipelineLayerSucceeded",
        "Detail": json.dumps(detail),
    }
    bus = (event_bus_name or "").strip()
    if bus:
        entry["EventBusName"] = bus

    resp = _events_client().put_events(Entries=[entry])
    if resp.get("FailedEntryCount", 0):
        raise RuntimeError(f"put_events failed: {resp!r}")
    logger.info("pipeline_emit_ok layer=%s bd=%s batch=%s", layer, business_date, batch_id)


def record_layer_succeeded_and_emit_next(
    *,
    completed_layer: str,
    job_name: str,
    argv: list[str],
) -> None:
    """
    completed_layer: capa que este job acaba de completar (p.ej. lake_validated_to_standardized).
    """
    skip = (_argv_opt(argv, "PIPELINE_SKIP_LAYER_FINISH") or "").lower()
    if skip in ("1", "true", "yes"):
        logger.warning("pipeline_layer_finish_skipped PIPELINE_SKIP_LAYER_FINISH")
        return

    table = (_argv_opt(argv, "PIPELINE_RUNS_TABLE") or "").strip()
    project = _argv_opt(argv, "PIPELINE_PROJECT") or os.environ.get("PIPELINE_PROJECT", "reporting")
    env = _argv_opt(argv, "PIPELINE_ENVIRONMENT") or os.environ.get("PIPELINE_ENVIRONMENT", "dev")
    bd = _argv_opt(argv, "PIPELINE_BUSINESS_DATE")
    bid = _argv_opt(argv, "PIPELINE_BATCH_ID")
    emit_on = (_argv_opt(argv, "ENABLE_PIPELINE_EMIT") or "").lower() in ("1", "true", "yes")
    event_bus = _argv_opt(argv, "PIPELINE_EVENT_BUS_NAME")

    if not bd or not bid:
        logger.warning("pipeline_layer_finish_missing_bd_bid skip Dynamo/emit")
        return

    if not table:
        logger.warning("pipeline_layer_finish_no_PIPELINE_RUNS_TABLE skip Dynamo")
        if emit_on:
            logger.warning("ENABLE_PIPELINE_EMIT sin tabla; no se emite EventBridge")
        return

    run_id = _glue_latest_run_id(job_name)
    pk = f"PIPE#{project}#{env}#BDATE#{bd}"
    sk = f"RUN#{bid}"
    env_key = f"PIPE#{project}#{env}"
    now = datetime.now(timezone.utc).isoformat()

    layer_doc = {
        "status": "SUCCEEDED",
        "updated_at": now,
        "glue_job_name": job_name,
        "glue_job_run_id": run_id,
        "error_message": None,
    }

    ddb = boto3.resource("dynamodb").Table(table)
    name_map = {"#lr": completed_layer}
    log_entry = [
        {
            "t": now,
            "layer": completed_layer,
            "action": "glue_job_finish",
            "status": "SUCCEEDED",
            "job_name": job_name,
            "run_id": run_id,
        }
    ]
    try:
        ddb.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=(
                "SET env_key = :ek, business_date = :bd, updated_at = :ua, "
                "layers.#lr = :ldoc, "
                "execution_log = list_append(if_not_exists(execution_log, :empty), :elog)"
            ),
            ExpressionAttributeNames=name_map,
            ExpressionAttributeValues={
                ":ek": env_key,
                ":bd": bd,
                ":ua": now,
                ":ldoc": layer_doc,
                ":empty": [],
                ":elog": log_entry,
            },
        )
    except Exception:
        logger.exception("pipeline_dynamo_finish_failed pk=%s sk=%s", pk, sk)
        raise
    logger.info("pipeline_dynamo_layer_ok layer=%s pk=%s sk=%s", completed_layer, pk, sk)

    if emit_on:
        _emit_pipeline_layer_succeeded(
            argv=argv,
            layer=completed_layer,
            project=project,
            environment=env,
            business_date=bd,
            batch_id=bid,
            event_bus_name=event_bus,
        )
